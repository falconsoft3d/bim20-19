# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class CrmLead(models.Model):
    _inherit = 'crm.lead'
    bim_order_ids = fields.One2many('bim.project', 'opportunity_id', string='Projects')
    bim_order_amount_total = fields.Monetary(compute='_compute_project_data', string="Sum of Orders",
                                        help="Untaxed Total of Confirmed Orders", currency_field='company_currency')
    bim_quotation_count = fields.Integer(string="Number of Sale Orders", compute='_compute_project_data',)

    budget_sample_count = fields.Integer(string="Number of Budget Samples", compute='_compute_budget_sample_data', store=True)
    budget_sample_ids = fields.One2many('bim.budget.sample', 'opportunity_id', string='Budget Samples')

    budget_request_ids = fields.One2many('budget.request', 'opportunity_id', string='Budget Requests')
    budget_request_count = fields.Integer(string="Number of Budget Requests", compute='_compute_budget_request_data', store=True)

    budget_ids = fields.One2many('bim.budget', 'opportunity_id', string='Bim Budget')
    budget_count = fields.Integer(string="Number of Bim Budget", compute='_compute_bim_budget')

    main_project_id = fields.Many2one('bim.project', string='Main Project', copy=False, compute='compute_main_project_id')


    def _compute_bim_budget(self):
        for record in self:
            record.budget_count = len(record.budget_ids)


    def action_view_bim_budget(self):
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        action['context'] = {
            'default_opportunity_id': self.id,
            'default_contact_id': self.partner_id.id,
            'default_name': self.name,
            'default_currency_id': self.company_currency.id,
            'default_project_id': self.main_project_id.id,
        }
        budgets = self.mapped('budget_ids')
        action['domain'] = [('id', 'in', budgets.ids)]
        return action

    def compute_main_project_id(self):
        for record in self:
            if record.bim_order_ids:
                if len(record.bim_order_ids) > 0:
                    record.main_project_id = record.bim_order_ids[0].id
                else:
                    record.main_project_id = False
            else:
                record.main_project_id = False


    @api.depends('budget_request_ids')
    def _compute_budget_request_data(self):
        for record in self:
            record.budget_request_count = len(record.budget_request_ids)

    def action_view_budget_request(self):
        action = self.env.ref('base_bim_2.budget_request_action').sudo().read()[0]
        action['context'] = {
            'default_opportunity_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_description': self.name,
        }
        budgets = self.mapped('budget_request_ids')
        action['domain'] = [('id', 'in', budgets.ids)]
        return action


    @api.depends('budget_sample_ids')
    def _compute_budget_sample_data(self):
        for record in self:
            record.budget_sample_count = len(record.budget_sample_ids)

    def action_view_bim_project(self):
        action = self.env.ref('base_bim_2.action_bim_proect').sudo().read()[0]
        action['context'] = {
            'search_default_state': 1,
            'search_default_partner_id': self.partner_id.id,
            'default_customer_id': self.partner_id.id,
            'default_nombre': self.name,
            'default_user_id': self.user_id.id,
            'default_opportunity_id': self.id
        }
        action['domain'] = [('opportunity_id', '=', self.id)]
        quotations = self.mapped('bim_order_ids')
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('base_bim_2.view_form_bim_project').id, 'form')]
            action['res_id'] = quotations.id
        return action


    def action_view_budget_sample(self):
        action = self.env.ref('bim_crm.action_bim_budget_sample').sudo().read()[0]
        action['context'] = {
            'default_opportunity_id': self.id,
            'default_partner_id': self.partner_id.id,
        }
        budgets = self.mapped('budget_sample_ids')
        action['domain'] = [('id', 'in', budgets.ids)]
        return action

    @api.depends('bim_order_ids.state_id', 'bim_order_ids.currency_id', 'bim_order_ids.company_id')
    def _compute_project_data(self):
        for lead in self:
            total = 0.0
            quotation_cnt = 0
            company_currency = lead.company_currency or self.env.company.currency_id
            for order in lead.bim_order_ids:
                quotation_cnt += 1
                total += order.currency_id._convert(
                    order.balance, company_currency, order.company_id,
                    order.date_ini or fields.Date.today())
            lead.bim_order_amount_total = total
            lead.bim_quotation_count = quotation_cnt

    @api.constrains('stage_id')
    def _onchange_bim_stage_id(self):
        for record in self:
            if record.stage_id.bim_project_state_id:
                bim_project_ids = self.env['bim.project'].search([('opportunity_id', '=', record.id)])
                if bim_project_ids:
                    for project in bim_project_ids:
                        project.state_id = record.stage_id.bim_project_state_id.id
                        print('project.state_id', project.state_id.name)

