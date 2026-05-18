# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date

class TmsExpenseRecord(models.Model):
    _description = "Tms Expense Record"
    _name = 'tms.expense.record'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    bim_transport_equipment_id = fields.Many2one('bim.transport.equipment', string='Equipment')
    date = fields.Date('Date', default=fields.Date.today)
    transportation_expenses_id = fields.Many2one('transportation.expenses', string='Expenses', required=True)
    amount = fields.Float('Amount')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    driver_id = fields.Many2one('res.partner', string='Driver')
    bim_project_id = fields.Many2one('bim.project', string='Project', required=True)
    kilometers = fields.Float('Kilometers')
    file_name = fields.Char("File Name", copy=False)
    file = fields.Binary(string='File', copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('invoiced', 'Invoiced'), ('cancel', 'Cancelled')], string='State', default='draft')
    supplier_id = fields.Many2one('res.partner', required=True)
    invoice_id = fields.Many2one('account.move', string='Invoice')

    # transportation_expenses_id
    @api.onchange('bim_transport_equipment_id')
    def _onchange_bim_transport_equipment_id(self):
        if self.bim_transport_equipment_id:
            self.driver_id = self.bim_transport_equipment_id.driver_id.id
            self.bim_project_id = self.bim_transport_equipment_id.bim_project_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('tms.expense.record') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        self.state = 'confirmed'

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'

    def action_invoice(self):
        self.ensure_one()
        journal_id = self.env['account.journal'].search([('type', '=', 'purchase'),('company_id','=',self.company_id.id)], limit=1)
        vals = {
            'move_type': 'in_invoice',
            'invoice_date': date.today(),
            'invoice_origin': self.name,
            'partner_id': self.supplier_id.id,
            'fiscal_position_id': self.supplier_id.with_company(self.company_id).property_account_position_id and self.supplier_id.with_company(self.company_id).property_account_position_id.id or False,
            'company_id': self.company_id.id,
            'invoice_user_id': self.user_id.id,
            'journal_id': journal_id.id,
            'currency_id': self.company_id.currency_id.id,
            'invoice_line_ids': [],
            'include_for_bim': True,
        }
        if self.transportation_expenses_id and self.transportation_expenses_id.product_id:
            product_expense = self.transportation_expenses_id.product_id
        else:
            product_expense = self.env["ir.config_parameter"].sudo().get_param("product_expense_invoice_id")
        if not product_expense:
            raise UserError(_('Please set product expense invoice in configuration'))
        vals['invoice_line_ids'].append(
            (0, 0,
             {'product_id': product_expense.id,
              'quantity': 1,
              'price_unit': self.amount,
              'company_id': self.company_id.id,
              'name': product_expense.partner_ref,
              'product_uom_id': product_expense.uom_po_id.id,
              'tax_ids': product_expense.supplier_taxes_id.filtered(lambda r: r.company_id == self.company_id),
              'analytic_distribution': {'%s' % (self.bim_project_id.analytic_id.id): 100}
        }))

        self.invoice_id = self.env['account.move'].create(vals).id
        self.state = 'invoiced'

    def action_view_invoice(self):
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        if self.invoice_id:
            action['views'] = [(False, "form")]
            action['res_id'] = self.invoice_id.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action