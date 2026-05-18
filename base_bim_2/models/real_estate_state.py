# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RealEstateState(models.Model):
    _name = 'real.estate.state'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Real Estate State'
    _order = "sequence asc, id desc"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=16)