# -*- coding: utf-8 -*-
# Part of Marlon Falcon Hernandez. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class BimCashFlow(models.Model):
    _description = "Bim Cash Flow"
    _name = 'bim.cash.flow'
    _order = "id desc"

    name = fields.Char('Code', default='New')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    budgeted = fields.Monetary(string="Budgeted")
    real = fields.Monetary(string="Real")
    real_signed = fields.Monetary(string="Real Signed",  compute='_compute_real_signed', store=True)
    budgeted_signed = fields.Monetary(string="Budgeted Signed ", compute='_compute_budgeted_signed', store=True)

    payments_ids = fields.Many2many('account.payment', string="Payments")
    type = fields.Selection([
                                ('income', 'Income'),
                                ('expense', 'Expense')], string="Type", default='expense')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id, required=True)

    bim_project_id = fields.Many2one('bim.project', string="Project")
    bim_budget_id = fields.Many2one('bim.budget', string="Budget")
    bim_concept_id = fields.Many2one('bim.concepts', string="Concept")

    bim_budget_stage_id = fields.Many2one('bim.budget.stage', string="Stage")
    contact_id = fields.Many2one('res.partner', string="Contact")

    note = fields.Char(string="Note")
    variation = fields.Monetary(string="Variation", compute='_compute_variation', store=True)
    variation_signed = fields.Monetary(string="Variation Signed", compute='_compute_variation_signed', store=True)
    journal_id = fields.Many2one('account.journal', string="Journal")

    bim_cash_flow_generator_id = fields.Many2one('bim.cash.flow.generator', string="Generator")
    real_state_sale_order_id = fields.Many2one('real.estate.sale.order', string="Sale Order")
    date = fields.Date(string="Date")
    bim_cash_flow_category_id = fields.Many2one('bim.cash.flow.category', string="Category")

    @api.depends('budgeted', 'real')
    def _compute_variation(self):
        for rec in self:
            rec.variation = rec.real - rec.budgeted

    @api.depends('budgeted', 'type','real')
    def _compute_variation_signed(self):
        for rec in self:
            if rec.real > 0 and rec.budgeted > 0:
                variation = abs(rec.real - rec.budgeted)
                rec.variation_signed = variation * -1 if rec.type == 'expense' else rec.variation
            else:
                rec.variation_signed = 0

    @api.onchange('payments_ids')
    def _onchange_payments_ids(self):
        self.real = sum(self.payments_ids.mapped('amount'))


    @api.depends('real', 'type')
    def _compute_real_signed(self):
        for rec in self:
            rec.real_signed = rec.real * -1 if rec.type == 'expense' else rec.real

    @api.depends('budgeted', 'type')
    def _compute_budgeted_signed(self):
        for rec in self:
            rec.budgeted_signed = rec.budgeted * -1 if rec.type == 'expense' else rec.budgeted

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.cash.flow') or 'New'
        return super().create(vals_list)