# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceResource(models.Model):
    _name = 'maintenance.resource'
    _description = 'Maintenance Resource'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float('Quantity', default=1)
    cost = fields.Monetary('Cost')
    total = fields.Monetary('Total', compute='_compute_total')
    resource_type = fields.Selection(
        [
          ('M', 'Material'),
          ('H', 'Labor'),
          ('Q', 'Equipment'),
         ],
        'Resourse Type', default='M')
    maintenance_task_id = fields.Many2one('maintenance.task', string='Task')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    used = fields.Boolean('Used', default=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
            self.cost = self.product_id.standard_price
            self.name = self.product_id.name

    @api.depends('quantity', 'cost')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.quantity * rec.cost