# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError,ValidationError
import base64
from io import BytesIO
from odoo.tools.misc import xlwt

class BimPurchaseServices(models.Model):
    _inherit = ['mail.thread']
    _description = "Services Request"
    _name = 'bim.purchase.services'
    _order = "id desc"

    name = fields.Char('Code', default="New")
    user_id = fields.Many2one('res.users', string='Responsable', tracking=True, default=lambda self: self.env.user)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    date_begin = fields.Date('Start Date', default = lambda self: datetime.today())
    date_prevista = fields.Date('Expected date', default = lambda self: datetime.today())


    def _get_domain_project_id(self):
        domain = [
            '&',  # Para combinar las siguientes dos condiciones con un "AND"
            ('company_id', '=', self.env.company.id),
            '|',  # Para especificar las dos condiciones alternativas
            ('requisition_user_ids', 'in', self.env.user.id),
            ('requisition_user_ids', '=', False)
        ]
        return domain

    project_id = fields.Many2one('bim.project', string='Project',
                                domain= _get_domain_project_id)

    obs = fields.Text('Notes', default="")
    analytic_id = fields.Many2one('account.analytic.account', 'Analytical Account')
    state = fields.Selection([('nuevo', 'New'),('aprobado', 'Approved'),('finalizado', 'Done'),
                              ('cancelled', 'Cancelled')],'Status', default='nuevo', tracking=True)
    product_ids = fields.One2many('service.list', 'service_id', string='Service List')
    purchase_ids = fields.One2many('purchase.order', 'bim_service_id', string='Purchases')
    purchase_count = fields.Integer('Quantity Purchases', compute="_compute_purchases")
    amount_total = fields.Float('Total', compute="_compute_total", digits="BIM price")
    space_id = fields.Many2one('bim.budget.space', 'Space')
    buy_more = fields.Boolean('Allow to Buy More', default=lambda self: self.env.company.allow_to_buy_more_serv,store=True)
    purchase_requisition_ids = fields.Many2many('purchase.requisition', string='Purchase Agreement')
    agree_count = fields.Integer('Agreement Quantity', compute="_compute_purchase_requisitions")
    separate = fields.Boolean('Separate')


    @api.onchange('project_id')
    def onchange_project_id(self):
        self.analytic_id = self.project_id.analytic_id.id

    def action_approve(self):
        self.write({'state': 'aprobado'})

    def action_export_xls(self):
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet(_("Product"))
        file_name = self.name
        style_border_table_top = xlwt.easyxf(
            'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

        worksheet.write(0, 0, _("Concept"), style_border_table_top)
        worksheet.write(0, 1, _("Product"), style_border_table_top)
        worksheet.write(0, 2, _("UOM"), style_border_table_top)
        worksheet.write(0, 3, _("CA"), style_border_table_top)
        worksheet.write(0, 4, _("Qty"), style_border_table_top)
        worksheet.write(0, 5, _("Cost"), style_border_table_top)
        worksheet.write(0, 6, _("Subtotal"), style_border_table_top)
        worksheet.write(0, 7, _("Obs"), style_border_table_top)

        row = 1
        for line in self.product_ids:
            style = style_border_table_details
            worksheet.write(row, 0, line.bim_concepts_id.name, style)
            worksheet.write(row, 1, line.product_id.name, style)
            worksheet.write(row, 2, line.um_id.name, style)
            worksheet.write(row, 3, line.analytic_id.name, style)
            worksheet.write(row, 4, line.quant , style)
            worksheet.write(row, 5, line.cost, style)
            worksheet.write(row, 6, line.subtotal, style)
            worksheet.write(row, 7, line.obs, style)
            row += 1

        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        data_b64 = base64.encodebytes(data)
        doc = self.env['ir.attachment'].create({
            'name': '%s.xls' % (file_name),
            'datas': data_b64,
        })
        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'no_destroy': False,
        }

    def action_done(self):
        self.write({'state': 'finalizado'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'new'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.purchase.services') or 'New'

        records = super().create(vals_list)
        for res in records:
            if res.project_id and res.project_id.nombre:
                res.name = f"{res.name} - {res.project_id.nombre}"
        return records

    def _compute_purchases(self):
        for req in self:
            req.purchase_count = len(req.purchase_ids)
    @api.depends('purchase_requisition_ids')
    def _compute_purchase_requisitions(self):
        for req in self:
            req.agree_count = len(req.purchase_requisition_ids)

    def _compute_total(self):
        for record in self:
            record.amount_total = sum(pd.subtotal for pd in record.product_ids)

    def action_view_purchases(self):
        purchases = self.mapped('purchase_ids')
        action = self.env.ref('purchase.purchase_rfq').sudo().read()[0]
        if len(purchases) > 0:
            action['domain'] = [('id', 'in', purchases.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_agreement(self):
        agreements = self.mapped('purchase_requisition_ids')
        action = self.env.ref('purchase_requisition.action_purchase_requisition').sudo().read()[0]
        if len(agreements) > 0:
            action['domain'] = [('id', 'in', agreements.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


class ServiceList(models.Model):
    _name = 'service.list'
    _description = 'Service List'
    _rec_name = 'product_id'

    solo_lectura = fields.Boolean('Readonly', default=False, compute='_compute_giveme_state')

    def _compute_giveme_state(self):
        if self.service_id.state == 'nuevo':
            self.solo_lectura = False
        else:
            self.solo_lectura = True

    @api.depends('service_id.purchase_ids')
    def _compute_qty_done(self):
        for record in self:
            orders = record.service_id.purchase_ids.mapped('order_line').filtered(lambda m: m.state not in ('cancel') and m.product_id.id == record.product_id.id)
            record.qty_done = sum(x.product_qty for x in orders)

    @api.depends('qty_done','quant')
    def _compute_qty_to_process(self):
        for record in self:
            if record.qty_done > record.quant:
                record.qty_to_process = 0
                record.subtotal = record.qty_done * record.cost
            else:
                record.qty_to_process = record.quant - record.qty_done
                record.subtotal = record.quant * record.cost

    @api.depends('service_id.purchase_ids')
    def _compute_qty_purchase(self):
        for record in self:
            purchase_lines = record.service_id.purchase_ids.mapped('order_line').filtered(lambda r: r.bim_req_line_id.id == record.id and r.state != 'cancel')
            record.qty_purchase = sum(x.product_qty for x in purchase_lines)

    product_id = fields.Many2one('product.product', 'Product')
    quant = fields.Float('Quantity', digits="BIM qty")
    cost = fields.Float('Cost')
    subtotal = fields.Float('Subtotal', compute="_compute_qty_to_process")
    obs = fields.Text('Notes', default="")
    um_id = fields.Many2one('uom.uom', 'U.M')
    done = fields.Boolean('Done')
    qty_to_process = fields.Float('To process', compute="_compute_qty_to_process", digits="BIM qty")
    qty_done = fields.Float('Dispatched Quant', compute="_compute_qty_done",store=True, digits="BIM qty")
    qty_purchase = fields.Float('Purchased', compute="_compute_qty_purchase",store=True, digits="BIM qty")
    sent_to_production = fields.Boolean('Sent to production')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    analytic_id = fields.Many2one('account.analytic.account', 'Analytical account')
    partner_ids = fields.Many2many('res.partner', string='Supplier')
    service_id = fields.Many2one('bim.purchase.services', 'Requisition', ondelete='cascade')
    project_id = fields.Many2one('bim.project', string="Project", domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', string="Budget")
    bim_concepts_id = fields.Many2one('bim.concepts', string='Concept')
    state = fields.Selection(related='service_id.state', string='State', store=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.um_id = self.product_id.uom_id.id
        self.analytic_id = self.service_id.analytic_id.id
        self.project_id = self.service_id.project_id.id
        self.cost = self.product_id.standard_price

    @api.constrains('product_id')
    def _check_product_id(self):
        if not self.service_id.state == 'nuevo':
            raise ValidationError(_("You cannot Add Lines in this State"))

    def unlink(self):
        for requisition_list in self:
            if requisition_list.solo_lectura:
                raise UserError(_('You cannot delete a Line in this other than New!'))
        return super().unlink()

