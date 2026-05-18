# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstateQuota(models.Model):
    _name = 'real.estate.quota'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Real Estate Quota'
    _order = "id desc"

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    date = fields.Date('Date', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    amount = fields.Monetary('Amount', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    real_state_sale_order_id = fields.Many2one('real.estate.sale.order', string='Sale Order')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False, tracking=True)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)

    account_journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    account_payment_ids = fields.Many2many('account.payment', string='Payments')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('real.estate.quota') or 'New'
        return super().create(vals_list)

    def action_to_draft(self):
        if self.account_payment_id:
            self.account_payment_id.action_cancel()
            self.account_payment_id.unlink()
            self.account_payment_id = False

        self.state = 'draft'


    def action_to_done(self):
        # Create payment
        if not self.account_payment_ids:
            payment = self.env['account.payment'].create({
                'journal_id': self.account_journal_id.id,
                'payment_type': 'inbound',
                'payment_method_id': 1,
                'partner_id': self.partner_id.id,
                'amount': self.amount,
                'currency_id': self.currency_id.id,
                'ref': self.name,
                'date': fields.Date.today(),
            })

            payment.action_post()
            self.account_payment_ids = [(4, payment.id)]

        self.state = 'done'