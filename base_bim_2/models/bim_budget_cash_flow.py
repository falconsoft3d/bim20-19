import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class BimBudgetCashFlow(models.Model):
    _name = 'bim.budget.cash.flow'
    _description = 'Budgets Cash Flow'

    budget_id = fields.Many2one('bim.budget', string='Budget', ondelete='cascade')
    project_id = fields.Many2one('bim.project', string='Project', related='budget_id.project_id', store=True)
    stage_id = fields.Many2one('bim.budget.stage', string='Stage', ondelete='restrict')
    flow_position = fields.Selection([
        ('start', 'Start'),('middle', 'Middle'),
        ('end', 'End')], string='Generate precedents',
         required=True, default='middle')
    egress = fields.Float(string='Egress', digits='BIM price')
    payment_state = fields.Float(string='Payment State', compute='_compute_payment_state', store=True, digits='BIM price')
    advance = fields.Float(string='Advance', digits='BIM price')
    retention = fields.Float(string='Retention', compute='_compute_retention', store=True, digits='BIM price')
    incomes = fields.Float(string='Incomes', compute='_compute_incomes', store=True, digits='BIM price')
    partial_cash_flow = fields.Float(string='Partial CF', compute='_compute_partial_cash_flow', store=True, digits='BIM price')
    accumulated = fields.Float(string='Accumulated CF', digits='BIM price')
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id')
    description = fields.Char(string='Description', compute='_compute_description', store=True)

    @api.depends('flow_position')
    def _compute_description(self):
        for flow in self:
            descritpion = _("Start ")
            if flow.flow_position == 'middle':
                descritpion = flow.stage_id.name
            elif flow.flow_position == 'end':
                descritpion = _("End")
            flow.description = descritpion

    @api.depends('egress','budget_id','budget_id.certification_factor')
    def _compute_payment_state(self):
        for flow in self:
            flow.payment_state = flow.egress * flow.budget_id.certification_factor

    @api.depends('payment_state', 'budget_id', 'budget_id.retention')
    def _compute_retention(self):
        for flow in self:
            if flow.flow_position != 'end':
                flow.retention = flow.payment_state * flow.budget_id.retention/100
            else:
                flow.retention = sum(cash.retention for cash in flow.budget_id.cas_flow_ids.filtered_domain([('flow_position','!=','end')]))

    @api.depends('payment_state', 'retention', 'advance')
    def _compute_incomes(self):
        for flow in self:
            incomes = flow.advance
            if flow.flow_position == 'middle':
                incomes = flow.payment_state - flow.advance - flow.retention
            elif flow.flow_position == 'end':
                incomes = flow.advance + flow.retention
            flow.incomes = incomes

    @api.depends('egress', 'incomes')
    def _compute_partial_cash_flow(self):
        for flow in self:
            flow.partial_cash_flow = flow.incomes - flow.egress

