# -*- coding: utf-8 -*-
from random import randint
from odoo import fields, models, api


class BimBudgetExtra(models.Model):
    _name = "bim.budget.extra"
    _description = "BIM Budget Extra"

    def _get_default_color(self):
        return randint(1, 11)
    color = fields.Integer(string='Color', default=_get_default_color)
    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)
    price = fields.Float(string="Price", required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id.id)

    def name_get(self):
        res = []
        for record in self:
            name = record.code
            if record.name:
                name = record.name
            res.append((record.id, name))
        return res

