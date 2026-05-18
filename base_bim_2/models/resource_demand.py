# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import base64
import io

class ResourceDemand(models.Model):
    _description = "Resource Demand"
    _name = 'resource.demand'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    quantity_demanded = fields.Float(string='Quantity Demanded', default=1)
    bim_project_ids = fields.Many2many('bim.project', string='Projects')
    resource_origin = fields.Selection([
        ('internal', 'Internal'),
        ('external', 'External')
    ], string='Origin', default='internal')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('resource.demand') or 'New'
        return super().create(vals_list)