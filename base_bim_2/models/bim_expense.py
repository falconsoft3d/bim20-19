# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
from math import ceil
from datetime import timedelta
import random
import string

class BimExpense(models.Model):
    _description = "Bim Expense"
    _name = 'bim.expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('required', 'Required'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('deposited', 'Deposited'),
        ('to_cover', 'To Cover'),
        ('finalized', 'Finalized'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft', required=True, copy=False, tracking=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, required=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Solicitante', required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id, required=True, copy=False)
    type = fields.Selection([
        ('surrender', 'Surrender'),
        ('reimbursement', 'Reimbursement'),
    ], string='Type', default='surrender', required=True, copy=False)

    amount_surrender = fields.Monetary('Amount Surrender', copy=False)
    amount_delivered = fields.Monetary('Amount Delivered', copy=False)
    observation = fields.Text('Observation', copy=False)
    date = fields.Datetime('Date', default=fields.Datetime.now, required=True, copy=False)
    approval_date = fields.Datetime('Approval Date', copy=False)
    line_ids = fields.One2many('bim.expense.line', 'bim_expense_id', string='Lines', copy=False)
    include_for_bim = fields.Boolean('Include for Bim', default=True, copy=False)
    saldo = fields.Monetary('Saldo', compute='_compute_saldo')

    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    phase_id = fields.Many2one('concept.phase', string='Phase')

    account_journal_id = fields.Many2one('account.journal', string='Journal', copy=False)

    account_move_id = fields.Many2one('account.move', string='Account Move 1', copy=False)
    account_move2_id = fields.Many2one('account.move', string='Account Move 2', copy=False)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        self.partner_id = self.user_id.partner_id.id

    @api.onchange('line_ids','type')
    def _onchange_line_ids(self):
        if self.type == 'reimbursement':
            self.amount_surrender = sum(self.line_ids.mapped('amount'))


    def _compute_saldo(self):
        for rec in self:
            rec.saldo = rec.amount_delivered - sum(rec.line_ids.mapped('amount'))





    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.expense') or 'New'
        return super().create(vals_list)

    def to_required(self):
        """
        if not self.line_ids and self.type == 'surrender':
            raise UserError(_('You must add at least one line'))
            """

        self.write({'state': 'required'})

    def to_approved(self):
        self.approval_date = fields.Datetime.now()

        if self.amount_delivered == 0:
            self.amount_delivered = self.amount_surrender

        self.write({'state': 'approved'})

    def to_rejected(self):
        self.write({'state': 'rejected'})


    def to_cancel(self):
        self.write({'state': 'cancel'})

    def to_draft(self):
        self.write({'state': 'draft'})

    def to_deposited(self):
        _logger.info('begin - to_deposited')
        if not self.account_journal_id:
            raise UserError(_('You must select a journal'))

        if self.type == 'surrender':
            # buscamos la cuenta de proveedores de la configuracion de la empresa
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'cuenta_gastos_proveedores'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the account of suppliers in the general settings, in the BIM module'))
            else:
                account = self.env['account.account'].search([
                    ('code', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            # buscamos el diario de operaciones varias para el asiento
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'nombre_diario_gastos'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the journal of expenses in the general settings, in the BIM module'))

            else:
                account_journal_id = self.env['account.journal'].search([
                    ('name', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            _logger.info('0- Creamos el asiento')
            # creamos el asiento
            # no valide el balance porque no se si es necesario
            account_move = self.env['account.move'].create({
                'journal_id': self.account_journal_id.id,
                'date': fields.Date.today(),
                'ref': self.name,
                'company_id': self.company_id.id,
                'state': 'draft',
                'project_id': self.project_id.id,
                'partner_id': self.partner_id.id,
                'line_ids': [(0, 0, {
                    'name': self.name,
                    'account_id': self.account_journal_id.default_account_id.id,
                    'debit': 0,
                    'credit': self.amount_delivered,
                    'company_id': self.company_id.id,
                }), (0, 0, {
                    'name': self.name,

                    'account_id': account.id,
                    'debit': self.amount_delivered,
                    'credit': 0,
                    'company_id': self.company_id.id,
                })]

            })

            _logger.info('1- account_move %s' % account_move)

            account_move.action_post()
            self.account_move_id = account_move.id
            self.write({'state': 'to_cover'})
        else:
            # buscamos la cuenta de entregas por rendir
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'cuenta_gastos_rendir'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the account of expenses to be rendered in the general settings, in the BIM module'))
            else:
                account = self.env['account.account'].search([
                    ('code', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            # buscamos el diario de operaciones varias para el asiento
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'nombre_diario_gastos'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the journal of expenses in the general settings, in the BIM module'))

            else:
                account_journal_id = self.env['account.journal'].search([
                    ('name', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            _logger.info('0- Creamos el asiento')
            # creamos el asiento
            # no valide el balance porque no se si es necesario
            account_move = self.env['account.move'].create({
                'journal_id': self.account_journal_id.id,
                'date': fields.Date.today(),
                'ref': self.name,
                'company_id': self.company_id.id,
                'state': 'draft',
                'project_id': self.project_id.id,
                'partner_id': self.partner_id.id,
                'line_ids': [(0, 0, {
                    'name': self.name,
                    'account_id': self.account_journal_id.default_account_id.id,
                    'debit': 0,
                    'credit': self.amount_delivered,
                    'company_id': self.company_id.id,
                }), (0, 0, {
                    'name': self.name,

                    'account_id': account.id,
                    'debit': self.amount_delivered,
                    'credit': 0,
                    'company_id': self.company_id.id,
                })]

            })

            _logger.info('1- account_move %s' % account_move)

            account_move.action_post()
            self.account_move_id = account_move.id
            self.write({'state': 'deposited'})


        _logger.info('end - to_deposited')
        # self.write({'state': 'deposited'})

    def to_finish(self):
        if self.type == 'reimbursement':
            # buscamos la cuenta de proveedores de la configuracion de la empresa
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'cuenta_gastos_proveedores'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the account of suppliers in the general settings, in the BIM module'))
            else:
                account = self.env['account.account'].search([
                    ('code', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            # buscamos el diario de operaciones varias para el asiento
            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'nombre_diario_gastos'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the journal of expenses in the general settings, in the BIM module'))


            else:
                account_journal_id = self.env['account.journal'].search([
                    ('name', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            bim_general_config_id = self.env['bim.general.config'].search([
                ('company_id', '=', self.company_id.id),
                ('key', '=', 'cuenta_gastos_rendir'),
            ], order='id desc', limit=1)

            if not bim_general_config_id:
                raise UserError(_('You must configure the account of expenses to be rendered in the general settings, in the BIM module'))

            account_r = self.env['account.account'].search([
                    ('code', '=', bim_general_config_id.value),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            _logger.info('0- Creamos el asiento')
            # creamos el asiento
            # no valide el balance porque no se si es necesario
            account_move = self.env['account.move'].create({
                'journal_id': self.account_journal_id.id,
                'date': fields.Date.today(),
                'ref': self.name,
                'company_id': self.company_id.id,
                'state': 'draft',
                'project_id': self.project_id.id,
                'partner_id': self.partner_id.id,
                'line_ids': [(0, 0, {
                    'name': self.name,
                    'account_id': account_r.id,
                    'debit': 0,
                    'credit': self.saldo,
                    'company_id': self.company_id.id,
                }), (0, 0, {
                    'name': self.name,
                    'account_id': account.id,
                    'debit': self.saldo,
                    'credit': 0,
                    'company_id': self.company_id.id,
                })]

            })

            _logger.info('1- account_move %s' % account_move)

            account_move.action_post()
            self.account_move2_id = account_move.id
            self.write({'state': 'finalized'})
        else:
            self.write({'state': 'finalized'})

    def to_cover(self):
        self.write({'state': 'to_cover'})

    def to_draft(self):
        self.write({'state': 'draft'})

    def delete_invoices(self):
        for line in self.line_ids:
            if line.invoice_id and line.invoice_id.state == 'draft':
                line.invoice_id.unlink()


    def create_invoices(self):
        _logger.info('begin - create_invoices')
        if not self.line_ids:
            raise UserError(_('You must add at least one line'))

        for line in self.line_ids:
            analytic_id = line.project_id.analytic_id.id
            invoice_id = line.invoice_id

            if not invoice_id and not line.storable:
                partner_id = line.partner_id

                invoice = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'partner_id': partner_id.id,
                    'invoice_date': line.date,
                    'currency_id': line.currency_id.id,
                    'include_for_bim': True,
                    'bim_expense_id': self.id,
                    'project_id': line.project_id.id,
                })

                product_id = self.env['product.product'].search([
                        ('type', '=', 'service'),
                        ('name', '=', 'GASTOS'),
                ], limit=1)

                if not product_id:
                    product_id = self.env['product.product'].create({
                        'name': 'GASTOS',
                        'type': 'service',
                        'list_price': 0,
                    })


                vals = {
                         'name': line.name,
                         'sequence': 1,
                         'account_id': product_id.property_account_expense_id.id or product_id.categ_id.property_account_expense_categ_id.id,
                         'price_unit': line.amount,
                         'quantity': 1,
                         'product_uom_id': product_id.uom_id.id,
                         'product_id': product_id.id,
                         'tax_ids': [(6, 0, product_id.taxes_id.ids)],
                         'project_id': line.project_id.id,
                         'company_id': self.company_id.id,
                     }
                analytic_id = line.project_id.analytic_id.id

                _logger.info('analytic_id %s' % analytic_id)

                if analytic_id:
                    vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })

                _logger.info('vals %s' % vals)

                invoice.write({'invoice_line_ids': [(0, 0, vals)]})

                line.invoice_id = invoice.id

        _logger.info('end - create_invoices')


class BimExpenseLine(models.Model):
    _description = "Bim Expense Line"
    _name = 'bim.expense.line'
    _order = 'id desc'

    bim_expense_id = fields.Many2one('bim.expense', string='Expense', required=True)
    name = fields.Char('Description', required=True)
    partner_id = fields.Many2one('res.partner', string='Contacto')
    invoice_number = fields.Char('Invoice Number', required=True)
    date = fields.Date('Date', required=True)
    amount = fields.Monetary('Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='bim_expense_id.currency_id', store=True, readonly=True)
    file = fields.Binary('File')
    file_name = fields.Char('File Name')
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    phase_id = fields.Many2one('concept.phase', string='Phase')
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    storable = fields.Boolean('Storable', default=False)
    invoice_id = fields.Many2one('account.move', string='Invoice')

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.project_id = self.bim_expense_id.project_id.id
            self.phase_id = self.bim_expense_id.phase_id.id
            self.budget_id = self.bim_expense_id.budget_id.id