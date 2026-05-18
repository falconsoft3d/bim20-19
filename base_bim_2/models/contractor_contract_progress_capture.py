# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ContractorContractProgressCapture(models.Model):
    _description = "Contractor Contract Progress Capture"
    _name = 'contractor.contract.progress.capture'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    date = fields.Datetime('Date', required=True, default=fields.Date.today)
    partner_id = fields.Many2one('res.partner', string='Sub Contractor', required=True)
    contractor_contract_id = fields.Many2one('contractor.contract', string='Contract')
    line_ids = fields.One2many('contractor.contract.progress.capture.line', 'progress_capture', string='Lines', copy=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    total = fields.Monetary(string='Total', compute='_compute_total', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('certificate', 'Certificate'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', copy=False, tracking=True)

    certification_by_line_ids = fields.One2many('bim.massive.certification.by.line', 'contractor_contract_progress_capture_id', 'Progress Capture')
    count_certifications = fields.Integer('Quantity Certification', compute="_compute_count_certifications")
    create_oc = fields.Boolean('Create OC')

    def _compute_count_certifications(self):
        for rec in self:
            rec.count_certifications = len(rec.certification_by_line_ids)

    def action_view_certifications(self):
        action = self.env.ref('base_bim_2.bim_massive_certification_by_line_action').sudo().read()[0]
        action['domain'] = [('contractor_contract_progress_capture_id', '=', self.id)]
        action['context'] = {
            'default_contractor_contract_progress_capture_id': self.id,
        }
        return action

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('contractor.contract.progress.capture') or 'New'
        return super().create(vals_list)

    def to_approved(self):
        self.state = 'approved'

    def to_certify(self):
        for record in self:
            budgets_ids = record.line_ids.mapped('budget_id')
            for budget_id in budgets_ids:
                _logger.info('budget_id: %s', budget_id)
                certification_id = self.env['bim.massive.certification.by.line'].search([
                    ('budget_id', '=', budget_id.id),
                    ('state', 'in', ['draft', 'loaded']),
                ], limit=1)

                if not certification_id:
                    certification_id = self.env['bim.massive.certification.by.line'].create({
                        'budget_id': budget_id.id,
                        'same_stage' : True,
                        'project_id': budget_id.project_id.id,
                        'contractor_contract_progress_capture_id': record.id,
                        'stage_id': self.env['bim.budget.stage'].search([
                            ('budget_id', '=', budget_id.id),
                            ('state', '=', 'process'),
                        ], limit=1).id,
                    })
                else:
                    certification_id.stage_id = self.env['bim.budget.stage'].search([
                            ('budget_id', '=', budget_id.id),
                            ('state', '=', 'process'),
                        ], limit=1).id

                line_for_budget = record.line_ids.filtered(lambda x: x.budget_id == budget_id)

                certification_id.only_concept_ids = False
                certification_id.same_stage = True

                for l in line_for_budget:
                    certification_id.only_concept_ids = [(4, l.concept_id.id)]

                certification_id.action_load_lines()

                for l in line_for_budget:
                    concept_id = l.concept_id
                    line = certification_id.certification_stage_ids.filtered(lambda x: x.concept_id == concept_id)
                    line.quantity_to_cert = l.qty



            record.state = 'certificate'

    def to_load(self):
        if self.contractor_contract_id:
            self.line_ids.unlink()
        for line in self.contractor_contract_id.line_ids:
            qty_last = 0

            contractor_contract_progress_capture_line_ids = self.env['contractor.contract.progress.capture.line'].search([
                ('concept_id', '=', line.concept_id.id),
                ('id', '!=', self.id),
            ])

            _logger.info(contractor_contract_progress_capture_line_ids)

            for contractor_contract_progress_capture_line_id in contractor_contract_progress_capture_line_ids:
                if contractor_contract_progress_capture_line_ids.progress_capture.state == 'done':
                    qty_last += contractor_contract_progress_capture_line_id.qty
                    _logger.info("qty_last: " + str(qty_last))

            _logger.info("qty_last t: " + str(qty_last))

            self.env['contractor.contract.progress.capture.line'].create({
                'progress_capture': self.id,
                'project_id': line.project_id.id,
                'budget_id': line.budget_id.id,
                'concept_id': line.concept_id.id,
                'qty_budget': line.qty,
                'qty_last': qty_last,
                'qty': 0,
                'qty_accumulated': 0,
                'price_unit': line.price_unit,
            })

        self.state = 'loaded'

    def to_draft(self):
        try:
            self.purchase_order_id = False
        except:
            pass
        self.state = 'draft'

    def to_done(self):
        qty_total = sum(self.line_ids.mapped('qty'))
        if qty_total <= 0:
            raise UserError(_('You must enter at least one quantity greater than zero.'))


        if self.create_oc:
            purchase_order_id = self.env['purchase.order'].create({
                'partner_id': self.partner_id.id,
                'date_order': self.date,
                'currency_id': self.currency_id.id,
                'company_id': self.company_id.id,
            })

            self.purchase_order_id = purchase_order_id.id
            for line in self.line_ids:

                product_id = self.company_id.paidstate_product
                if not product_id:
                    product_id = self.env['product.product'].search([
                        ('name', '=', line.concept_id.name),
                    ], limit=1)

                if not product_id:
                    product_id = self.env['product.product'].search([], limit=1)

                product_uom = product_id.uom_id.id


                if line.qty > 0:
                    val_line = {
                        'order_id': purchase_order_id.id,
                        'product_id': product_id.id,
                        'name': line.concept_id.name,
                        'product_qty': line.qty,
                        'product_uom': product_uom,
                        'price_unit': line.price_unit,
                        'date_planned': self.date,
                    }

                    _logger.info('val_line: %s', val_line)
                    self.env['purchase.order.line'].create(val_line)


        self.state = 'done'

class ContractorContractProgressCaptureLine(models.Model):
    _name = 'contractor.contract.progress.capture.line'
    _description = 'Contractor Contract Progress Capture Line'

    progress_capture = fields.Many2one(comodel_name="contractor.contract.progress.capture", string="Progress Capture")
    project_id = fields.Many2one(comodel_name="bim.project", string="Project")
    budget_id = fields.Many2one(comodel_name="bim.budget", string="Budget")
    concept_id = fields.Many2one(comodel_name="bim.concepts", string="Concept")
    qty_budget = fields.Float(string="Qty Budget")
    qty_last = fields.Float(string="Qty Last")
    qty = fields.Float(string="Qty Current")
    qty_accumulated = fields.Float(string="Qty Accumulated", compute='_compute_qty_accumulated', store=True)
    currency_id = fields.Many2one('res.currency', related='progress_capture.currency_id', store=True)
    price_unit = fields.Monetary(string="Unit Price")
    amount = fields.Monetary(string="Amount", compute="_compute_amount", store=True)
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')

    @api.depends('qty', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.qty * rec.price_unit


    @api.depends('qty_last', 'qty')
    def _compute_qty_accumulated(self):
        for rec in self:
            rec.qty_accumulated = rec.qty_last + rec.qty
