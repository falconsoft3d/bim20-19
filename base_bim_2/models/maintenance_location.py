# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceLocation(models.Model):
    _name = 'maintenance.location'
    _description = 'Maintenance Locations'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', copy=False, required=True)
    parent_id = fields.Many2one('maintenance.location', 'Parent Location', index=True)
    partner_id = fields.Many2one('res.partner', 'Partner')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    priority = fields.Selection([
            ('0', 'Very low'),
            ('1', 'Low'),
            ('2', 'Normal'),
            ('3', 'High'),
            ('4', 'Very high'),
            ], 'Priority', default='2')


    maintenance_asset_ids = fields.One2many('maintenance.asset', 'maintenance_location_id', 'Maint Asset')
    count_maintenance_assets = fields.Integer('Quantity Assets', compute="_compute_count_assets")

    def _compute_count_assets(self):
        for rec in self:
            rec.count_maintenance_assets = len(rec.maintenance_asset_ids)


    def action_view_maintenance_assets(self):
        action = self.env.ref('base_bim_2.action_maintenance_asset').sudo().read()[0]
        action['domain'] = [('maintenance_location_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_location_id': self.id,
        }
        return action