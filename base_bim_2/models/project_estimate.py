# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ProjectEstimate(models.Model):
    _description = "Project Estimate"
    _name = 'project.estimate'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True,
    readonly=True, copy=False, index=True,
    default=lambda self: self.env['ir.sequence'].next_by_code('project.estimate'))

    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")

    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    date = fields.Date('Date', default=fields.Datetime.now, readonly=True)
    bim_budget_stage_id = fields.Many2one('bim.budget.stage', 'Stage', ondelete="cascade")

    line_ids = fields.One2many('project.estimate.line', 'project_estimate_id', 'Estimate Lines')

    include_bim = fields.Boolean('Include BIM', default=True)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)

    amount_total = fields.Float('Total Amount')

    type_search = fields.Selection([
        ('100', '<=100'),
        ('all', 'All')
        ],
        string='Type Search', index=True, required=True, default='100', copy=False)

    type = fields.Selection([
        ('labor', 'Labor'),
        ('equip', 'Equipment'),
        ('material', 'Material'),
        ('ALL', 'All'),],
        string='Type', index=True, required=True, default='labor', copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('validated', 'Validated'),
        ('cancel', 'Cancelled'),
        ], string='Status', default='draft', copy=False, tracking=True)


    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        if self.budget_id:
            bim_budget_stage_id = self.env['bim.budget.stage'].search([
                ('budget_id', '=', self.budget_id.id),
                ('state', '=', 'process')
            ], limit=1)

            if bim_budget_stage_id:
                self.bim_budget_stage_id = bim_budget_stage_id.id

    def exe_draft(self):
        for rec in self:
            rec.state = 'draft'


    def exe_validate(self):
        for rec in self:
            amount_total = 0
            for line in rec.line_ids:
                amount_total += line.amount
            rec.amount_total = amount_total

            # delete lines in quantity 0
            for line in rec.line_ids:
                if line.quantity == 0:
                    line.unlink()

            rec.state = 'validated'

    def exe_load_2(self):
        for rec in self:
            rec.state = 'loaded'



    def exe_load(self):
        for rec in self:
            rec.line_ids.unlink()

            concept_ids = self.env['bim.concepts'].search([
                ('budget_id', '=', rec.budget_id.id)], order='code desc')

            for concept in concept_ids:
                if concept.type == rec.type:
                    quantity_acu = 0
                    project_estimate_line_ids = self.env['project.estimate.line'].search([
                        ('concept_id', '=', concept.parent_id.id),
                        ('productc_id', '=', concept.id),
                    ])

                    quantity_acu = sum(project_estimate_line_ids.mapped('quantity'))
                    quantity_budget = concept.quantity * concept.balance

                    print('quantity_budget', quantity_budget)
                    print('quantity_acu', quantity_acu)


                    if rec.type_search == '100':
                        if not quantity_acu >= quantity_budget:
                            self.env['project.estimate.line'].create({
                                                'concept_id': concept.parent_id.id,
                                                'productc_id': concept.id,
                                                'project_estimate_id': rec.id,
                                                'budget_amount': concept.balance * concept.parent_id.quantity,
                                                'quantity_budget': quantity_budget,
                                                'price_unit': concept.amount_fixed,
                                                'quantity_acu': quantity_acu,
                                            })

                    else:
                        self.env['project.estimate.line'].create({
                                            'concept_id': concept.parent_id.id,
                                            'productc_id': concept.id,
                                            'project_estimate_id': rec.id,
                                            'budget_amount': concept.balance * concept.parent_id.quantity,
                                            'quantity_budget': quantity_budget,
                                            'price_unit': concept.amount_fixed,
                                            'quantity_acu': quantity_acu,
                                        })


            rec.state = 'loaded'


class ProjectEstimateLine(models.Model):
    _description = "Project Estimate Line"
    _name = 'project.estimate.line'
    _order = 'id desc'
    _rec_name = 'concept_id'

    project_estimate_id = fields.Many2one('project.estimate', 'Project Estimate', ondelete="cascade")
    concept_id = fields.Many2one('bim.concepts', 'Departure', ondelete="cascade")
    productc_id = fields.Many2one('bim.concepts', 'Resource', ondelete="cascade")
    budget_amount = fields.Float('Budget Amount', required=True, default=0.0)
    quantity_budget= fields.Float('Quantity Budget', required=True, default=0.0)
    quantity_acu = fields.Float('Quantity Acu', required=True, default=0.0)
    quantity = fields.Float('Quantity', required=True, default=0.0)
    price_unit = fields.Float('Unit Price', required=True, default=0.0)
    amount = fields.Float('Amount', required=True, default=0.0, compute='_compute_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    project_id = fields.Many2one('bim.project', 'Project', related='project_estimate_id.project_id', store=True, readonly=True)
    budget_id = fields.Many2one('bim.budget', 'Budget', related='project_estimate_id.budget_id', store=True, readonly=True)
    date = fields.Date('Date', related='project_estimate_id.date', store=True, readonly=True)
    state = fields.Selection(string='Status', related='project_estimate_id.state', store=True, readonly=True)

    company_id = fields.Many2one('res.company', 'Company', related='project_estimate_id.company_id', store=True, readonly=True)



    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.price_unit