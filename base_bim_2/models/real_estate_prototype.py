# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstatePrototype(models.Model):
    _description = "Real Estate Prototype"
    _name = 'real.estate.prototype'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']


    name = fields.Char('Name')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')