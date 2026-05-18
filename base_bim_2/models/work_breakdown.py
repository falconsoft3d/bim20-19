# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class WorkBreakdown(models.Model):
    _description = "Work Breakdown"
    _name = 'work.breakdown'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code')
    description = fields.Char('Description')
    bim_pcp_id = fields.Many2one('bim.pcp', 'PCP', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    percentage = fields.Float('Percentage', default=0)