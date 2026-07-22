# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PurchaseValuation(models.Model):
    _description = "Purchase Valuation"
    _name = 'purchase.valuation'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char('Code', default="New", copy=False)
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    purchase_id = fields.Many2one('purchase.order', 'Purchase Order')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('received', 'Recibido'),
        ('canceled', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        tracking=True,
        default='draft')
    create_date = fields.Datetime('Creation Date', readonly=True, index=True, copy=False, default=fields.Date.context_today)
    date = fields.Date('Date', default=fields.Date.context_today)
    line_ids = fields.One2many('purchase.valuation.line', 'valuation_id', 'Lines')
    include_for_bim = fields.Boolean(tracking=True, default=True)
    project_id = fields.Many2one('bim.project', 'Project', related='purchase_id.project_id', store=True)
    partner_id = fields.Many2one('res.partner', 'Supplier', related='purchase_id.partner_id', store=True)

    price_subtotal = fields.Float('Base', compute='_compute_price_subtotal', store=True)
    tax_subtotal = fields.Float('Taxes Subtotal', compute='_compute_price_subtotal', store=True)
    price_total = fields.Monetary('Price Total', compute='_compute_price_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='purchase_id.currency_id', store=True)
    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice',
        required=False)
    payment_term_id = fields.Many2one('account.payment.term', related='purchase_id.payment_term_id', store=True)
    valuation_sign = fields.Binary('Sign', attachment=True)
    purchase_valuation_reference = fields.Binary(string="Valoración Firmada")
    balance_oc = fields.Float('Balance OC', compute='_compute_balance_oc')

    begin_date = fields.Date('Begin Date')
    end_date = fields.Date('End Date')
    technical_approval = fields.Boolean('Aprobación Técnica', tracking=True)
    financial_approval = fields.Boolean('Aprobación Finanzas', tracking=True)

    def action_received(self):
        self.write({'state': 'received'})


    @api.depends('purchase_id.amount_total', 'price_total')
    def _compute_balance_oc(self):
        for rec in self:
            rec.balance_oc = rec.purchase_id.amount_total - sum(rec.purchase_id.purchase_valuation_ids.mapped('price_total'))


    @api.depends('line_ids.price_subtotal')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = sum(line.price_subtotal for line in rec.line_ids)
            rec.tax_subtotal = sum(line.tax_subtotal for line in rec.line_ids)
            rec.price_total = rec.price_subtotal + rec.tax_subtotal

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.valuation') or 'New'
        return super().create(vals_list)

    def action_for_invoice(self):
        self.write({'state': 'for_invoice'})


    def action_approve(self):
        for rec in self:
            if not rec.technical_approval or not rec.financial_approval:
                raise ValidationError(_('Debe marcar Aprobación Técnica y Aprobación Finanzas para poder aprobar.'))
        self.write({'state': 'approved'})


    def action_draft(self):
        self.write({'state': 'draft'})


    def load_lines(self):
        if self.purchase_id.closed_valuation:
            raise ValidationError(_('The purchase order has a closed valuation'))

        self.line_ids.unlink()
        bim_general_config_id = self.env['bim.general.config'].search([('key', '=', 'valoration')], limit=1)

        if not bim_general_config_id:
            pos = '3'
        else:
            pos = bim_general_config_id.value


        for line in self.purchase_id.order_line:
            product_type = line.product_id.type

            if product_type == 'service' and pos == '2':
                continue

            if product_type in ['consu', 'combo'] and pos == '1':
                continue

            self.line_ids.create({
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.price_unit,
                'valuation_id': self.id,
                'discount': line.discount,
                'taxes_id': line.tax_ids.ids,
                'description': line.name,
                'concept_phase_id': line.concept_phase_id.id,
                'purchase_line_id': line.id,
            })

    def action_done(self):
        if self.price_total <= 0:
            raise ValidationError(_('The total amount must be greater than 0'))

        if self.price_total > self.purchase_id.amount_total:
            raise ValidationError(_('The total amount of the valuation is greater than the total amount of the purchase order'))

        """
        if not self.account_move_id:
            self.create_invoice()
            """

        self.write({'state': 'done'})


    def update_invoice(self):
        # Revisamos si las lineas de factura tiene las líneas de las OC
        if self.account_move_id:
            for line in self.account_move_id.invoice_line_ids:
                if not line.purchase_line_id:
                    purchase_line_id = self.purchase_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id)
                    if purchase_line_id:
                        line.purchase_line_id = purchase_line_id.id

    def create_invoice(self):
        invoice_obj = self.env['account.move']

        if self.account_move_id:
            if self.account_move_id.state == 'draft':
                self.account_move_id.unlink()

        if not self.line_ids:
            raise ValidationError(_('No lines to invoice'))

        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.purchase_id.partner_id.id,
            'purchase_id': self.purchase_id.id,
            'currency_id': self.purchase_id.currency_id.id,
            'company_id': self.purchase_id.company_id.id,
            'include_for_bim': True,
            'project_id': self.project_id.id,
            'date': self.date,
            'invoice_origin': self.purchase_id.name,
            }


        invoice_line_ids = []

        for line in self.line_ids:
            vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'quantity': line.product_qty,
                    'product_uom_id': line.product_uom_id.id,
                    'price_unit': line.price_unit,
                    'tax_ids': line.taxes_id.ids,
                    'discount': line.discount,
                    'concept_phase_id': line.concept_phase_id.id,
                    'project_id': self.project_id.id,
                    'budget_id': self.purchase_id.budget_id.id,
                    'concept_id': self.purchase_id.concept_id.id,
                }

            if line.purchase_line_id:
                vals['purchase_line_id'] = line.purchase_line_id.id
            else:
                purchase_line_ids = self.purchase_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id)
                purchase_line_id = purchase_line_ids and purchase_line_ids[0] or False

                if purchase_line_id:
                    vals['purchase_line_id'] = purchase_line_id.id


            analytic_id = self.project_id.analytic_id.id and self.project_id.analytic_id.id or False
            if analytic_id:
                    vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })

            invoice_line_ids.append((0, 0, vals))
            invoice_vals.update({'invoice_line_ids': invoice_line_ids})

        invoice_id = invoice_obj.create(invoice_vals)
        self.account_move_id = invoice_id.id
        self.write({'state': 'invoiced'})

        # Muestro la factura creada
        return {
            'name': _('Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice_id.id,
            'target': 'current',
        }

    def action_view_invoice(self):
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        action['domain'] = [('id', '=', self.account_move_id.id)]
        return action

    def action_cancel(self):
        self.write({'state': 'canceled'})


class PurchaseValuationLine(models.Model):
    _description = "Purchase Valuation Line"
    _name = 'purchase.valuation.line'

    purchase_id = fields.Many2one('purchase.order', 'Purchase Order', related='valuation_id.purchase_id', store=True)
    partner_id = fields.Many2one('res.partner', 'Supplier', related='valuation_id.partner_id', store=True)
    product_qty_oc = fields.Float('Quantity OC', compute='_compute_product_qty')

    price_unit_oc = fields.Float('Unit Price OC', compute='_compute_product_price_unit')
    total_oc = fields.Float('Total OC', compute='_compute_total_oc')
    create_date = fields.Datetime('Creation Date', compute='_compute_create_date')
    company_id = fields.Many2one('res.company', 'Company', related='valuation_id.company_id', store=True)


    valuation_id = fields.Many2one('purchase.valuation', 'Valuation')
    product_id = fields.Many2one('product.product', 'Product', required=True)
    product_qty = fields.Float('Quantity', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'UOM', required=True)
    price_unit = fields.Float('Unit Price', required=True)
    discount = fields.Float('Discount %', required=False, default=0.0)
    taxes_id = fields.Many2many(comodel_name='account.tax', string='Taxes')
    price_subtotal = fields.Float('Subtotal', compute='_compute_price_subtotal', store=True)
    tax_subtotal = fields.Monetary('Tax Subtotal', compute='_compute_price_subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_price_subtotal', string='Total', store=True)
    price_unit_discounted = fields.Float('Unit Price (Discounted)', compute='_compute_price_unit_discounted')
    currency_id = fields.Many2one('res.currency', related='valuation_id.currency_id', store=True)
    description = fields.Text('Description')
    concept_phase_id = fields.Many2one('concept.phase', 'Concept Phase')
    purchase_line_id = fields.Many2one('purchase.order.line', 'Purchase Line')

    begin_date = fields.Date('Begin Date', related='valuation_id.begin_date')
    end_date = fields.Date('End Date', related='valuation_id.end_date')
    date = fields.Date('Date', related='valuation_id.date')
    state = fields.Selection(related='valuation_id.state', store=True)


    @api.depends('purchase_id')
    def _compute_create_date(self):
        for line in self:
            line.create_date = line.purchase_id.create_date


    @api.depends('product_qty', 'price_unit')
    def _compute_total_oc(self):
        for line in self:
            line.total_oc = line.product_qty_oc * line.price_unit_oc

    @api.depends('purchase_id')
    def _compute_product_price_unit(self):
        for line in self:
            line.price_unit_oc = line.purchase_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id).price_unit

    @api.onchange('purchase_id')
    def _compute_product_qty(self):
        for line in self:
            line.product_qty_oc = sum(line.purchase_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id).mapped('product_qty'))


    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            currency=self.currency_id,
            product=self.product_id,
            taxes=self.taxes_id,
            price_unit=self.price_unit,
            quantity=self.product_qty,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
        )

    @api.depends('discount', 'price_unit')
    def _compute_price_unit_discounted(self):
        for line in self:
            line.price_unit_discounted = line.price_unit * (1 - line.discount / 100)

    @api.depends('product_qty', 'price_unit', 'discount', 'taxes_id')
    def _compute_price_subtotal(self):
        for line in self:
            price = line.price_unit * (1 - line.discount / 100.0)
            taxes = line.taxes_id.compute_all(
                price,
                currency=line.valuation_id.currency_id,
                quantity=line.product_qty,
                product=line.product_id,
            )
            line.price_subtotal = taxes['total_excluded']
            line.tax_subtotal = taxes['total_included'] - taxes['total_excluded']
            line.price_total = taxes['total_included']

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id.id