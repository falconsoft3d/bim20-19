# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class BimFormula(models.Model):
    _name = 'bim.formula'
    _description = "Measurement Formulas"

    name = fields.Char(string='Name', required=True)
    length = fields.Float(string='Length (X)', digits="BIM qty")
    width = fields.Float(string='Width (Y)', digits="BIM qty")
    height = fields.Float(string='High (Z)', digits="BIM qty")
    formula = fields.Char(string='Formula')

    def name_get(self):
        reads = self.read(['name', 'formula'])
        res = []
        for record in reads:
            name = record['name']
            if record['formula']:
                name = record['formula'] + '=' + name
            res.append((record['id'], name))
        return res

    @api.model
    def default_get(self, fields):
        res = super(BimFormula, self).default_get(fields)
        if 'name' in res:
            res['formula'] = res['name']
            res['name'] = _('New')
        return res


