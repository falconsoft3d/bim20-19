# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeBimPayroll(models.Model):
    _description = "Employee Bim Payroll"
    _name = 'employee.bim.payroll'
    _order = "id desc"

    name = fields.Char('Name', copy=False)