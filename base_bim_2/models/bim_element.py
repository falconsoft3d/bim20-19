# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class BimElement(models.Model):
    _description = "Bim Element"
    _name = 'bim.element'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name')
    code = fields.Char('Code')
    weight = fields.Float('Weight')
    volume = fields.Float('Volume')
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    bim_element_type_id = fields.Many2one('bim.element.type', string='Element Type', required=True)
