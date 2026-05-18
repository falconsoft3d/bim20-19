# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ConceptSpecialty(models.Model):
    _description = "Concept Specialty"
    _name = 'concept.specialty'
    _order = "id desc"

    name = fields.Char('Name', copy=False)
    description = fields.Char('Description')
    parent_id = fields.Many2one('concept.specialty', string='Parent')