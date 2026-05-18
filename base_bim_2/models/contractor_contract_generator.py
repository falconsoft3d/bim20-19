# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ContractorContractGenerator(models.Model):
    _description = "Contractor Contract Generator"
    _name = 'contractor.contract.generator'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    project_id = fields.Many2one(comodel_name="bim.project", string="Project")
    budget_id = fields.Many2one(comodel_name="bim.budget", string="Budget")

    date = fields.Date('Date', required=True, default=fields.Date.today)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('contractor.contract.generator.line', 'contractor_contract_generator_id', string='Lines', copy=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', copy=False, tracking=True)

    def to_load(self):
        self.line_ids.unlink()
        for line in self.budget_id.concept_ids:
            if line.type == 'departure':
                self.env['contractor.contract.generator.line'].create({
                    'contractor_contract_generator_id': self.id,
                    'concept_id': line.id,
                    'qty': line.quantity,
                    'price_unit': line.amount_compute,
                })

        self.write({'state': 'loaded'})

    def to_done(self):
        # Reviso si no tengo lineas tiene partner_id
        check_lines = self.line_ids.filtered(lambda x: not x.partner_id)
        if check_lines:
            raise UserError('You must select a contractor for each line')

        lines_agrupadas = {}
        for line in self.line_ids:
            if line.partner_id:
                contractor_contract_id = self.env['contractor.contract'].search([
                    ('partner_id', '=', line.partner_id.id),
                    ('state', '=', 'draft')
                ], limit=1)

                if not contractor_contract_id:
                    contractor_contract_id = self.env['contractor.contract'].create({
                        'date_start': self.date,
                        'date_end': self.date,
                        'company_id': self.company_id.id,
                        'user_id': self.user_id.id,
                        'partner_id': line.partner_id.id,
                    })

                line.contractor_contract_id = contractor_contract_id.id




                contractor_contract_id.line_ids.create({
                    'project_id': self.project_id.id,
                    'budget_id': self.budget_id.id,
                    'concept_id': line.concept_id.id,
                    'qty': line.qty,
                    'price_unit': line.price_unit,
                    'acs_date_start' : line.concept_id.acs_date_start,
                    'acs_date_end' :  line.concept_id.acs_date_end,
                    'contractor_contract_id': contractor_contract_id.id,
                })

        self.write({'state': 'done'})

    def to_cancel(self):
        self.write({'state': 'cancel'})

    def to_draft(self):
        self.write({'state': 'draft'})

    def to_approved(self):
        self.write({'state': 'approved'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('contractor.contract.generator') or 'New'
        return super().create(vals_list)


class ContractorContractLine(models.Model):
    _name = 'contractor.contract.generator.line'
    _description = 'Contractor Contract Generator Line'

    contractor_contract_generator_id = fields.Many2one(comodel_name="contractor.contract.generator", string="Contractor Contract Generator")
    concept_id = fields.Many2one(comodel_name="bim.concepts", string="Concept")
    partner_id = fields.Many2one('res.partner', string='Sub Contractor')
    qty = fields.Float(string="Quantity")
    price_unit = fields.Monetary(string="Unit Price")
    amount = fields.Monetary(string="Amount", compute="_compute_amount", store=True)
    currency_id = fields.Many2one(related='contractor_contract_generator_id.currency_id', store=True)
    contractor_contract_id = fields.Many2one(comodel_name="contractor.contract", string="Contractor Contract", copy=False)

    @api.depends('qty', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.qty * rec.price_unit


    @api.onchange('concept_id')
    def _onchange_concept_id(self):
        for rec in self:
            rec.price_unit = rec.concept_id.amount_compute
            rec.qty = rec.concept_id.quantity
            rec.amount = rec.qty * rec.price_unit