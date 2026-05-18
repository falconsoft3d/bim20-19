# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import base64
import io
import xlrd

class MeasurementCapture(models.Model):
    _description = "Measurement Capture"
    _name = 'measurement.capture'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True, readonly=True, copy=False, index=True,
    default=lambda self: self.env['ir.sequence'].next_by_code('measurement.capture'))

    measurement_origin_id = fields.Many2one('measurement.origin', 'Measurement Origin', required=True)
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    date = fields.Datetime(' Date', default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    bim_budget_stage_id = fields.Many2one('bim.budget.stage', 'Stage')
    currency_id = fields.Many2one('res.currency', 'Currency', related='budget_id.currency_id', readonly=True)
    file = fields.Binary('File')
    origin = fields.Char('Origin', help="Origin of the measurement capture, e.g., 'Site visit', 'Client request', etc.")
    description = fields.Text('Comment', help="Additional comments or notes regarding the measurement capture.")
    partner_id = fields.Many2one('res.partner', 'Partner', help="The partner associated with this measurement capture, e.g., the client or contractor.")
    done_date = fields.Date('Date', help="The date when the measurement capture was completed.", default=fields.Date.context_today, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='Status', default='draft', required=True, copy=False, tracking=True)


    lines_ids = fields.One2many('measurement.capture.line', 'measurement_capture_id', 'Lines')
    amount_total = fields.Monetary('Total Amount', compute='_compute_amount_total')
    amount_total_acc = fields.Monetary('Total Amount Acc', compute='_compute_amount_total_acc')

    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', 'Massive Certification by Line')

    @api.depends('lines_ids.amount_acc')
    def _compute_amount_total_acc(self):
        for rec in self:
            rec.amount_total_acc = sum(rec.lines_ids.mapped('amount_acc'))

    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.lines_ids.mapped('amount'))

    def action_clear(self):
        self.lines_ids.unlink()


    def action_to_load(self):
        for line in self.lines_ids:
            qty_last = 0
            last_concept = self.env['measurement.capture.line'].search([
                                    ('concept_id', '=', line.concept_id.id),
                                    ('id', '!=', self.id),
                                ], order='id desc')
            line.qty_last  = sum(last_concept.mapped('qty_accumulated'))
            line.qty_budget = line.concept_id.quantity
            line.price_unit = line.concept_id.sale_price

        self.state = 'loaded'



    def action_import(self):
        if not self.file:
            raise UserError(_('Please select a file to import.'))

        self.lines_ids.unlink()

        file_path = '/tmp/boq_import.xlsx'
        with open(file_path, 'wb') as file:
            file.write(base64.b64decode(self.file))
        workbook = xlrd.open_workbook(file_path)
        sheet = workbook.sheet_by_index(0)

        for row in range(1, sheet.nrows):
            code = sheet.cell_value(row, 0)
            qty = sheet.cell_value(row, 1)

            _logger.info('code: %s, qty: %s', code, qty)

            concept = self.env['bim.concepts'].search([('id_bim', '=', code),
                                                       ('budget_id', '=', self.budget_id.id)], limit=1)

            if concept:
                qty_last = 0
                last_concept = self.env['measurement.capture.line'].search([
                                    ('concept_id', '=', concept.id),
                                    ('id', '!=', self.id),
                                ], order='id desc')
                qty_last  = sum(last_concept.mapped('qty_accumulated'))

                # revisar si ya existe la linea
                line = self.env['measurement.capture.line'].search([
                    ('measurement_capture_id', '=', self.id),
                    ('concept_id', '=', concept.id),
                ], limit=1)

                if not line:
                    self.env['measurement.capture.line'].create({
                        'measurement_capture_id': self.id,
                        'concept_id': concept.id,
                        'qty': qty,
                        'qty_last': qty_last,
                        'price_unit': concept.sale_price,
                        'qty_budget': concept.quantity,
                    })

                else:
                    line.qty += qty

        self.write({'state': 'loaded'})


    def action_load(self):
        concept_ids = self.env['bim.concepts'].search([
                    ('budget_id', '=', self.budget_id.id),
                    ('type', '=', 'departure'),
                    ])
        # Delete all lines
        self.lines_ids.unlink()
        # Create new lines
        for concept in concept_ids:
            last_concept = self.env['measurement.capture.line'].search([
                                ('concept_id', '=', concept.id),
                            ], order='id desc')

            qty_last  = sum(last_concept.mapped('qty'))

            self.env['measurement.capture.line'].create({
                'measurement_capture_id': self.id,
                'concept_id': concept.id,
                'qty_budget': concept.quantity,
                'qty_last': qty_last,
                'price_unit' : concept.sale_price,
            })

        self.write({'state': 'loaded'})

    def action_to_done(self):
        # reviso la cant de origen no sea mayor a la cantidad presupuestada
        for line in self.lines_ids:
            if line.qty_o > line.qty_budget:
                raise ValidationError(_('The origin quantity for concept %s cannot be greater than the budget quantity.') % line.concept_id.name)


        # reviso si hay un closing.expenses con un projecto
        closing_expenses_id = self.env['closing.expenses'].search([
            ('project_ids', 'in', self.project_id.id),
            ('state', '=', 'closed'),
            ('date_closing', '>=', self.done_date),
        ], limit=1)

        if closing_expenses_id:
            raise ValidationError(_('There is a closed closing expenses for this project after the done date of this measurement capture. Please review.'))

        # Valido que al menos haya una linea con cantidad
        if not any(line.qty for line in self.lines_ids):
            raise ValidationError(_('You must enter at least one quantity'))
        self.write({'state': 'done'})


    def action_to_draft(self):
        self.write({'state': 'draft'})


class MeasurementCaptureLine(models.Model):
    _description = "Measurement Capture Line"
    _name = 'measurement.capture.line'
    _order = 'id desc'

    measurement_capture_id = fields.Many2one('measurement.capture', 'Measurement Capture', required=True, ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', related='measurement_capture_id.budget_id', readonly=True)
    concept_id = fields.Many2one('bim.concepts', 'Concept', required=True, help="The concept associated with this measurement capture line.")
    qty_budget = fields.Float('Qty Budget')
    qty_last = fields.Float('Qty Last')
    qty = fields.Float('Qty')
    qty_o = fields.Float('Qty Origin')
    qty_accumulated = fields.Float('Qty Accumulated')
    price_unit = fields.Monetary('Price Unit')
    amount = fields.Monetary('Amount', compute='_compute_amount')
    currency_id = fields.Many2one('res.currency', 'Currency', related='measurement_capture_id.currency_id', readonly=True)
    amount_acc = fields.Monetary('Amount Acc', compute='_compute_amount_acc')

    @api.onchange('qty_o')
    def _onchange_qty_o(self):
        self.qty = self.qty_o - self.qty_last
        self.qty_accumulated = self.qty_last + self.qty


    @api.onchange('qty')
    def _onchange_qty(self):
        self.amount = self.qty * self.price_unit
        self.qty_accumulated = self.qty_last + self.qty


    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.qty * rec.price_unit


    def _compute_amount_acc(self):
        for rec in self:
            rec.amount_acc = rec.qty_accumulated * rec.price_unit
