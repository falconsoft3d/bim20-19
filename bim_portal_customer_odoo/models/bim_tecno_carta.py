# -*- coding: utf-8 -*-
from odoo import fields, models


class BimTecnoCarta(models.Model):
    _name = 'bim.tecno.carta'
    _description = 'Tecno Carta'
    _order = 'titulo'

    titulo = fields.Char(string='Título', required=True, translate=True)
    texto = fields.Html(string='Texto', sanitize=True, sanitize_style=True, translate=True)
    categoria_id = fields.Many2one(
        'bim.tecno.carta.categoria', string='Categoría',
        ondelete='set null', index=True)
    active = fields.Boolean(default=True)
