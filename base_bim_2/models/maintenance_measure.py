# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceMeasure(models.Model):
    _name = 'maintenance.measure'
    _description = 'Maintenance Measure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    maintenance_asset_id = fields.Many2one('maintenance.asset', string='Asset', required=True)
    date = fields.Datetime('Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    note = fields.Text('Note')
    value = fields.Float('Value', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='Status', default='draft', copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.measure') or 'New'
        return super().create(vals_list)

    def action_to_done(self):
        self.write({'state': 'done'})

    def to_draft(self):
        self.write({'state': 'draft'})