# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class OtherExpense(models.Model):
    _description = "Other Expense"
    _name = 'other.expense'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True,
        readonly=True, copy=False, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('other.expense'))

    partnerp_id = fields.Many2one('res.partner', 'Proveedor', ondelete="cascade")
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    date = fields.Date('Date', default=fields.Datetime.now, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False, tracking=True)

    line_ids = fields.One2many('other.expense.line', 'other_expense_id', string='Other Expense Lines')

    total = fields.Float('Total', compute='_compute_total', store=True)

    @api.depends('line_ids.total')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(line.total for line in rec.line_ids)


    def action_to_done(self):
        self.write({'state': 'done'})


    def action_to_draft(self):
        self.write({'state': 'draft'})


    def action_to_cancel(self):
        self.write({'state': 'cancel'})


class OtherExpenseLine(models.Model):
    _name = 'other.expense.line'
    _description = 'Other Expense Line'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Char('Description')
    project_id = fields.Many2one('bim.project', string='Proyecto')
    budget_id = fields.Many2one('bim.budget', string='Presupuesto', domain="[('project_id', '=', project_id)]")
    concept_id = fields.Many2one('bim.concepts', string='Partida', domain="[('budget_id', '=', budget_id),('type', '=', 'departure')]")

    qty = fields.Float('Quantity')
    price_unit = fields.Float('Unit Price')
    total = fields.Float('Total' , compute='_compute_total', store=True)
    other_expense_id = fields.Many2one('other.expense', string='Other Expense')
    currency_id = fields.Many2one(related='other_expense_id.currency_id', store=True)
    date = fields.Date(related='other_expense_id.date', store=True)


    @api.depends('qty', 'price_unit')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.qty * rec.price_unit


    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price
            self.name = self.product_id.name