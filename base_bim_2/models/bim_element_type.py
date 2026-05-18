# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class BimElementType(models.Model):
    _description = "Bim Element Type"
    _name = 'bim.element.type'
    _order = "id desc"

    name = fields.Char('Name')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)