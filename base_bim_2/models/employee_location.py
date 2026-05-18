# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeLocation(models.Model):
    _description = "Employee Location"
    _name = 'employee.location'
    _order = "id desc"

    name = fields.Char('Name', copy=False)