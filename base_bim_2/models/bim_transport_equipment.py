# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class BimTransportEquipment(models.Model):
    _description = "Bim Transport Equipment"
    _name = 'bim.transport.equipment'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'description'

    name = fields.Char('Code', default="New", copy=False)
    description = fields.Char('Description')
    driver_id = fields.Many2one('res.partner', string='Driver')
    state = fields.Selection([
        ('ready', 'ready'),
        ('broken', 'Broken'),
        ('maintenance', 'Maintenance'),
        ('not_available', 'Not_available'),], string='Status',
        tracking=True, default='ready', copy=False, index=True)

    brand_id = fields.Many2one('bim.transport.equipment.brand', string='Brand')
    chassis_number = fields.Char('Chassis number')
    plate_number = fields.Char('Plate number')
    kilometers = fields.Float('Kilometers')
    price = fields.Float('Price')
    product_id = fields.Many2one('product.product', string='Product')
    bim_project_id = fields.Many2one('bim.project', string='Project')
    account_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic account')

    earnings = fields.Float('Earnings', compute='_compute_earnings')
    expenses = fields.Float('Expenses', compute='_compute_expenses')
    benefit = fields.Float('Benefit', compute='_compute_benefit')
    rent_state = fields.Selection([('available', 'Available'), ('rented', 'Rented'), ('disable', 'Disable')],
                                  default='available')
    rented_by = fields.Many2one('res.partner')
    model_id = fields.Many2one('bim.transport.equipment.model', string='Model', domain="[('brand_id', '=', brand_id)]")

    @api.onchange('brand_id')
    def _onchange_brand_id(self):
        self.model_id = False

    # tms.expense.record by transportation_expenses_id
    def _compute_earnings(self):
        for record in self:
            earnings = self.env['tms.shipment'].search([('bim_transport_equipment_id', '=', record.id)])
            record.earnings = sum(earnings.mapped('total'))

    def _compute_expenses(self):
        for record in self:
            expenses = self.env['tms.expense.record'].search([('bim_transport_equipment_id', '=', record.id)])
            record.expenses = sum(expenses.mapped('amount'))

    def _compute_benefit(self):
        for record in self:
            record.benefit = record.earnings - record.expenses

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.transport.equipment') or 'New'
        return super().create(vals_list)