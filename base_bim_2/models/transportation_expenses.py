# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class TransportationExpenses(models.Model):
    _description = "Transportation Expenses"
    _name = 'transportation.expenses'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'description'

    name = fields.Char('Code', default="New", copy=False)
    description = fields.Char('Description')
    product_id = fields.Many2one('product.product', string='Product')
    account_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic account')
    type = fields.Selection([
        ('only', 'only'),
        ('recurrent', 'Recurrent')], string='Type',    tracking=True, default='only', copy=False, index=True)
    price = fields.Float('Price')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('transportation.expenses') or 'New'
        return super().create(vals_list)