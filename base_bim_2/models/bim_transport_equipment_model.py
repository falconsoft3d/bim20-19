# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class BimTransportEquipmentModel(models.Model):
    _description = "Bim Transport EquipmentBrand"
    _name = 'bim.transport.equipment.model'
    _order = "id desc"

    name = fields.Char('Name', required=True)
    brand_id = fields.Many2one('bim.transport.equipment.brand', string='Brand', required=True, ondelete='restrict')