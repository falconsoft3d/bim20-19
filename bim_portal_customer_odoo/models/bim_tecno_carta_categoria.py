# -*- coding: utf-8 -*-
from odoo import fields, models


class BimTecnoCartaCategoria(models.Model):
    _name = 'bim.tecno.carta.categoria'
    _description = 'Tecno Carta Categoría'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'name'
    _order = 'complete_name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    parent_id = fields.Many2one(
        'bim.tecno.carta.categoria', string='Padre',
        ondelete='restrict', index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    complete_name = fields.Char(
        string='Nombre completo', compute='_compute_complete_name', store=True, recursive=True)
    child_ids = fields.One2many('bim.tecno.carta.categoria', 'parent_id', string='Subcategorías')
    carta_ids = fields.One2many('bim.tecno.carta', 'categoria_id', string='Tecno Cartas')

    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f'{rec.parent_id.complete_name} / {rec.name}'
            else:
                rec.complete_name = rec.name
