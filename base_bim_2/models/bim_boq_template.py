# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class BimBoqTemplate(models.Model):
    _name = 'bim.boq.template'
    _description = 'Bim Boq Template'
    _order = 'id desc'

    name = fields.Char("Reference", required=True, copy=False)
    quantity_name = fields.Char("Quantity Name", required=True, copy=False)
    code_name = fields.Char("Code Name", required=True, copy=False)
    type = fields.Selection([('csv', 'Csv'), ('xls', 'Excel')], string="Type", required=True, default='csv')
