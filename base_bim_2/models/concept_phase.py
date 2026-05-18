# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ConceptPhase(models.Model):
    _description = "Concept Phase"
    _name = 'concept.phase'
    _order = "id desc"

    name = fields.Char('Name', copy=False)
    description = fields.Char('Description')
    parent_id = fields.Many2one('concept.phase', string='Parent')
    ro = fields.Boolean('RO', default=True)

    # El name es unico
    @api.constrains('name')
    def _check_name(self):
        for record in self:
            if record.name:
                if self.search_count([('name', '=', record.name)]) > 1:
                    raise ValidationError(_('Name must be unique!'))