# -*- coding: utf-8 -*-
from odoo import fields, models, api


class BudgetRequest(models.Model):
    _inherit = "budget.request"

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', check_company=True,
                                     tracking=True,
                                     domain="[('type', '=', 'opportunity'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")