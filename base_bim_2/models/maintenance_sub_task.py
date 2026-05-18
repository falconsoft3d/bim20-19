# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import requests

class MaintenanceSubTask(models.Model):
    _description = "Maintenance Sub Task"
    _name = 'maintenance.sub.task'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    maintenance_task_id = fields.Many2one('maintenance.task', string='Task')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', tracking=True)
    maintenance_part_id = fields.Many2one('maintenance.part', string='Part')
    type = fields.Selection([
        ('text', 'Text'),
        ('numeric', 'Numeric'),
        ('verify', 'Verify'),
        ('date', 'Date'),
        ('reading', 'Reading'),
        ('gps', 'GPS'),
        ('list', 'List'),
        ('date_time', 'Date Time')
    ], string='Type', required=True, default='text')

    sequence = fields.Integer('Sequence', default=10)

    required = fields.Boolean('Required')
    doc_required = fields.Boolean('Doc Required')


    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='State', default='draft', tracking=True)

    sub_task_text = fields.Text('Sub Task Text')
    sub_task_numeric = fields.Float('Sub Task Numeric')
    sub_task_date = fields.Date('Sub Task Date')
    sub_task_date_time = fields.Datetime('Sub Task Date Time')

    sub_latitude = fields.Float('Latitude', digits=(16, 15))
    sub_longitude = fields.Float('Longitude', digits=(16, 15))


    def get_location(self):
        # Read the location from the device from the GPS
        url = 'http://ip-api.com/json'
        response = requests.get(url)
        data = response.json()
        _logger.info(data)
        self.sub_latitude = data['lat']
        self.sub_longitude = data['lon']

    def to_draft(self):
        self.write({'state': 'draft'})


    def action_ots_in_process(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('maintenance.sub.task') or 'New'
        return super().create(vals_list)
