# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeArea(models.Model):
    _description = "Employee Area"
    _name = 'employee.area'
    _order = "id desc"

    name = fields.Char('Name', copy=False)