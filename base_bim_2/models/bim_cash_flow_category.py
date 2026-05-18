# -*- coding: utf-8 -*-
# Part of Marlon Falcon Hernandez. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class BimCashFlowCategory(models.Model):
    _description = "Bim Cash Flow Category"
    _name = 'bim.cash.flow.category'
    _order = "id desc"

    name = fields.Char('Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)