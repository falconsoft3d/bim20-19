# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class MaintenanceWorkRequest(models.Model):
    _description = "Maintenance Work Request"
    _name = 'maintenance.work.request'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    maintenance_task_id = fields.Many2one('maintenance.task', string='Work Order')
    date = fields.Datetime('Date', default=fields.Datetime.now)
    priority = fields.Selection([
            ('0', 'Very low'),
            ('1', 'Low'),
            ('2', 'Normal'),
            ('3', 'High'),
            ('4', 'Very high'),
            ], 'Priority', default='2')
    description = fields.Char('Description')
    observation = fields.Text('Observation')

    state = fields.Selection([
            ('draft', 'Draft'),
            ('ots_in_process', 'Ots in Process'),
            ('ots_in_review', 'Ots in Review'),
            ('ots_finished', 'Ots Finished'),
            ], 'State', default='draft', tracking=True)

    maintenance_asset_id = fields.Many2one('maintenance.asset', string='Asset')

    requested_by = fields.Char('Requested By')
    requested_email = fields.Char('Requested Email')
    reference = fields.Char('Reference')
    requested_phone = fields.Char('Requested Phone')

    maintenance_location_id = fields.Many2one('maintenance.location', string='Location')

    maintenance_part_id = fields.Many2one('maintenance.part', string='Part')
    maintenance_category_1 = fields.Many2one('maintenance.category', string='Category 1')
    maintenance_category_2 = fields.Many2one('maintenance.category', string='Category 2')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Partner')


    def create_work_order(self):
        self.ensure_one()
        if not self.maintenance_task_id:
            maintenance_type_task_id = self.env['maintenance.type.task'].search([], limit=1)

            self.maintenance_task_id = self.env['maintenance.task'].create({
                'maintenance_work_request_id': self.id,
                'maintenance_asset_id': self.maintenance_asset_id.id,
                'maintenance_category_1': self.maintenance_category_1.id,
                'maintenance_category_2': self.maintenance_category_2.id,
                'priority': self.priority,
                'maintenance_type_task_id': maintenance_type_task_id.id,
                'name': self.description,
                'note': self.observation,
            })

        else:
            raise UserError(_('Work Order already created'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.work.request') or 'New'
        return super().create(vals_list)