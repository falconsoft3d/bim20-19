# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstatePriceList(models.Model):
    _description = "Real Estate Price List"
    _name = 'real.estate.price.list'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Name')
    number_quotas = fields.Integer('Number of Quotas')
    initial_payment = fields.Monetary('Initial Payment')
    initial_percentage = fields.Float('Initial %', default=10)
    price = fields.Monetary('Price')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    user_id = fields.Many2one(comodel_name="res.users", string="User", default=lambda self: self.env.user, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    type_price = fields.Selection([
        ('property', 'Property'),
        ('list_price', 'List Price'),
    ], string='Type', default='list_price', copy=False, tracking=True)