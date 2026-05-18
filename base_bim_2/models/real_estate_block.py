# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstateBlock(models.Model):
    _description = "Real Estate Block"
    _name = 'real.estate.block'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']


    name = fields.Char('Name')
    real_estate_development_id = fields.Many2one(comodel_name="real.estate.development", string="Development")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)