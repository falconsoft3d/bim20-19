# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CostSettlement(models.Model):
    _description = "Cost Settlement"
    _name = 'cost.settlement'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    stage_id = fields.Many2one('bim.budget.stage', string='Stage')
    line_ids = fields.One2many('cost.settlement.line', 'cost_settlement_id', string='Lines')

    begin_date = fields.Date('Begin Date')
    end_date = fields.Date('End Date')

    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', 'Certification')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('read', 'Read'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='State', readonly=True, copy=False, index=True, tracking=True, default='draft')

    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        if self.stage_id:
            self.begin_date = self.stage_id.date_start
            self.end_date = self.stage_id.date_stop

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('cost.settlement') or 'New'
        return super().create(vals_list)

    def action_read(self):
        self.state = 'read'

        # Buscamos la etapa del presupuesto
        stage_id = self.env['bim.budget.stage'].search([('budget_id', '=', self.budget_id.id),
                                                         ('date_start', '=', self.begin_date),
                                                         ('date_stop', '=', self.end_date)], limit=1)
        if stage_id:
            self.stage_id = stage_id.id
        else:
            stage_id = self.env['bim.budget.stage'].create({
                'budget_id': self.budget_id.id,
                'name': self.name,
                'date_start': self.begin_date,
                'date_stop': self.end_date,
                'state': 'draft',
            })

            self.stage_id = stage_id.id


        #  Buscamos las lineas de las facturas


        if self.begin_date and self.end_date:
            invoice_line_ids = self.env['account.move.line'].search([
                                                                        ('budget_id', '=', self.budget_id.id),
                                                                        ('move_id.invoice_date', '>=', self.begin_date),
                                                                        ('move_id.invoice_date', '<=', self.end_date),
                                                                        ('move_id.include_for_bim', '=', True),
                                                                        ('move_id.cost_settlement_id', '=', False),
                                                                        ('move_id.state', '=', 'posted')
                                                                    ])
        else:
            invoice_line_ids = self.env['account.move.line'].search([
                                                                        ('budget_id', '=', self.budget_id.id),
                                                                        ('move_id.include_for_bim', '=', True),
                                                                        ('move_id.cost_settlement_id', '=', False),
                                                                        ('move_id.state', '=', 'posted')
                                                                    ])

        if invoice_line_ids:
            for line in invoice_line_ids:
                # Revisamos si ya se ha creado esa partida y no la agregamos
                if self.line_ids.filtered(lambda x: x.concept_id.id == line.concept_id.id):
                    continue

                self.env['cost.settlement.line'].create({
                    'cost_settlement_id': self.id,
                    'concept_id': line.concept_id.id,
                    'account_id': line.move_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'product_id': line.product_id.id,
                    'qty_departure': line.concept_id.quantity,
                })

                line.move_id.cost_settlement_id = self.id

        else:
            raise ValidationError(_('No invoices found for this period'))


    def action_draft(self):
        # Desvinculamos la facturas
        account_move_ids = self.env['account.move'].search([('cost_settlement_id', '=', self.id)])
        for move in account_move_ids:
            move.cost_settlement_id = False

        self.line_ids.unlink()
        self.state = 'draft'

    def action_done(self):
        if not self.stage_id.state == 'process':
            self.stage_id.state = 'process'

        certification_id = self.env['bim.massive.certification.by.line'].create({
                        'budget_id': self.budget_id.id,
                        'same_stage' : True,
                        'project_id': self.budget_id.project_id.id,
                        'stage_id': self.stage_id.id,
                    })

        certification_id.only_concept_ids = False
        certification_id.same_stage = True

        for l in self.line_ids:
            certification_id.only_concept_ids = [(4, l.concept_id.id)]

        certification_id.action_load_lines()

        for l in self.line_ids:
            concept_id = l.concept_id
            line = certification_id.certification_stage_ids.filtered(lambda x: x.concept_id == concept_id)
            line.quantity_to_cert = l.qty_certification


        if certification_id:
            self.bim_massive_certification_by_line_id = certification_id.id


        self.state = 'done'



class CostSettlementLine(models.Model):
    _description = "Cost Settlement Line"
    _name = 'cost.settlement.line'
    _order = "id desc"

    cost_settlement_id = fields.Many2one('cost.settlement', string='Cost Settlement')
    concept_id = fields.Many2one('bim.concepts', string='Concept')
    account_id = fields.Many2one('account.move', string='Invoice')
    quantity = fields.Float('Quantity', default=1.0)
    price_unit = fields.Float('Price Unit')
    product_id = fields.Many2one('product.product', string='Product')
    total = fields.Float('Total', compute='_compute_total', store=True)

    qty_departure = fields.Float('Qty Departure')
    qty_certification = fields.Float('Qty Certification', compute='_compute_qty_certification', store=True)


    @api.depends('quantity', 'price_unit')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.quantity * rec.price_unit


    @api.depends('qty_departure')
    def _compute_qty_certification(self):
        for rec in self:
            # Calculamos la cantidad de ese producto en la partida
            departure_qty = rec.qty_departure
            product_qty = self.env['bim.concepts'].search([
                                ('product_id', '=', rec.product_id.id),
                                ('budget_id', '=', rec.cost_settlement_id.budget_id.id),
                                ('parent_id', '=', rec.concept_id.id),
                                ], limit=1)

            final_qty_certification = rec.qty_departure * product_qty.quantity
            rec.qty_certification = rec.quantity / final_qty_certification * departure_qty if ( final_qty_certification * departure_qty > 0 ) else 1