# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCurrencyState(models.Model):
    _inherit = 'res.currency.rate'

    exchange_operator = fields.Selection([('/','/'),('*','*')], default='/', required=True)

