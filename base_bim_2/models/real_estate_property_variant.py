# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class RealEstatePropertyVariant(models.Model):
    _description = "Real Estate Property Variant"
    _name = 'real.estate.property.variant'
    _order = "id desc"

    name = fields.Char('Name')