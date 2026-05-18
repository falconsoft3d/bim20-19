# -*- coding: utf-8 -*-

from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    budget_sample_id = fields.Many2one('bim.budget.sample', string='Budget Sample')
