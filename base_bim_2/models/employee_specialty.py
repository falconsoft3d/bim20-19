# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EmployeeSpecialty(models.Model):
    _description = "Employee Specialty"
    _name = 'employee.specialty'
    _order = "id desc"

    name = fields.Char('Name', copy=False)