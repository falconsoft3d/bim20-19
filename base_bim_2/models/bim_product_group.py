# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BimProductGroup(models.Model):
    _description = "Bim Product Group"
    _name = 'bim.product.group'

    name = fields.Char('Name', required=True)
    code = fields.Integer('Code', required=True)

    def name_get(self):
        reads = self.read(['code', 'name'])
        res = []
        for record in reads:
            name = record['name']
            code = str(record['code'])
            full_name = "[" + code + '] ' + name
            res.append((record['id'], full_name))
        return res





