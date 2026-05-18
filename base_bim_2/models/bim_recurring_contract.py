# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)


class BimRecurringContract(models.Model):
    _name = 'bim.recurring.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Recurring Contract'
    _order = 'id desc'

    name = fields.Char("Code", required=True, default='New', copy=False)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    contact_ids = fields.Many2many('res.partner', string='Contacts')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    date_start = fields.Date(string='Begin Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    bim_project_id = fields.Many2one('bim.project', string='Project')
    desc = fields.Text(string='Description')
    state = fields.Selection([('draft', 'Draft'),
                              ('confirmed', 'Confirmed'),
                              ('finished', 'Finished'),
                              ('cancel', 'Cancelled')], string='State', default='draft', tracking=True)

    time_unit = fields.Selection([('day', 'Day'),
                                  ('week', 'Week'),
                                  ('month', 'Month'),
                                  ('year', 'Year')], string='Time Unit', default='month')

    active = fields.Boolean(string='Active', default=True)

    frequency = fields.Integer(string='Frequency', default=1)
    day_invoice = fields.Integer(string='Day Invoice', default=1)
    amount = fields.Float(string='Amount')
    state_invoice = fields.Selection([('draft', 'Draft'),
                                      ('open', 'Open'),
                                      ('email', 'Email')], string='State Invoice', default='draft')

    invoice_ids = fields.One2many('account.move', 'bim_recurring_contract_id', 'Invoices')
    invoice_count = fields.Integer('Quantity Invoices', compute="_compute_invoice")


    @api.depends('invoice_ids')
    def _compute_invoice(self):
        for contract in self:
            invoices = contract.invoice_ids
            out_invoices = invoices.filtered(lambda i: i.state != 'cancel' and i.move_type == 'out_invoice')
            contract.invoice_count = len(out_invoices)

    def action_view_invoice(self):
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        action['domain'] = [('bim_recurring_contract_id', '=', self.id)]
        action['context'] = {'default_bim_recurring_contract_id': self.id}
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.recurring.contract') or 'New'
        return super().create(vals_list)


    # Onchange partner_id
    @api.onchange('sale_order_id')
    def onchange_sale_order_id(self):
        if self.sale_order_id:
            self.amount = self.sale_order_id.amount_total


    def action_confirm(self):
        self.write({'state': 'confirmed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_finish(self):
        self.write({'state': 'finished'})
        return True


    def action_draft(self):
        self.write({'state': 'draft'})
        return True

    def cron_run_contract(self):
        contracts = self.search([('state', '=', 'confirmed')])
        for contract in contracts:
            contract.action_execute()

    def action_execute(self):
        # Comprobamos que no este vencido el contrato.
        if self.date_end and self.date_end < fields.Date.today():
            self.action_finish()
            return False

        # Comprobando si se debe generar una factura basado en la frecuencia
        if self._should_generate_invoice():
            invoice_vals = self._prepare_invoice_values()
            invoice = self.env['account.move'].create(invoice_vals)

            if self.state_invoice == 'open':
                invoice.action_post()

            return invoice
        else:
            # Si no es momento de generar una factura, puedes registrar esto o simplemente no hacer nada
            _logger.info("No es momento de generar una factura para el contrato: %s", self.name)
            return False

    def _should_generate_invoice(self):
        # si la frecuencia es 1
        # y time unit es month
        # y day_invoice es igual al dia de hoy
        # y no existe una factura para este contrato en el dia de hoy
        # entonces se debe generar una factura
        if self.frequency == 1 and self.time_unit == 'month' and self.day_invoice == fields.Date.today().day and not self.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.move_type == 'out_invoice'):
            return True

        # si la frecuencia es diferente de 1
        # y time unit es month
        # y day_invoice es igual al dia de hoy
        # y no existe una factura para este contrato para ese rango de fechas
        # entonces se debe generar una factura
        print(fields.Date.today().day)
        if self.frequency != 1 and self.time_unit == 'month' and self.day_invoice == fields.Date.today().day and not self.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.move_type == 'out_invoice' and i.invoice_date >= fields.Date.today() - relativedelta(months=self.frequency) and i.invoice_date <= fields.Date.today()):
            return True

        return False

    def _prepare_invoice_values(self):
        # Asegurarse de que hay una orden de venta asociada
        if not self.sale_order_id:
            raise UserError(_('No hay una orden de venta asociada con este contrato.'))

        invoice_lines = []
        for line in self.sale_order_id.order_line:
            invoice_line_vals = {
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
            }
            analytic_id = self.bim_project_id.analytic_id.id if self.bim_project_id.analytic_id else False
            if analytic_id:
                    invoice_line_vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })

            invoice_lines.append((0, 0, invoice_line_vals))

        return {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',  # Tipo de factura de cliente
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'bim_recurring_contract_id' : self.id,
            'include_for_bim' : True,
            'project_id' : self.bim_project_id.id,
            'company_id': self.company_id.id,
            # Puedes agregar más campos aquí según sea necesario
        }