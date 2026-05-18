# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CustomerQuestion(models.Model):
    _description = "Customer Question"
    _name = 'customer.question'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', copy=False)
    long = fields.Integer('Long', default=5)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)