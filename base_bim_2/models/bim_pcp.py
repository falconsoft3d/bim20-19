# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class BimPcp(models.Model):
    _description = "Bim Pcp"
    _name = 'bim.pcp'
    _order = "id desc"

    name = fields.Char('Name', copy=False)
    description = fields.Char('Description')
    concept_phase_id = fields.Many2one('concept.phase', string='Parent')