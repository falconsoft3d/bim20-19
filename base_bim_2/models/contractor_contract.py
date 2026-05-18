# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ContractorContract(models.Model):
    _description = "Contractor Contract"
    _name = 'contractor.contract'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    date_start = fields.Date('Start Date', required=True, default=fields.Date.today)
    date_end = fields.Date('End Date', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    line_ids = fields.One2many('contractor.contract.line', 'contractor_contract_id', string='Lines', copy=True)
    total = fields.Monetary(string='Total', compute='_compute_total', store=True)

    create_purchase = fields.Boolean('Create Purchase Order', default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', copy=False, tracking=True)


    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('contractor.contract') or 'New'
        return super().create(vals_list)

    def to_done(self):
        self.write({'state': 'done'})

    def to_cancel(self):
        self.write({'state': 'cancel'})

    def to_draft(self):
        self.write({'state': 'draft'})

    def to_approved(self):
        self.write({'state': 'approved'})

class ContractorContractLine(models.Model):
    _name = 'contractor.contract.line'
    _description = 'Contractor Contract Line'

    contractor_contract_id = fields.Many2one(comodel_name="contractor.contract", string="Contractor Contract")
    project_id = fields.Many2one(comodel_name="bim.project", string="Project")
    budget_id = fields.Many2one(comodel_name="bim.budget", string="Budget")
    concept_id = fields.Many2one(comodel_name="bim.concepts", string="Concept")
    qty = fields.Float(string="Quantity")
    price_unit = fields.Monetary(string="Unit Price")
    amount = fields.Monetary(string="Amount", compute="_compute_amount", store=True)
    currency_id = fields.Many2one(related='contractor_contract_id.currency_id', store=True)
    acs_date_start = fields.Datetime('Start Date')
    acs_date_end = fields.Datetime('End Date')
    stock_picking_id = fields.Many2one('stock.picking', string='Stock Picking', copy=False)

    @api.depends('qty', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.qty * rec.price_unit


    @api.onchange('concept_id')
    def _onchange_concept_id(self):
        for rec in self:
            rec.price_unit = rec.concept_id.amount_compute
            rec.qty = rec.concept_id.quantity
            rec.acs_date_start = rec.concept_id.acs_date_start
            rec.acs_date_end = rec.concept_id.acs_date_end
            rec.amount = rec.qty * rec.price_unit


    def to_move(self):
        location_id = self.project_id.stock_location_id.id
        if not location_id:
            location_id = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('company_id', '=', self.contractor_contract_id.company_id.id)
            ], limit=1).id

        val = {
            'partner_id': self.contractor_contract_id.partner_id.id,
            'origin': self.contractor_contract_id.name,
            'location_id': location_id,
            'location_dest_id': location_id,
            'picking_type_id': self.env['stock.picking.type'].search([
                                ('code', '=', 'internal'),
                                ('company_id', '=', self.contractor_contract_id.company_id.id)
                            ], limit=1).id,
        }

        _logger.info('val: %s', val)

        stock_picking_id = self.env['stock.picking'].create(val)

        concept_son_ids = self.env['bim.concepts'].search([
            ('parent_id', '=', self.concept_id.id)
        ])

        for mat in concept_son_ids:
            if mat.product_id.type == 'product':

                _logger.info('mat: %s', mat.product_id.name)
                _logger.info('qty: %s', mat.quantity)
                _logger.info('parent qty: %s', mat.parent_id.quantity)

                _vals = {
                    'product_id': mat.product_id.id,
                    'quantity': mat.quantity * mat.parent_id.quantity,
                    'location_id': location_id,
                    'location_dest_id': location_id,
                    'picking_id': stock_picking_id.id,
                }
                _logger.info('_vals Line: %s', _vals)

                stock_picking_line = self.env['stock.move.line'].create(_vals)

        if stock_picking_id:
            self.stock_picking_id = stock_picking_id.id
