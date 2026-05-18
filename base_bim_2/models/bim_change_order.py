# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import base64
import io
import xlrd

class BimChangeOrder(models.Model):
    _description = "Bim Change Order"
    _name = 'bim.change.order'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True, readonly=True, copy=False, index=True, default=lambda self: self.env['ir.sequence'].next_by_code('bim.change.order'))
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    partner_id = fields.Many2one('res.partner', 'Partner', help="The partner associated with this change order, e.g., the client or contractor.")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='Status', default='draft', required=True, copy=False, tracking=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='budget_id.currency_id', readonly=True)
    lines_ids = fields.One2many('bim.change.order.line', 'bim_change_order_id', 'Lines')
    description = fields.Text('Description', help="Additional comments or notes regarding the change order.")
    amount_total = fields.Monetary('Total Amount', compute='_compute_amount_total')


    def action_load(self):
        for rec in self:
            rec.state = 'loaded'

    def action_approve(self):
        for rec in self:
            if not rec.lines_ids:
                raise UserError(_("You must add at least one line to the change order before approving it."))
            rec.state = 'approved'

    def action_to_done(self):
        for rec in self:
            if not rec.lines_ids:
                raise UserError(_("You must add at least one line to the change order before marking it as done."))
            rec.state = 'done'

    def action_to_draft(self):
        for rec in self:
            rec.state = 'draft'


    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.lines_ids.mapped('amount'))


class BimChangeOrderLine(models.Model):
    _description = "Bim Change Order Line"
    _name = 'bim.change.order.line'
    _order = 'id desc'

    bim_change_order_id = fields.Many2one('bim.change.order', 'Change Order', required=True, ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', related='bim_change_order_id.budget_id', readonly=True)
    concept_id = fields.Many2one('bim.concepts', 'Concept')
    name = fields.Char('Name', required=True, help="Description of the change order line.")
    qty = fields.Float('Qty')
    price_unit = fields.Monetary('Price Unit')
    amount = fields.Monetary('Amount')
    currency_id = fields.Many2one('res.currency', 'Currency', related='bim_change_order_id.currency_id', readonly=True)


    @api.onchange('concept_id')
    def _onchange_concept_id(self):
        self.name = self.concept_id.name if self.concept_id else ''

    @api.onchange('qty', 'price_unit')
    def _onchange_qty(self):
        self.amount = self.qty * self.price_unit