# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class FrameworkContract(models.Model):
    _description = "Framework Contract"
    _name = 'framework.contract'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    title = fields.Char('Title', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    amount = fields.Float('Amount', required=True, digits='BIM price')
    total_projects = fields.Float('Total Projects', digits='BIM price')
    pending_contract = fields.Float('Pending Contract', compute="_compute_pending_contract", store=True)


    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    create_date = fields.Datetime('Create Date', default=fields.Datetime.now)
    observation = fields.Text('Observation')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('framework.contract') or 'New'
        return super().create(vals_list)




    bim_project_ids = fields.One2many('bim.project', 'framework_contract_id', 'Projects')
    count_bim_projects = fields.Integer('Quantity Projects', compute="_compute_count_bim_projects")

    def _compute_count_bim_projects(self):
        for rec in self:
            rec.count_bim_projects = len(rec.bim_project_ids)
            rec.total_projects = sum([x.balance for x in rec.bim_project_ids])

    def action_view_bim_project(self):
        action = self.env.ref('base_bim_2.action_bim_proect').sudo().read()[0]
        action['domain'] = [('framework_contract_id', '=', self.id)]
        action['context'] = {
            'default_framework_contract_id': self.id,
            'default_contact_id': self.partner_id.id,
        }
        return action

    @api.depends('amount', 'total_projects')
    def _compute_pending_contract(self):
        for rec in self:
            rec.pending_contract = rec.amount - rec.total_projects