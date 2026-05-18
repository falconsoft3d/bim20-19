# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class ContractorContractAnalysis(models.Model):
    _description = "Contractor Contract Analysis"
    _name = 'contractor.contract.analysis'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    project_ids = fields.Many2many('bim.project', string='Projects')
    budget_ids = fields.Many2many('bim.budget', string='Budgets')
    line_ids = fields.One2many('contractor.contract.analysis.line', 'contractor_contract_analysis_id', string='Lines', copy=True)
    date = fields.Datetime('Create Date', default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='Status', default='draft', copy=False, tracking=True)

    @api.onchange('project_ids')
    def _onchange_project_ids(self):
        for rec in self:
            if rec.project_ids:
                budget_ids = self.env['bim.budget'].search([('project_id', 'in', rec.project_ids.ids)])
                rec.budget_ids = budget_ids.ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('contractor.contract.analysis') or 'New'
        return super().create(vals_list)


    def ex_search(self):
        self.line_ids.unlink()

        if self.budget_ids:
            budget_ids = self.env['bim.budget'].search([('id', '=', self.budget_ids.ids)])

        concept_ids = self.env['bim.concepts'].search([
            ('budget_id', 'in', budget_ids.ids),
            ('type', '=', 'departure'),
        ])

        if concept_ids:
            for concept_id in concept_ids:
                contractor_contract_progress_capture_line_ids = self.env['contractor.contract.progress.capture.line'].search([
                        ('concept_id', '=', concept_id.id),
                ])

                _logger.info(">> contractor_contract_progress_capture_line_ids: %s" % contractor_contract_progress_capture_line_ids)

                amount_r = 0
                for l in contractor_contract_progress_capture_line_ids:
                    amount_r += l.amount


                real_date = fields.Datetime.now()

                if contractor_contract_progress_capture_line_ids:
                    last_contractor_contract_progress_capture_line_id = contractor_contract_progress_capture_line_ids[-1]
                    if last_contractor_contract_progress_capture_line_id:
                        real_date = last_contractor_contract_progress_capture_line_id.progress_capture.date
                    qty_accumulated = sum(contractor_contract_progress_capture_line_ids.mapped('qty'))
                else:
                    qty_accumulated = 0

                if concept_id.acs_date_end:
                    acs_date_end = concept_id.acs_date_end
                else:
                    acs_date_end =  concept_id.acs_date_start

                if qty_accumulated == 0 and real_date < acs_date_end:
                    status = 'on_time'
                elif qty_accumulated == 0 and real_date > acs_date_end:
                    status = 'late'
                elif qty_accumulated > 0 and real_date < acs_date_end:
                    status = 'on_time'
                elif qty_accumulated > 0 and real_date > acs_date_end:
                    status = 'late'

                self.env['contractor.contract.analysis.line'].create({
                    'contractor_contract_analysis_id': self.id,
                    'project_id': concept_id.budget_id.project_id.id,
                    'budget_id': concept_id.budget_id.id,
                    'concept_id': concept_id.id,
                    'qty': concept_id.quantity,
                    'price_unit': concept_id.amount_compute,
                    'amount': concept_id.quantity * concept_id.amount_compute,
                    'acs_date_start' : concept_id.acs_date_start,
                    'acs_date_end' : concept_id.acs_date_end,
                    'qty_accumulated': qty_accumulated,
                    'qty_pending': concept_id.quantity - qty_accumulated,
                    'real_date': real_date,
                    'amount_r': amount_r,
                    'status': status,
                })



class ContractorContractAnalysisLine(models.Model):
    _name = 'contractor.contract.analysis.line'
    _description = 'Contractor Contract Analysis Line'

    contractor_contract_analysis_id = fields.Many2one(comodel_name="contractor.contract.analysis", string="Contractor Contract Analysis")
    project_id = fields.Many2one(comodel_name="bim.project", string="Project")
    budget_id = fields.Many2one(comodel_name="bim.budget", string="Budget")
    concept_id = fields.Many2one(comodel_name="bim.concepts", string="Concept")
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")

    qty = fields.Float(string="Quantity")
    qty_accumulated = fields.Float(string="Qty Accumulated")
    qty_pending = fields.Float(string="Qty Pending")

    price_unit = fields.Monetary(string="Unit Price")
    amount = fields.Monetary(string="Amount")
    amount_r = fields.Monetary(string="Real Amount")
    currency_id = fields.Many2one(related='contractor_contract_analysis_id.currency_id', store=True)
    acs_date_start = fields.Datetime('Start Date')
    acs_date_end = fields.Datetime('End Date')
    real_date = fields.Datetime('Real Date')
    status = fields.Selection([
        ('on_time', 'On Time'),
        ('advanced', 'Advanced'),
        ('late', 'Late'),
    ], string='Status', default='on_time', copy=False)