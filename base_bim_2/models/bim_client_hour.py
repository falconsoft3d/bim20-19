# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class BimClientHour(models.Model):
    _description = "Bim Client Hour"
    _name = 'bim.client.hour'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _rec_name = 'partner_id'

    name = fields.Char('Name', default="New", required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    price = fields.Float('Price', required=True)
    lines_ids = fields.One2many('bim.client.hour.line', 'bim_client_hour_id', string='Lines')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.client.hour') or 'New'
        return super().create(vals_list)


class BimClientHourLine(models.Model):
    _description = "Bim Client Hour Line"
    _name = 'bim.client.hour.line'

    name = fields.Many2one('hr.employee', required=True)
    price = fields.Float('Price', required=True)
    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')
    bim_client_hour_id = fields.Many2one('bim.client.hour', string='Client Hour')

