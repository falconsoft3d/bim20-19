# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

class ClosingExpenses(models.Model):
    _description = "Closing Expenses"
    _name = 'closing.expenses'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True, readonly=True, copy=False, index=True, default=lambda self: self.env['ir.sequence'].next_by_code('closing.expenses'))
    project_ids = fields.Many2many('bim.project', string='Projects')
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    date_closing = fields.Date('Closing Date', default=fields.Date.context_today, required=True)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ('cancel', 'Cancelled'),
        ], string='State', default='draft', copy=False, tracking=True)

    def action_validate(self):
        for rec in self:
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'
