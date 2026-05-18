# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenancePart(models.Model):
    _name = 'maintenance.part'
    _description = 'Maintenance Part'

    name = fields.Char('Name', copy=False, required=True)