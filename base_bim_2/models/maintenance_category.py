# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceCategory(models.Model):
    _name = 'maintenance.category'
    _description = 'Maintenance Category'

    name = fields.Char('Name', copy=False, required=True)
    parent_id = fields.Many2one('maintenance.category', 'Parent Category', index=True)