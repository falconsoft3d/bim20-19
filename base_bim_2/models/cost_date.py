# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CostDate(models.Model):
    _description = "Cost Date"
    _name = 'cost.date'
    _order = "id desc"

    name = fields.Char('Name')
    begin_date = fields.Date('Begin Date')
    end_date = fields.Date('End Date')
    cost = fields.Float('Cost')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)