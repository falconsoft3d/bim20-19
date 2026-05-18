# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

import logging
_logger = logging.getLogger(__name__)


class BimRent(models.Model):
    _name = 'bim.rent'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Rent'
    _order = 'id desc'

    name = fields.Char("Reference", required=True, default='New', copy=False)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True,required=True, related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True,
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    state = fields.Selection(selection=[('draft', 'Draft'), ('signed', 'Signed'),('invoiced', 'Invoiced'), ('finished', 'Finished'), ('cancel', 'Cancelled')], string='Status', default='draft', tracking=True)
    terms = fields.Text("Terms", default="")
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=True)
    user_id = fields.Many2one('res.users', string='Sales Person', readonly=True, index=True, tracking=True, default=lambda self: self.env.user)
    rent_line_ids = fields.One2many('bim.rent.line', 'bim_rent_id', string='Rent Lines', copy=True)
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
    rent_type = fields.Selection([('in_invoice','In Rent'),
    ('out_invoice','Out Rent')],
    help="Entrada es para rentas de equipos que se alquilan a la empresa, Salida es para rentas de equipos que la empresa alquila a terceros",
    default='in_invoice', tracking=True, required=True)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rent in self:
            rent.invoice_count = len(rent.invoice_ids)

    def action_view_invoice(self):
        invoice_ids = self.mapped('invoice_ids')
        action = self.env.ref('account.action_move_out_invoice_type').sudo().read()[0]
        if len(invoice_ids) == 1:
            action['views'] = [(False, "form")]
            action['res_id'] = self.invoice_ids.id
        elif len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

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
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.rent') or 'New'
        return super().create(vals_list)

    def action_sign(self):
        for record in self:
            if not record.rent_line_ids:
                raise UserError(_("You can not sign a contract without contract lines"))
            record.state = 'signed'
            for line in record.rent_line_ids:
                # line.equipment_id.rented_by = record.partner_id.id
                line.equipment_id.rent_state = 'rented'

    def action_finished(self):
        for record in self:
            record.update({
                'state': 'finished'
            })

            for line in record.rent_line_ids:
                line.equipment_id.rent_state = 'available'

    def action_cancel(self):
        for record in self:
            record.update({
                'state': 'cancel'
            })
            for line in record.rent_line_ids:
                line.equipment_id.rented_by = False
                line.equipment_id.rent_state = 'available'

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
                line.onchange_equipment_id()

    def action_invoice(self):
        self.ensure_one()
        journal = False
        journal_type = 'purchase' if self.rent_type == 'in_invoice' else 'sale'
        try:
            journal = self.env['account.journal'].sudo().search(
                [('type', '=', journal_type), ('company_id', '=', self.company_id.id)], limit=1).id
        except:
            pass
        if not journal:
            raise UserError(_("There are not journal to invoice this rent in Company {}").format(self.company_id.display_name))

        include_for_bim = False
        if self.rent_type == 'in_invoice':
            include_for_bim = True
        vals = {
            'move_type': self.rent_type,
            'invoice_origin': self.name,
            'partner_id': self.partner_id.id,
            'fiscal_position_id': self.partner_id.with_company(self.company_id).property_account_position_id.id if self.partner_id.with_company(self.company_id).property_account_position_id else False,
            'company_id': self.company_id.id,
            'invoice_user_id': self.user_id.id,
            'journal_id': journal,
            'currency_id': self.currency_id.id,
            'project_id': self.project_id.id if self.project_id else False,
            'budget_id': self.budget_id.id if self.budget_id else False,
            'concept_id': self.concept_id.id if self.concept_id else False,
            'invoice_line_ids': [],
            'include_for_bim': include_for_bim,
        }
        invoice_lines = []
        analytic_id = False
        if self.rent_type == 'in_invoice' and self.project_id and self.project_id.analytic_id:
            analytic_id = self.project_id.analytic_id.id
        for line in self.rent_line_ids:
            if not line.equipment_id.product_id:
                raise UserError(_("There are not product for equipment {}").format(line.equipment_id.display_name))
            line_vals = {
                'product_id': line.equipment_id.product_id.id,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'company_id': self.company_id.id,
                'name': line.name,
                'tax_ids': line.equipment_id.product_id.taxes_id.ids or [],
                'product_uom_id': line.product_uom.id,
            }
            if analytic_id:
                line_vals.update({
                    'analytic_distribution': {'%s'%(analytic_id): 100}
                })
            invoice_lines.append((0,0,line_vals))
        vals['invoice_line_ids'] = invoice_lines
        invoice = self.env['account.move'].sudo().create(vals)
        self.invoice_ids = [(4, invoice.id)]
        self.state = 'invoiced'

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


class BimRentLine(models.Model):
    _name = 'bim.rent.line'
    _description = 'Rent Lines'

    # product_id = fields.Many2one('product.product', string='Product', required=True, domain="[('type','=','service'),('rent_state','=','available'),('resource_type','=','Q')]")
    equipment_id = fields.Many2one('fleet.vehicle', string='Equipment', required=True)
    name = fields.Text(string='Description', required=True, default="")
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, related='bim_rent_id.company_id')
    currency_id = fields.Many2one(related='bim_rent_id.currency_id', depends=['bim_rent_id.currency_id'], store=True, string='Currency', readonly=True)
    price_unit = fields.Float('Price Unit', required=True, digits="BIM price")
    product_uom_qty = fields.Float('Quantity', required=True, digits="BIM qty")
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    bim_rent_id = fields.Many2one('bim.rent', string='Rent', ondelete='cascade')
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    @api.onchange('equipment_id')
    def onchange_equipment_id(self):
        self.name = self.equipment_id.name
        self.product_uom_qty = 1

        if self.equipment_id.fleet_vehicle_price_id:
            self.price_unit = self.equipment_id.fleet_vehicle_price_id.price

    """
    @api.onchange('equipment_id')
    def onchange_equipment_id(self):
        if not self.equipment_id:
            return
        if not self.bim_rent_id.date_from or not self.bim_rent_id.date_to:
            raise UserError(_("Select dates to continue!"))
        vals = {}
        product_uom_qty = self._prepare_quantity_according_to_dates()

        vals['product_uom_qty'] = product_uom_qty

        vals.update(name=self.equipment_id.description)
        vals['price_unit'] = self.equipment_id.price
        vals['product_uom_qty'] = product_uom_qty
        self.update(vals)"""

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