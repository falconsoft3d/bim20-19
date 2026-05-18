# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

import logging
_logger = logging.getLogger(__name__)


class BimRent(models.Model):
    _name = 'bim.tool.rent'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Tool Rent'
    _order = 'id desc'

    name = fields.Char("Reference", required=True, default='New', copy=False)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True,required=True, compute='_compute_currency_id')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True,
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    state = fields.Selection(selection=[('draft', 'Draft'), ('rented', 'Rented'),('finished', 'Finished'), ('cancel', 'Cancelled')], string='Status', default='draft', tracking=True)
    terms = fields.Text("Terms", default="")
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=True)
    user_id = fields.Many2one('res.users', string='Sales Person', readonly=True, index=True, tracking=True, default=lambda self: self.env.user)
    rent_line_ids = fields.One2many('bim.tool.rent.line', 'bim_rent_id', string='Rent Lines', copy=True)
    date_from = fields.Date(string='Date From:', default=fields.Date.context_today, required=True)
    date_to = fields.Date(string='Date To:', default=fields.Date.context_today, required=True)
    invoice_ids = fields.Many2many('account.move', copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    project_id = fields.Many2one('bim.project', 'Project', ondelete="restrict", copy=True,
                                 domain="[('company_id','=',company_id)]", tracking=1)
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", copy=True,
                                domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict", copy=True,
                                 domain="[('budget_id','=',budget_id),('type','=','departure')]")
    rent_type = fields.Selection([('in','In Rent'),('out_invoice','Out Rent')], default='in', tracking=True, required=True)
    delivery_id = fields.Many2one('deliver.products', 'Delivery', copy=False, readonly=True)
    bim_purchase_requisition_id = fields.Many2one('bim.purchase.requisition', 'Purchase Requisition', copy=False, readonly=True)

    @api.depends('company_id', 'project_id')
    def _compute_currency_id(self):
        for record in self:
            currency_id = record.company_id.currency_id
            if record.project_id:
                currency_id = record.project_id.currency_id
            record.currency_id = currency_id.id

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for record in self:
            if record.partner_id.user_id:
                record.user_id = record.partner_id.user_id.id
            else:
                record.user_id = record.env.user

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.tool.rent') or 'New'
        return super().create(vals_list)

    def action_sign(self):
        for record in self:
            if not record.rent_line_ids:
                raise UserError(_("You can not rent without tools"))
            record.state = 'rented'
            delivery_lines = [(0,0,{
                'product_id': line.product_id.id,
                'qty': line.product_uom_qty,
                'cost': line.price_unit,
            }) for line in record.rent_line_ids]
            record.make_tool_delivery(delivery_lines)
            record.project_id.action_update_all()


    def make_tool_delivery(self, delivery_lines):
        employee = self.env['hr.employee'].search([('user_partner_id','=',self.partner_id.id)],limit=1)
        if employee:

            delivery = self.env['deliver.products'].create({
                'employee_id': employee.id,
                'type':'delivery',
                'product_ids': delivery_lines


            })
            delivery.exe_solicitado()
            delivery.exe_aprobar()
            delivery.exe_deliver()
            self.delivery_id = delivery.id



    def action_finished(self):
        for record in self:
            record.update({
                'state': 'finished'
            })

    def action_cancel(self):
        for record in self:
            record.update({
                'state': 'cancel'
            })


    def convert_to_draft(self):
        for record in self:
            record.update({
                'state': 'draft'
            })

    @api.constrains('date_to','date_from')
    def _check_dates(self):
        if self.date_to and self.date_from:
            if self.date_from > self.date_to:
                raise UserError(_("Interval dates is wrong!"))

    @api.onchange('date_from','date_to','partner_id')
    def onchange_dates(self):
        if self.date_to and self.date_from:
            for line in self.rent_line_ids:
                line.onchange_product_id()


    @api.depends('rent_line_ids.price_total')
    def _amount_all(self):
        for contract in self:
            amount_untaxed = 0.0
            for line in contract.rent_line_ids:
                amount_untaxed += line.price_total
            contract.amount_total = amount_untaxed

    def action_send_rent(self):
        template_id = self.env.ref('recurrent_account_move.mail_template_contract_confirmation').id
        template = self.env['mail.template'].browse(template_id)
        ctx = {
            'default_model': 'account.contract',
            'default_res_id': self.ids[0],
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'force_email': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    @api.onchange('project_id')
    def onchange_project_id(self):
        self.budget_id = False
        self.concept_id = False

    @api.onchange('budget_id')
    def onchange_budget_id(self):
        self.concept_id = False

    def unlink(self):
        for rent in self:
            if rent.state != 'draft':
                raise UserError(_("It is not possible to delete Rent Record in other state than draft!"))
        return super().unlink()


class BimToolRentLine(models.Model):
    _name = 'bim.tool.rent.line'
    _description = 'Rent Tool Lines'

    product_id = fields.Many2one('product.product', string='Tool', required=True, domain="[('tool_ok', '=', True)]")
    name = fields.Text(string='Description', required=True, default="")
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, related='bim_rent_id.company_id')
    currency_id = fields.Many2one(related='bim_rent_id.currency_id', depends=['bim_rent_id.currency_id'], store=True, string='Currency', readonly=True)
    price_unit = fields.Float('Price Unit', required=True, digits="BIM price")
    product_uom_qty = fields.Float('Quantity', required=True, digits="BIM qty")
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    bim_rent_id = fields.Many2one('bim.tool.rent', string='Rent', ondelete='cascade')
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return
        if not self.bim_rent_id.date_from or not self.bim_rent_id.date_to:
            raise UserError(_("Select dates to continue!"))
        vals = {}
        product_uom_qty = self._prepare_quantity_according_to_dates()

        vals['product_uom_qty'] = product_uom_qty

        vals.update(name=self.product_id.display_name)
        vals['price_unit'] = self.product_id.with_company(self.company_id).lst_price
        vals['product_uom_qty'] = product_uom_qty
        self.update(vals)

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * line.product_uom_qty
            line.update({
                'price_total': price,
            })

    def _prepare_quantity_according_to_dates(self):
        product_uom_qty = 1
        if self.bim_rent_id.date_from and self.bim_rent_id.date_to:
            product_uom_qty = (self.bim_rent_id.date_to - self.bim_rent_id.date_from).days
            if product_uom_qty == 0:
                product_uom_qty = 1
        return product_uom_qty

    def _handle_weekend_and_holiday(self):
        date_start = self.bim_rent_id.date_from
        date_end = self.bim_rent_id.date_to
        product_uom_qty = (self.bim_rent_id.date_to - self.bim_rent_id.date_from).days
        if date_start == date_end and date_start.isoweekday() in [6,7]:
            return 0
        else:
            while date_start != date_end:
                date_start += timedelta(days=1)
                if date_start.isoweekday() in [6,7]:
                    product_uom_qty -= 1
        return product_uom_qty