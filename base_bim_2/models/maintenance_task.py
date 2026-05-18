# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class MaintenanceTask(models.Model):
    _description = "Maintenance Task"
    _name = 'maintenance.task'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    maintenance_type_task_id = fields.Many2one('maintenance.type.task', string='Type Task', required=True)
    maintenance_category_1 = fields.Many2one('maintenance.category', string='Category 1')
    maintenance_category_2 = fields.Many2one('maintenance.category', string='Category 2')
    priority = fields.Selection([
            ('0', 'Very low'),
            ('1', 'Low'),
            ('2', 'Normal'),
            ('3', 'High'),
            ('4', 'Very high'),
            ], 'Priority', default='2')
    estimated_duration = fields.Float('Estimated Duration  (minutes)')
    maintenance_downtime = fields.Float('Downtime (minutes)')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', tracking=True)
    maintenance_task_plan_id = fields.Many2one('maintenance.task.plan', string='Task Plan')

    maintenance_activator_ids = fields.One2many('maintenance.activator', 'maintenance_task_id', 'Task')
    count_maintenance_activator = fields.Integer('Quantity Activator', compute="_compute_count_activator")

    cost = fields.Monetary('Cost' , compute='_compute_cost')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    note = fields.Text('Note')
    digital_signature = fields.Binary(string='Signature')

    maintenance_work_request_id = fields.Many2one('maintenance.work.request', string='Work Request')
    maintenance_asset_id = fields.Many2one('maintenance.asset', string='Asset')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('maintenance.task') or 'New'
        return super().create(vals_list)

    @api.depends('bim_resource_ids.total')
    def _compute_cost(self):
        for rec in self:
            # Solo suma las used
            rec.cost = sum(rec.bim_resource_ids.mapped('total'))

    def _compute_count_activator(self):
        for rec in self:
            rec.count_maintenance_activator = len(rec.maintenance_activator_ids)

    def action_view_maintenance_activator(self):
        action = self.env.ref('base_bim_2.action_maintenance_activator').sudo().read()[0]
        action['domain'] = [('maintenance_task_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_id': self.id,
        }
        return action


    maintenance_sub_task_ids = fields.One2many('maintenance.sub.task', 'maintenance_task_id', 'Sub Task')
    count_maintenance_sub_task = fields.Integer('Quantity Sub Task', compute="_compute_count_sub_task")

    def _compute_count_sub_task(self):
        for rec in self:
            rec.count_maintenance_sub_task = len(rec.maintenance_sub_task_ids)


    def action_view_maintenance_sub_task(self):
        action = self.env.ref('base_bim_2.action_sub_task').sudo().read()[0]
        action['domain'] = [('maintenance_task_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_id': self.id,
        }
        return action

    bim_documentation = fields.One2many('bim.documentation', 'maintenance_task_id', 'Documentation')
    count_bim_documentation = fields.Integer('Quantity Documentation', compute="_compute_count_documentation")

    def _compute_count_documentation(self):
        for rec in self:
            rec.count_bim_documentation = len(rec.bim_documentation)

    def action_view_bim_documentation(self):
        action = self.env.ref('base_bim_2.action_bim_documentation').sudo().read()[0]
        action['domain'] = [('maintenance_task_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_id': self.id,
        }
        return action


    bim_resource_ids = fields.One2many('maintenance.resource', 'maintenance_task_id', 'Resources')
    count_maintenance_resource = fields.Integer('Quantity Resources', compute="_compute_count_resource")

    def _compute_count_resource(self):
        for rec in self:
            rec.count_maintenance_resource = len(rec.bim_resource_ids)

    def action_view_bim_resources(self):
        action = self.env.ref('base_bim_2.action_maintenance_resource').sudo().read()[0]
        action['domain'] = [('maintenance_task_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_task_id': self.id,
        }
        return action

    state = fields.Selection([
            ('draft', 'Draft'),
            ('ots_in_process', 'Ots in Process'),
            ('ots_in_review', 'Ots in Review'),
            ('ots_finished', 'Ots Finished'),
            ], 'State', default='draft', tracking=True)

    run_state = fields.Selection([
            ('stop', 'Stop'),
            ('play', 'Play'),
            ], 'Run State', default='stop', tracking=True)

    partner_id = fields.Many2one('res.partner', string='Responsible', tracking=True)

    who_review_id = fields.Many2one('res.partner', string='Who Review', tracking=True)

    begin_date = fields.Datetime('Begin Date')
    end_date = fields.Datetime('End Date')
    real_duration = fields.Float('Real Duration  (minutes)')
    bim_project_id = fields.Many2one('bim.project', string='Project')
    include_for_bim = fields.Boolean(tracking=True, default=True)

    def action_ots_in_process(self):
        if not self.partner_id:
            raise UserError(_('You must select a contact'))

        if self.maintenance_work_request_id:
            self.maintenance_work_request_id.state = 'ots_in_process'
        self.state = 'ots_in_process'

    def action_ots_in_review(self):
        for sub_task in self.maintenance_sub_task_ids:
            if sub_task.required and sub_task.state != 'done':
                raise UserError(_('You must complete all the required subtasks'))


        if self.maintenance_work_request_id:
            self.maintenance_work_request_id.state = 'ots_in_review'
        self.state = 'ots_in_review'

    def action_ots_finished(self):
        if not self.who_review_id:
            raise UserError(_('You must select a contact'))

        if self.maintenance_work_request_id:
            self.maintenance_work_request_id.state = 'ots_finished'
        self.state = 'ots_finished'

    def to_draft(self):
        if self.maintenance_work_request_id:
            self.maintenance_work_request_id.state = 'draft'
        self.state = 'draft'


    def action_play(self):
        self.run_state = 'play'
        if not self.begin_date:
            self.begin_date = datetime.now()

    def action_stop(self):
        self.run_state = 'stop'
        self.end_date = datetime.now()
        self.real_duration = (self.end_date - self.begin_date).total_seconds() / 60

class MaintenanceActivator(models.Model):
    _description = "Maintenance Activator"
    _name = 'maintenance.activator'
    _order = "id desc"



    maintenance_task_id = fields.Many2one('maintenance.task', string='Task', required=True)
    type = fields.Selection([
            ('date', 'Date'),
            ('each', 'Each'),
            ('when', 'When'),
            ('per_event', 'Per Event'),
            ], 'Type', default='date')


    do_each = fields.Integer('Do Each')
    frequency = fields.Selection([
            ('day', 'Day'),
            ('week', 'Week'),
            ('month', 'Month'),
            ('year', 'Year'),
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
            ('Sunday', 'Sunday'),
            ], 'Frequency', default='month')

    repeat = fields.Integer('Repeat')

    how_many = fields.Selection([
            ('for', 'For'),
            ('forever', 'Forever'),
            ], 'How Many', default='forever')

    until = fields.Date('Until')

    type_of_programming = fields.Selection([
            ('fixed', 'Fixed'),
            ('variable', 'Variable'),
            ], 'Type of Programming', default='fixed')

