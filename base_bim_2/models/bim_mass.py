# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimMass(models.Model):
    _description = "Bim Mass"
    _name = 'bim.mass'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code', default='New', required=True, copy=False)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    type = fields.Selection([
        ('apu_total_calc_budget', 'Apu Total Calc - Presupuesto'),
        ('apu_total_calc_departure', 'Apu Total Calc - Partidas'),
    ], string='Type', default='apu_total_calc_budget', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='State', default='draft', required=True, tracking=True)

    def to_done(self):
        for record in self:
            if record.type == 'apu_total_calc_budget':
                bim_budget_ids = self.env['bim.budget'].search([])
                for bim_budget in bim_budget_ids:
                    bim_budget.type_calc_total_apu = 'budget'

            if record.type == 'apu_total_calc_departure':
                bim_budget_ids = self.env['bim.budget'].search([])
                for bim_budget in bim_budget_ids:
                    bim_budget.type_calc_total_apu = 'departures'
            record.state = 'done'

    def to_draft(self):
        for record in self:
            record.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.mass') or 'New'
        return super().create(vals_list)
