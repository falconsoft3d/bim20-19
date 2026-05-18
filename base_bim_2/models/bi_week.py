# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class BiWeek(models.Model):
    _description = "Bi Week"
    _name = 'bi.week'
    _order = 'id desc'

    name = fields.Char('Code')
    date_from = fields.Date('Date From', required=True)
    date_to = fields.Date('Date To', required=True)