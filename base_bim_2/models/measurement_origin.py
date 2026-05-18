# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class MeasurementOrigin(models.Model):
    _description = "Measurement Origin"
    _name = 'measurement.origin'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Name')
    description = fields.Text('Description')
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)