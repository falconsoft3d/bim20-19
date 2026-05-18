# -*- coding: utf-8 -*-
import base64
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class BimRq(models.Model):
    _description = "Bim Rq"
    _name = 'bim.rq'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, index=True,default='New')
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    line_ids = fields.One2many('bim.rq.line', 'rq_id', string='Lines', copy=True)
    date = fields.Date('Date', default=datetime.today(), required=True)
    date_required = fields.Date('Date Required', default=datetime.today(), required=True)
    purchase_id = fields.Many2one('purchase.order', string='Purchase Order', copy=False)
    partner_id = fields.Many2one('res.partner', string='Vendor')
    project_id = fields.Many2one('bim.project', string='Project')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='State', required=True, default='draft', tracking=True)

    description = fields.Text('Description')

    # onchange line_ids to set project_id
    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        if self.line_ids:
            self.project_id = self.line_ids[0].project_id.id
        else:
            self.project_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.rq') or 'New'
        return super().create(vals_list)

    # to_review
    def action_to_review(self):
        self.state = 'review'

    # approve
    def action_approve(self):
        self.state = 'approved'

    # reject
    def action_reject(self):
        self.state = 'rejected'

    # action_set_to_draft
    def action_set_to_draft(self):
        self.state = 'draft'

    # done
    def action_set_to_done(self):
        if not self.line_ids:
            raise UserError(_('You cannot set to done a RQ without lines.'))

        if not self.partner_id:
            raise UserError(_('You must set a Vendor before setting the RQ to done.'))

        if not self.purchase_id:
            # la creamos
            purchase_vals = {
                'partner_id': self.partner_id.id,
                'date_order': self.date,
                'company_id': self.company_id.id,
                'origin': self.name,
                'project_id': self.project_id.id if self.line_ids else False,
                'budget_id': self.line_ids[0].budget_id.id if self.line_ids else False,
            }

            purchase = self.env['purchase.order'].create(purchase_vals)

            for line in self.line_ids:
                purchase_line_vals = {
                    'order_id': purchase.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.qty,
                    'date_planned': self.date,
                    'company_id': self.company_id.id,
                    'price_unit': 0.0,
                    'name': line.description if line.description else line.product_id.name_get()[0][1],
                }
                self.env['purchase.order.line'].create(purchase_line_vals)

            self.purchase_id = purchase.id

        self.state = 'done'

class BimRqLine(models.Model):
    _description = "Bim Rq"
    _name = 'bim.rq.line'

    rq_id = fields.Many2one('bim.rq', string='RQ', required=True)
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    qty = fields.Float('Quantity', required=True, default=1.0)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Text('Description')
    unit_price = fields.Float('Unit Cost', required=True, default=0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.name_get()[0][1]
