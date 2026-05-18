# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeCategory(models.Model):
    _description = "Employee Category"
    _name = 'employee.category'
    _order = "id desc"

    name = fields.Char('Name', copy=False)