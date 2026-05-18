# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstateLot(models.Model):
    _description = "Real Estate Lot"
    _name = 'real.estate.lot'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']


    name = fields.Char('Name')
    real_estate_development_id = fields.Many2one(comodel_name="real.estate.development", string="Development")
    real_estate_block_id = fields.Many2one(comodel_name="real.estate.block", string="Block")

    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Contact")
    price = fields.Monetary('Price')
    cost = fields.Monetary('Cost')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('not_available', 'Not Available'),
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('blocked', 'Blocked'),
    ], string='State', default='not_available', required=True, copy=False, tracking=True)