# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import xlrd
import base64
from datetime import timedelta

class BiRo(models.Model):
    _description = "Bi Ro"
    _name = 'bi.ro'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)

    bim_budget_id = fields.Many2one('bim.budget', string='Parent Budget')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    currency_id = fields.Many2one('res.currency', string='Currency', related='budget_id.currency_id', readonly=True)
    clear_invoices_ids = fields.Many2many('account.move', copy=False)
    parent_bim_concept_ids = fields.Many2many('bim.concepts', copy=False)
    obj_bim_budget_id = fields.Many2one('bim.budget', string='Obj Budget')

    type = fields.Selection([
        ('phase', 'Phase'),
    ], string='Type', default='phase', required=True)
    line_ids = fields.One2many('bi.ro.line', 'ro_id', string='Lines')


    def parent_check(self):
        self.parent_bim_concept_ids = [(5, 0, 0)]
        bim_concept_ids = self.env['bim.concepts'].search([
                    ('budget_id', '=', self.obj_bim_budget_id.id),
                    ('type', '=', 'departure'),
                    ('sub_phase_id', '=', False),
                    ])

        for concept in bim_concept_ids:
            if concept not in self.parent_bim_concept_ids:
                self.parent_bim_concept_ids = [(4, concept.id)]


    def action_open_invoices(self):
        # Buscamos todas las facturas que las lineas no tinen fases
        account_move_line_ids = self.env['account.move.line'].search([
                            ('concept_phase_id', '=', False),
                        ])

        self.clear_invoices_ids = [(5, 0, 0)]

        for account_move_line_id in account_move_line_ids:
            if account_move_line_id.move_id not in self.clear_invoices_ids:
                if account_move_line_id.move_id.move_type in ['in_invoice', 'in_refund'] and account_move_line_id.product_id:
                    self.clear_invoices_ids = [(4, account_move_line_id.move_id.id)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bi.ro') or 'New'
        return super().create(vals_list)


    def calculate_ro(self):
        _logger.info('calculate_ro')

        # Limpiamos las líneas
        self.line_ids.unlink()


        # bim_budget_id
        bim_concept_ids = self.env['bim.concepts'].search([
                    ('budget_id', '=', self.bim_budget_id.id),
                    ('type', '=', 'departure'),
                    ])

        for concept in bim_concept_ids:
            bi_ro_line_id = self.env['bi.ro.line'].search([
                    ('ro_id', '=', self.id),
                    ('name', '=', concept.sub_phase_id.name),
                    ])

            if not bi_ro_line_id:
                _l = self.env['bi.ro.line'].create({
                    'ro_id': self.id,
                    'name': concept.sub_phase_id.name,
                    'parent_budget': concept.sale_amount,
                    'description': concept.sub_phase_id.description,
                    })


            else:
                bi_ro_line_id.parent_budget += concept.sale_amount

            # Agregamos el concepto a la lista de conceptos
            if not concept in _l.bim_concept_ids:
                _l.bim_concept_ids = [(4, concept.id)]

        # budget_id
        bim_concept_ids = self.env['bim.concepts'].search([
                    ('budget_id', '=', self.budget_id.id),
                    ('type', '=', 'departure'),
                    ])

        for concept in bim_concept_ids:
            bi_ro_line_id = self.env['bi.ro.line'].search([
                    ('ro_id', '=', self.id),
                    ('name', '=', concept.sub_phase_id.name),
                    ])

            if not bi_ro_line_id:
                self.env['bi.ro.line'].create({
                    'ro_id': self.id,
                    'name': concept.sub_phase_id.name,
                    'budget': concept.sale_amount,
                    'forecast': concept.balance,
                    'description': concept.sub_phase_id.description,
                    })
            else:
                bi_ro_line_id.budget += concept.sale_amount
                bi_ro_line_id.forecast += concept.balance


        # buscamos los gastos
        for line in self.line_ids:
            _logger.info('line.name -> : %s', line.name)
            concept_phase_id = self.env['concept.phase'].search([
                       ('name', '=', line.name),
                       ('ro', '=', True),
                     ], limit=1)
            # Buscamos las OC
            if concept_phase_id:
                # buscamos las OC de esta y fase y el prsupuesto 2
                purchase_order_line_ids = self.env['purchase.order.line'].search([
                            ('concept_phase_id', '=', concept_phase_id.id),
                            ('order_id.state', 'in', ['purchase', 'done']),
                            ])

                for purchase_order_line_id in purchase_order_line_ids:
                    line_id = self.env['bi.ro.line'].search([
                            ('ro_id', '=', self.id),
                            ('name', '=', purchase_order_line_id.concept_phase_id.name),
                            ])
                    if line_id:
                        line_id.purchase_order += purchase_order_line_id.price_subtotal
                    else:
                        self.env['bi.ro.line'].create({
                            'ro_id': self.id,
                            'name': purchase_order_line_id.concept_phase_id.name,
                            'purchase_order': purchase_order_line_id.price_subtotal,
                            'description': purchase_order_line_id.concept_phase_id.description,
                            })

            # Buscamos las facturas
            if concept_phase_id:
                # buscamos las facturas de esta y fase y el prsupuesto 2
                account_move_ids = self.env['account.move'].search([
                            ('project_id', '=', self.budget_id.project_id.id),
                            ('state', '=', 'posted'),
                            ('include_for_bim', '=', True),
                            ('move_type', 'in', ['in_invoice', 'in_refund']),
                            ])

                for account_move_id in account_move_ids:
                    for l in account_move_id.line_ids:
                        if l.concept_phase_id.id == concept_phase_id.id:
                            line_id = self.env['bi.ro.line'].search([
                                    ('ro_id', '=', self.id),
                                    ('name', '=', l.concept_phase_id.name),
                                    ])
                            if line_id:
                               if account_move_id.move_type == 'in_invoice':
                                   line_id.expenses += l.price_subtotal
                               else:
                                   line_id.expenses -= l.price_subtotal

                               # Inserto la factura si no está
                               if account_move_id not in line_id.invoices_ids:
                                   line_id.invoices_ids = [(4, account_move_id.id)]

        _logger.info('calculate_ro - END')

class BiRoLine(models.Model):
    _description = "Bi Ro line"
    _name = 'bi.ro.line'

    ro_id = fields.Many2one('bi.ro', string='RO', ondelete='cascade')
    name = fields.Char('Name')
    description = fields.Text('Description')
    parent_budget = fields.Monetary('Parent Budget')
    budget = fields.Monetary('Budget')
    forecast = fields.Monetary('Provision')
    estimated_margin = fields.Monetary('Estimated Margin', compute='_compute_estimated_margin')
    expenses = fields.Monetary('Expenses')
    currency_id = fields.Many2one('res.currency', string='Currency', related='ro_id.budget_id.currency_id', readonly=True)
    invoices_ids = fields.Many2many('account.move', copy=False)
    bim_concept_ids = fields.Many2many('bim.concepts', copy=False)
    purchase_order = fields.Monetary('OC Aprob')
    saldo = fields.Monetary('Saldo OC', compute='_compute_saldo')


    def _compute_estimated_margin(self):
        for rec in self:
            rec.estimated_margin = rec.budget - rec.forecast


    def _compute_saldo(self):
        for rec in self:
            rec.saldo = rec.budget - rec.purchase_order