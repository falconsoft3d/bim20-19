# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeDiscipline(models.Model):
    _description = "Employee Discipline"
    _name = 'employee.discipline'
    _order = "id desc"

    name = fields.Char('Name', copy=False)