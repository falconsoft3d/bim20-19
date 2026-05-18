# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class HrSize(models.Model):
    _name = 'hr.size'
    _description = 'Hr Size'

    name = fields.Char('Size', copy=False, required=True)
    type = fields.Selection(
        [('shirt', 'Shirt'), ('pants', 'Pants'),
         ('shoes', 'Shoes'), ('jacket', 'Jacket'),
         ('gloves', 'Gloves'), ('vest', 'Vest'),
         ('jacket', 'Jacket'),
         ('tshirt', 'T-shirt'), ('polo', 'Polo')],
        string='Type',
        required=True)