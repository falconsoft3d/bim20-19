# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class BimTransportEquipmentBrand(models.Model):
    _description = "Bim Transport EquipmentBrand"
    _name = 'bim.transport.equipment.brand'
    _order = "id desc"

    name = fields.Char('Name', required=True)