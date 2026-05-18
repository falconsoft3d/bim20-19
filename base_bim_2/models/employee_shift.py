# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeShift(models.Model):
    _description = "Employee Shift"
    _name = 'employee.shift'
    _order = "id desc"

    name = fields.Char('Name', copy=False)