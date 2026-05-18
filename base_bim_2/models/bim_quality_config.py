# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class BimInspectionType(models.Model):
    _description = "Inspection Type"
    _name = 'bim.inspection.type'
    _order = "id desc"

    name = fields.Char(required=True)


class BimRegisterType(models.Model):
    _description = "Inspection Type"
    _name = 'bim.register.type'
    _order = "id desc"

    name = fields.Char(required=True)