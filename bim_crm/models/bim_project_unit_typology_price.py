# -*- coding: utf-8 -*-
from odoo import fields, models, api,_


class BimProjectUnitTypologyPRice(models.Model):
    _name = "bim.project.unit.typology.price"
    _description = "BIM Project Unit Typology Price"

    unit_id = fields.Many2one('bim.project.unit',string="Project Unit", required=True, ondelete='restrict')
    typology_id = fields.Many2one('bim.typology', string="Typology", ondelete='restrict')
    price = fields.Float(string="Price m²", required=True)
    surface = fields.Float(string="Surface m²", required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id.id)

    _sql_constraints = [('unique_unit_typology', 'unique(unit_id, typology_id, surface)', _('The unit and typology and surface must be unique!'))]

    def name_get(self):
        res = []
        for record in self:
            name = record.code
            if record.name:
                name = record.name
            res.append((record.id, name))
        return res

