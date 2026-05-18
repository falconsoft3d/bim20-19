# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
from math import ceil
from datetime import timedelta
import random
import string

class EmployeeDocumentation(models.Model):
    _description = "Employee Documentation"
    _name = 'employee.documentation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    title = fields.Char('Title', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True,
                                 copy=False)
    expiration_date = fields.Date('Expiration Date', required=True)
    hr_employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    file = fields.Binary('File', attachment=True)
    file_name = fields.Char('File Name')

    state = fields.Selection([
        ('valid', 'Valid'),
        ('expired', 'Expired'),
    ], string='State', default='valid', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('employee.documentation') or 'New'
        return super().create(vals_list)


    @api.onchange('expiration_date')
    def _onchange_expiration_date(self):
        if self.expiration_date and self.expiration_date < fields.Date.today():
            self.state = 'expired'
        else:
            self.state = 'valid'