# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class MaintenanceTaskPlan(models.Model):
    _description = "Maintenance Task Plan"
    _name = 'maintenance.task.plan'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    description = fields.Char('Description')
    observation = fields.Text('Observation')
    maintenance_location_id = fields.Many2one('maintenance.location', string='Location', required=True)

    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)


    maintenance_task_ids = fields.One2many('maintenance.task', 'maintenance_task_plan_id', 'Plan')
    count_maintenance_tasks = fields.Integer('Quantity Tasks', compute="_compute_count_tasks")

    bim_project_id = fields.Many2one('bim.project', string='Project', required=True)

    def _compute_count_tasks(self):
        for rec in self:
            rec.count_maintenance_tasks = len(rec.maintenance_task_ids)

    def action_view_maintenance_tasks(self):
        action = self.env.ref('base_bim_2.action_maintenance_task').sudo().read()[0]
        action['domain'] = [('maintenance_task_plan_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_plan_id': self.id,
            'default_bim_project_id': self.bim_project_id.id,
        }
        return action


    maintenance_asset_ids = fields.One2many('maintenance.asset', 'maintenance_task_plan_id', 'Plan Maintenance Assets')
    count_maintenance_assets = fields.Integer('Quantity Assets', compute="_compute_count_assets")

    def _compute_count_assets(self):
        for rec in self:
            rec.count_maintenance_assets = len(rec.maintenance_asset_ids)


    def action_view_maintenance_assets(self):
        action = self.env.ref('base_bim_2.action_maintenance_asset').sudo().read()[0]
        action['domain'] = [('maintenance_task_plan_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_plan_id': self.id,
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.task.plan') or 'New'
        return super().create(vals_list)