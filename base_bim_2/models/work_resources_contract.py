# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class WorkResourcesContract(models.Model):
    _description = "Work Resources Contract"
    _name = 'work.resources.contract'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('work.resources.contract.line', 'work_resources_contract_id', string='Lines')
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('work.resources.contract') or 'New'
        return super().create(vals_list)



class WorkResourcesContractLine(models.Model):
    _description = "Work Resources Contract Line"
    _name = 'work.resources.contract.line'

    name = fields.Many2one('product.product', string='Product', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    price_unit = fields.Float('Unit Price', required=True)
    work_resources_contract_id = fields.Many2one('work.resources.contract', string='Contract', required=True)
