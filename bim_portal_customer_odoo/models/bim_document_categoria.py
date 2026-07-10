# -*- coding: utf-8 -*-
from odoo import fields, models


class BimDocumentCategoria(models.Model):
    _name = 'bim.document.categoria'
    _description = 'Categoría de Documento BIM'
    _order = 'sequence, name'

    name = fields.Char('Nombre', required=True)
    sequence = fields.Integer('Secuencia', default=10)
    active = fields.Boolean('Activo', default=True)


class BimDocumentationPortal(models.Model):
    _inherit = 'bim.documentation'

    portal_categoria_id = fields.Many2one(
        'bim.document.categoria',
        string='Categoría',
        ondelete='set null',
    )
