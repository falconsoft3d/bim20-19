# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class BimAccountMove(models.Model):
    _inherit = "account.move"

    budget_ids = fields.Many2many('bim.budget', string='Budgets', compute="_compute_budget_ids")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict",
                                 domain="[('budget_id','=',budget_id),('type','=','departure')]")
    project_id = fields.Many2one('bim.project', 'Project',
                 tracking=True, domain="[('company_id','=',company_id)]", store=True)
    workorder_id = fields.Many2one('bim.work.order', 'Work Order')

    bim_classification = fields.Selection([('income', 'Income'), ('expense', 'Expense')], string='BIM Classification',
                                          index=True)
    include_for_bim = fields.Boolean(tracking=True)
    date_include_for_bim = fields.Date("Date Include for BIM")
    bim_multi_project = fields.Boolean(default=lambda self: self.env.company.bim_invoice_multiple_project)
    bim_recurring_contract_id = fields.Many2one('bim.recurring.contract', string='Recurring Contract')

    retention = fields.Monetary('Retention' , compute='_compute_retention', store=True)
    retention_percentage = fields.Float('Retention (%)')
    total_pay_retention = fields.Monetary('Total a Pagar', compute='_compute_total_pay_retention')
    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', 'Certification')

    certification_now_origin = fields.Monetary('Certification Now Origin')
    certification_now_last = fields.Monetary('Certification Now Last')
    cost_settlement_id = fields.Many2one('cost.settlement', 'Cost Settlement')
    bim_expense_id = fields.Many2one('bim.expense', 'Bim Expense')

    def create_purchase_valuation(self):
        purchase_valuation_id = self.env['purchase.valuation'].search([
            ('account_move_id', '=', self.id)
        ])

        if purchase_valuation_id:
            raise UserError('Ya existe una valuación de compra ( %s ) para esta factura ' % purchase_valuation_id.name)


        else:
            if not self.invoice_origin:
                raise UserError('No se puede crear una valuación de compra sin el número de orden de compra')

            # Compra
            purchase_order_id = self.env['purchase.order'].search([
                ('name', '=', self.invoice_origin)
            ])

            if not purchase_order_id:
                raise UserError('No se encontró la orden de compra con el número %s' % self.invoice_origin)

            else:
                vals = {
                        'purchase_id': purchase_order_id.id,
                        'project_id': purchase_order_id.project_id.id,
                        'company_id': self.company_id.id,
                        'currency_id': self.currency_id.id,
                        'account_move_id': self.id,
                        'state': 'invoiced',
                        'date': self.invoice_date,
                        }

                purchase_valuation_id = self.env['purchase.valuation'].create(vals)

                # recorremos las lineas de la factura
                for line in self.invoice_line_ids:
                    vals = {
                        'valuation_id': purchase_valuation_id.id,
                        'product_id': line.product_id.id,
                        'description': line.name,
                        'product_qty': line.quantity,
                        'product_uom_id': line.product_uom_id.id,
                        'price_unit': line.price_unit,
                        'taxes_id': [(6, 0, line.tax_ids.ids)],
                        }

                    self.env['purchase.valuation.line'].create(vals)





    def action_update_retention(self):
        for rec in self:
            rec._compute_retention()


    # Calculamos el project_id en base a la primera linea de factura y su cuenta analitica
    @api.onchange('invoice_line_ids','state')
    def _onchange_invoice_bim_line_ids(self):
        for rec in self:
            if rec.invoice_line_ids:
                if rec.invoice_line_ids[0].project_id and rec.state == 'draft':
                    rec.project_id = rec.invoice_line_ids[0].project_id

    # _onchange_total_pay_retention
    @api.depends('retention','retention_percentage','amount_total')
    def _compute_total_pay_retention(self):
        for rec in self:
            total_pay_retention = rec.amount_total - rec.retention
            if rec.amount_total_signed < 0:
                total_pay_retention = total_pay_retention * -1
            rec.total_pay_retention = total_pay_retention


    @api.depends('retention_percentage', 'amount_untaxed','state','line_ids')
    def _compute_retention(self):
        for rec in self:
            rec.retention = rec.retention_percentage / 100 * rec.amount_untaxed

    def cron_run_include_bim(self):
        for rec in self.search([('include_for_bim', '=', False),
                                ('date_include_for_bim', '!=', False),
                                ('date_include_for_bim', '<=', fields.Date.today()),
                                ('state', '=', 'posted')]):
            rec.include_for_bim = True

    # action_post
    def action_post(self):
        res = super().action_post()
        for rec in self:
            if rec.project_id:
                rec.project_id.update_project_cost()
                rec.project_id.update_sale_project_cost()

            if rec.invoice_line_ids:
                for line in rec.invoice_line_ids:
                    if line.budget_id and line.analytic_account_id:
                        account_analytic_line_id = self.env['account.analytic.line'].search([
                            ('move_line_id', '=', line.id),
                        ], limit=1)
                        if account_analytic_line_id:
                            account_analytic_line_id.ref = "[" + line.budget_id.code + "] " + line.budget_id.name

                    if line.budget_id:
                        line.budget_id.project_id.update_project_cost()
                        line.budget_id.project_id.update_sale_project_cost()
                    else:
                        if line.project_id:
                            line.project_id.update_project_cost()
                            line.project_id.update_sale_project_cost()
        return res

    @api.depends('project_id', 'move_type', 'bim_classification')
    def _compute_budget_ids(self):
        for rec in self:
            budget_domain = []
            if rec.project_id:
                budget_domain.append(('project_id', '=', rec.project_id.id))
                if rec.move_type == 'in_invoice' or (rec.move_type == 'entry' and rec.bim_classification == 'expense'):
                    budget_domain.append(('state_id.allow_supplier_invoice', '=', True))
            if len(budget_domain) > 0:
                rec.budget_ids = self.env['bim.budget'].search(budget_domain).ids
            else:
                rec.budget_ids = False

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if 'move_type' in values and values['move_type'] == 'in_refund':
            values['include_for_bim'] = self.env.company.bim_include_refund
        elif 'move_type' in values and values['move_type'] == 'in_invoice':
            values['include_for_bim'] = self.env.company.bim_include_invoice_purchase
        elif 'move_type' in values and values['move_type'] == 'out_invoice':
            values['include_for_bim'] = self.env.company.bim_include_invoice_sale
        return values

    @api.onchange('concept_id')
    def _onchange_concept_id(self):
        for record in self:
            if record.move_type in ['in_invoice', 'in_refund', 'in_receipt'] and not record.bim_multi_project:
                for line in record.invoice_line_ids:
                    line.concept_id = record.concept_id.id

    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        for record in self:
            record.concept_id = False
            if record.move_type in ['in_invoice', 'in_refund', 'in_receipt'] and not record.bim_multi_project:
                for line in record.invoice_line_ids:
                    line.budget_id = record.budget_id.id
                    line.concept_id = False

    @api.onchange('project_id')
    def _onchange_project_id(self):
        for record in self:
            record.budget_id = False
            record.concept_id = False
            for line in record.invoice_line_ids:
                line.budget_id = False
                line.concept_id = False
                line.analytic_distribution = {str(record.project_id.analytic_id.id): 100}
                line.project_id = record.project_id



class BimAccountMoveLine(models.Model):
    _inherit = "account.move.line"

    budget_id = fields.Many2one('bim.budget', domain="[('id','in',budget_ids)]")
    budgetr_id = fields.Many2one('bim.budget', string='Budget (Invoice)', related='move_id.budget_id')
    concept_id = fields.Many2one('bim.concepts', 'Concept',
                                 domain="[('budget_id','=',budget_id),('type','=','departure')]")
    budget_ids = fields.Many2many('bim.budget', string='Budgets', compute='_compute_budget_ids')
    bim_multi_project = fields.Boolean(related='move_id.bim_multi_project')
    project_id = fields.Many2one('bim.project')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', ondelete="restrict",
                                          domain="[('company_id','=',company_id)]",
                                          readonly=False, store=True,
                                          tracking=True, compute="_compute_analytic_account_id")
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')

    detailed_type = fields.Selection(related='product_id.type', store=True, string='Tipo Producto')
    invoice_date = fields.Date(related='move_id.invoice_date', store=True, string='Fecha Factura')
    state = fields.Selection(related='move_id.state', store=True, string='Estado Factura')
    price_subtotal_signed = fields.Monetary(compute='_compute_price_subtotal_signed', string='Subtotal (Signed)', store=True)

    @api.depends('price_subtotal')
    def _compute_price_subtotal_signed(self):
        for line in self:
            line.price_subtotal_signed = line.price_subtotal
            if line.move_id.move_type in ['out_refund', 'in_refund']:
                line.price_subtotal_signed *= -1
            else:
                line.price_subtotal_signed = line.price_subtotal


    @api.depends('analytic_line_ids')
    def _compute_analytic_account_id(self):
        for line in self:
            analytic_account_id = False
            if line.analytic_line_ids:
                analytic_account_id = line.analytic_line_ids[0].account_id.id
            line.analytic_account_id = analytic_account_id

    @api.onchange('product_id')
    def _onchange_product_id_line(self):
        for line in self.filtered(lambda line: line.account_id.account_type not in (
                'asset_receivable', 'liability_payable') or line.tax_line_id):
            if line.move_id.project_id and line.move_id.project_id.analytic_id:
                line.analytic_distribution = {str(line.move_id.project_id.analytic_id.id): 100}

            line.budget_id = line.move_id.budget_id
            line.concept_id = line.move_id.concept_id
            line.project_id = line.move_id.project_id

    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        for line in self:
            if line.analytic_distribution:
                analytic_id = int(list(line.analytic_distribution.keys())[0])
                if analytic_id:
                    project_id = self.env['bim.project'].search([('analytic_id', '=', analytic_id)], limit=1)
                    if project_id:
                        line.project_id = project_id.id
            else:
                line.project_id = False


    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        for line in self:
            line.concept_id = False

    @api.depends('move_id.project_id', 'bim_multi_project', 'analytic_distribution', 'product_id')
    def _compute_budget_ids(self):
        for record in self:
            budget_list = record.project_id.budget_ids

            if record.move_id.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
                budget_list = budget_list.filtered(lambda x: x.state_id.allow_supplier_invoice)

            record.budget_ids = budget_list.ids or []