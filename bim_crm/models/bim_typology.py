# -*- coding: utf-8 -*-
from random import randint

from odoo import fields, models, api

class BimTypology(models.Model):
    _name = "bim.typology"
    _description = "BIM Typology"
    def _get_default_color(self):
        return randint(1, 11)
    color = fields.Integer(string='Color', default=_get_default_color)
    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)

    def name_get(self):
        res = []
        for record in self:
            name = record.code
            if record.name:
                name = record.name
            res.append((record.id, name))
        return res

