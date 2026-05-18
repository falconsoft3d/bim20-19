# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceTypeTask(models.Model):
    _name = 'maintenance.type.task'
    _description = 'Maintenance Type Task'

    name = fields.Char('Name', copy=False, required=True)