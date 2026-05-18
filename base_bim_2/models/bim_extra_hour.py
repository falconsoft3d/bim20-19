# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class BimExtraHour(models.Model):
    _description = "Bim Extra Hour"
    _name = 'bim.extra.hour'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Name')
    value = fields.Float(string="Value", digits='BIM price')
    factor = fields.Float(string="Factor", digits='BIM factor')
    desc = fields.Char('Description')