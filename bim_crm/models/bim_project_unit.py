# -*- coding: utf-8 -*-
from odoo import fields, models, api


class BimProjectUnit(models.Model):
    _name = "bim.project.unit"
    _description = "BIM Project Unit"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)
    typology_ids = fields.Many2many('bim.typology', string="Typologies")
    product_id = fields.Many2one('product.product', string='Product', domain="[('type', '=', 'service')]", required=True, ondelete='restrict')

    def name_get(self):
        res = []
        for record in self:
            name = record.code
            if record.name:
                name = record.name
            res.append((record.id, name))
        return res

