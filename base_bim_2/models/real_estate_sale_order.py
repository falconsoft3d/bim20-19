# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from dateutil.relativedelta import relativedelta

class RealEstateSaleOrder(models.Model):
    _description = "Real Estate Sale Order"
    _name = 'real.estate.sale.order'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    date = fields.Date('Start Date', required=True, default=fields.Date.today)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('real.estate.sale.order.line', 'real_state_sale_order_id', string='Sale Order Lines')
    real_estate_price_list = fields.Many2one('real.estate.price.list', string='Price List')


    amount_total = fields.Monetary('Total', store=True, compute='_amount_all')
    state_id = fields.Many2one(
        'real.estate.state', string='State', index=True, tracking=True,
        compute='_compute_state_id', readonly=False, store=True,
        copy=False, ondelete='restrict', default= lambda s: s.env['real.estate.state'].search([], limit=1))


    # quotas
    cash_flow_ids = fields.One2many('bim.cash.flow','real_state_sale_order_id', string='Cash Flows')
    cash_flow_count = fields.Integer(compute='compute_cash_flow_count')

    def compute_cash_flow_count(self):
        for record in self:
            record.cash_flow_count = len(record.cash_flow_ids)

    def action_view_cash_flows(self):
        action = self.env.ref('base_bim_2.action_bim_cash_flow').sudo().read()[0]
        action['domain'] = [('real_state_sale_order_id', '=', self.id)]
        action['context'] = {
            'default_real_state_sale_order_id': self.id,
            'default_company_id': self.company_id.id,
            'default_currency_id': self.currency_id.id,
        }
        return action


    # quotas
    quota_ids = fields.One2many('real.estate.quota','real_state_sale_order_id', string='Quotas')
    quota_count = fields.Integer(compute='compute_quota_count')

    total_paid = fields.Monetary('Total Paid', compute='_compute_total_paid')

    def action_crate_cash_flow(self):
        if not self.quota_ids:
            raise UserError(_('You must create at least one quota to create the cash flow'))

        for quota in self.quota_ids:
            bim_project_id = self.line_ids[0].property_id.project_ids[0] if self.line_ids[0].property_id.project_ids else False
            budget_id = self.line_ids[0].property_id.budget_ids[0] if self.line_ids[0].property_id.budget_ids else False

            bim_cash_flow_id = self.env['bim.cash.flow'].create({
                'date': quota.date,
                'budgeted': quota.amount,
                'note': quota.name,
                'company_id': quota.company_id.id,
                'currency_id': quota.currency_id.id,
                'contact_id': quota.partner_id.id if quota.partner_id else self.partner_id.id,
                'type': 'income',
                'real_state_sale_order_id': self.id,
                'bim_project_id': bim_project_id.id if bim_project_id else False,
                'bim_budget_id': budget_id.id if budget_id else False,
                'payments_ids': [(4, quota.account_payment_ids.id)] if quota.account_payment_ids else False,
                'real': sum(quota.account_payment_ids.mapped('amount'))
            })

    def _compute_total_paid(self):
        for record in self:
            record.total_paid = sum(record.quota_ids.filtered(lambda x: x.state == 'done').mapped('amount'))

    def compute_quota_count(self):
        for record in self:
            record.quota_count = len(record.quota_ids)


    def action_view_quotas(self):
        action = self.env.ref('base_bim_2.action_real_estate_quota').sudo().read()[0]
        action['domain'] = [('real_state_sale_order_id', '=', self.id)]
        action['context'] = {
            'default_real_state_sale_order_id': self.id,
            'default_company_id': self.company_id.id,
            'default_currency_id': self.currency_id.id,
        }
        return action

    def action_create_quotas(self):
        _logger.info('action_create_quotas')
        if not self.line_ids:
            raise UserError(_('You must add at least one property to create the quotas'))

        if self.amount_total <= 0:
            raise UserError(_('The total amount must be greater than zero'))

        if not self.real_estate_price_list:
            raise UserError(_('You must select a price list'))

        number_quotas = self.real_estate_price_list.number_quotas
        amount = self.amount_total
        initial_payment = self.real_estate_price_list.initial_payment
        initial_percentage = self.real_estate_price_list.initial_percentage

        n_cuota = 0
        if initial_payment > 0:
            n_cuota += 1
            amount -= initial_payment
            self.env['real.estate.quota'].create({
                'date': self.date,
                'partner_id': self.partner_id.id,
                'amount': initial_payment,
                'real_state_sale_order_id': self.id,
                'account_journal_id': self.env['account.journal'].search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id,
            })

        if initial_percentage > 0:
            n_cuota += 1
            amount -= (initial_percentage / 100) * self.amount_total
            self.env['real.estate.quota'].create({
                'date': self.date,
                'partner_id': self.partner_id.id,
                'amount': amount,
                'real_state_sale_order_id': self.id,
                'account_journal_id': self.env['account.journal'].search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id,
            })

        # Cramos las cuotas
        for i in range(1, number_quotas + 1):

            # Incrementamos la fecha cada mes
            next_date = self.date
            if n_cuota > 0:
                next_date = self.date + relativedelta(months=i)



            self.env['real.estate.quota'].create({
                'date': next_date,
                'partner_id': self.partner_id.id,
                'amount': amount / number_quotas,
                'real_state_sale_order_id': self.id,
                'account_journal_id': self.env['account.journal'].search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('real.estate.sale.order') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids')
    def _amount_all(self):
        for order in self:
            amount_total = 0.0
            for line in order.line_ids:
                amount_total += line.subtotal
            order.update({
                'amount_total': amount_total,
            })

class RealStateSaleOrderLine(models.Model):
    _name = 'real.estate.sale.order.line'
    _description = 'Real Estate Sale OrderLine'
    _rec_name = 'property_id'

    real_estate_development_id = fields.Many2one(comodel_name="real.estate.development", string="Development")
    real_estate_block_id = fields.Many2one(comodel_name="real.estate.block", string="Block")
    property_id = fields.Many2one(comodel_name="real.estate.property", string="Property")
    real_state_sale_order_id = fields.Many2one(comodel_name="real.estate.sale.order", string="Sale Order")
    subtotal = fields.Monetary('Subtotal', store=True)
    company_id = fields.Many2one('res.company', string='Company', related='real_state_sale_order_id.company_id')
    currency_id = fields.Many2one('res.currency', related='real_state_sale_order_id.currency_id')

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.real_state_sale_order_id.real_estate_price_list.type_price == 'property':
            self.subtotal = self.property_id.price if self.property_id.price > 0 else self.real_state_sale_order_id.real_estate_price_list.price
        else:
            self.subtotal = self.real_state_sale_order_id.real_estate_price_list.price