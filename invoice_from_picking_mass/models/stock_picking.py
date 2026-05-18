# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _order = "id desc"

    state_invoice = fields.Selection([
        ('to_invoice', 'Por Facturar'),
        ('invoiced', 'Facturado'),
    ], 'Facturación', default='to_invoice', copy=False, tracking=True)