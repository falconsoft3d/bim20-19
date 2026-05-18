# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class BimTemplateXls(models.Model):
    _description = "Bim Template Xls"
    _name = 'bim.template.xls'
    _order = "id desc"


    name = fields.Char('Name')
    code = fields.Text('Code', default="[[DEPARTURE,PARTIDA],[PARENT,PADRE],[TYPE,NAT],[UOM,UNIDAD],[NAME,DESCRIPCION DE PARTIDA],[QTY,MEDICION],[PRICE,PRECIO],[AMOUNT,IMPORTE]]")
    description = fields.Text('Description')