# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import datetime, date
import logging
_logger = logging.getLogger(__name__)

class InvoiceFromPickingMass(models.Model):
    _name = 'invoice.from.picking.mass'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Invoice From Picking'
    _order = "id desc"

    @api.depends('invoice_ids')
    def _compute_count_invoices(self):
        for record in self:
            in_invoices = record.invoice_ids.filtered(lambda s: s.move_type in ['in_invoice', 'in_refund'])
            out_invoices = record.invoice_ids.filtered(lambda s: s.move_type in ['out_invoice', 'out_refund'])
            record.count_in_invoices = len(in_invoices)
            record.count_out_invoices = len(out_invoices)

    name = fields.Char('Referencia', copy=False, default="Nuevo")
    invoicefrompicking_line_ids = fields.One2many('invoice.from.picking.mass.line', 'invoicefrompicking_id', copy=False,
                                                string='Lineas Albaranes')

    invoice_from_picking_mass_line_add_ids = fields.One2many('invoice.from.picking.mass.line.add', 'invoicefrompicking_id', copy=False,
                                                string='Add Albaranes')

    state = fields.Selection(string='Estado', selection=[('draft', 'Borrador'),
                                                          ('process', 'Facturas Generadas'),
                                                          ('approved', 'Facturas Aprobadas'),
                                                          ('deleted', 'Facturas Borradas')]
                                                          , default='draft')
    count_out_invoices = fields.Integer('Nº Facturas Out Invoices', compute='_compute_count_invoices')
    invoice_ids = fields.One2many('account.move', 'invoicefrompicking_id', 'Facturas')
    count_in_invoices = fields.Integer('Nº Facturas In Invoices', compute='_compute_count_invoices')
    company_id = fields.Many2one(comodel_name="res.company", string="Compañía", default=lambda self: self.env.company,
                                 required=True)
    user_id = fields.Many2one('res.users', string="Creado por", default=lambda self: self.env.user)
    date_to_invoice = fields.Datetime(string='Fecha Facturas', default=fields.Datetime.now)
    type = fields.Selection(string='Tipo', selection=[('purchase', 'Compras'), ('sale', 'Ventas')])
    add_invoice = fields.Boolean('Añadir Factura', default=False)
    add_account_move_id = fields.Many2one('account.move', 'Factura')

    def action_view_out_invoices(self):
        invoices = []
        for inv in self.invoice_ids:
            if inv.move_type in ['out_invoice', 'out_refund']:
                invoices.append(inv.id)

        action = self.env.ref('account.action_move_out_invoice_type').read()[0]

        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_in_invoices(self):
        invoices = []
        for inv in self.invoice_ids:
            if inv.move_type in ['in_invoice', 'in_refund']:
                invoices.append(inv.id)
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _prepare_invoice_values(self, result, line, partner, type, step):
        if partner.parent_id:
            partner = partner.parent_id
        flag = True
        if result:
            for r in result:
                if r['partner_id'] == partner.id:
                    picking_id_name = ""
                    for l in line.picking_id.move_ids:
                        _name = "Albarán:" + line.picking_id.name + ", Fecha: " + str(line.picking_id.scheduled_date)
                        if line.picking_id.external_reference:
                            _name += ", Ref. Ext: " + line.picking_id.external_reference
                        if picking_id_name != line.picking_id.name:
                            r['invoice_line_ids'].append((0, 0, {
                                'name': _name,
                                'display_type': 'line_section',
                            }))
                        picking_id_name = line.picking_id.name



                        _logger.info("A")

                        purchase_line_id = False
                        price_unit = 0.0
                        tax_ids = False

                        discount = 0
                        price_unit = l.product_cost

                        if l.purchase_line_id:
                            _purchase_line_id = self.env['purchase.order.line'].search([
                                    ('id', '=', l.purchase_line_id.id)
                            ], limit=1)

                            if _purchase_line_id:
                                purchase_line_id = _purchase_line_id.id
                                price_unit = _purchase_line_id.price_unit
                                tax_ids = _purchase_line_id.taxes_id.ids
                                discount = _purchase_line_id.discount

                        if l.sale_line_id:
                            _sale_line_id = self.env['sale.order.line'].search([
                                    ('id', '=', l.sale_line_id.id)
                            ], limit=1)

                            if _sale_line_id:
                                price_unit = _sale_line_id.price_unit
                                tax_ids = _sale_line_id.tax_id.ids
                                discount = _sale_line_id.discount

                        r['invoice_line_ids'].append((0, 0, {
                            'picking_id': line.picking_id.id,
                            'line_picking_id': l.id,
                            'purchase_line_id': purchase_line_id if purchase_line_id else False,
                            'product_id': l.product_id.id,
                            'quantity': l.quantity,
                            'price_unit': l.product_cost,
                            'tax_ids': tax_ids,
                        }))
                    flag = False
                    break

        if flag:
            invoice_lines = []
            for xline in line.picking_id:
                _name = "Albarán:" + line.picking_id.name + ", Fecha: " + str(line.picking_id.scheduled_date)
                if line.picking_id.external_reference:
                    _name += ", Ref. Ext: " + line.picking_id.external_reference
                line_vals = {
                    'name': _name,
                    'display_type': 'line_section',
                }
                invoice_lines.append((0, 0, line_vals))

                for l in xline.move_ids:
                    line_vals = {
                        'picking_id': line.picking_id.id,
                        'line_picking_id': l.id,
                        'sale_line_ids': [(6, 0, l.sale_line_id.ids)] if l.sale_line_id else [(6, 0, [])],
                        'product_id': l.product_id.id,
                        'quantity': l.quantity,
                        'price_unit': l.product_cost,
                    }
                    invoice_lines.append((0, 0, line_vals))




            if type == 'sale':
                _move_type = 'out_invoice' if step == 1 else 'out_refund'
            else:
                _move_type = 'in_invoice' if step == 1 else 'in_refund'

            _val = {
                'ref': line.picking_id.sale_id.client_order_ref,
                'move_type': _move_type,
                'invoice_date': self.date_to_invoice,
                'invoice_origin': self.name,
                'picking_id': line.picking_id.id,
                'narration': line.picking_id.sale_id.note if line.picking_id.sale_id else line.picking_id.purchase_id.notes,
                'partner_id': partner.id,
                'fiscal_position_id': line.picking_id.partner_id.property_account_position_id.id,
                'partner_shipping_id': line.picking_id.sale_id.partner_shipping_id.id if line.picking_id.sale_id else False,
                'currency_id': line.picking_id.company_id.currency_id.id,
                'invoicefrompicking_id': self.id,
                'invoice_line_ids': invoice_lines,
            }
            result.append(_val)
        return result


    def add_picking(self):
        if not self.invoice_ids:
            raise UserError('Debe generar las facturas antes de añadir albaranes')
        else:
            if not self.add_account_move_id:
                self.add_account_move_id = self.invoice_ids[0].id

        # Adicionamos las lineas de albaranes a la factura
        for line in self.invoice_from_picking_mass_line_add_ids:
            if line.picking_id.state_invoice == 'to_invoice':
                line.picking_id.state_invoice = 'invoiced'

                val = {
                    'name': "Albarán:" + line.picking_id.name + ", Fecha: " + str(line.picking_id.scheduled_date),
                    'display_type': 'line_section',
                    'move_id': self.add_account_move_id.id,
                }


                l = self.env['account.move.line'].create(val)
                line.account_move_line_ids = [(4, l.id)]


                for line_picking in line.picking_id.move_ids:
                    _logger.info(line_picking.product_id.name)

                    val = {
                        'move_id': self.add_account_move_id.id,
                        'product_id': line_picking.product_id.id,
                        'quantity': line_picking.quantity,
                        'price_unit': line_picking.product_cost,
                        'tax_ids': [(6, 0, line_picking.product_id.supplier_taxes_id.ids)],
                    }

                    l = self.env['account.move.line'].create(val)
                    line.account_move_line_ids = [(4, l.id)]


        self.add_invoice = True

    def delete_picking(self):
        for line in self.invoice_from_picking_mass_line_add_ids:
            line.picking_id.state_invoice = 'to_invoice'

            for l in line.account_move_line_ids:
                if l.move_id.state == 'draft':
                    l.unlink()
                else:
                    raise UserError('No se puede eliminar la linea de factura, ya esta contabilizada')

        self.add_invoice = False

    def make_invoice_picking(self):
        # Facturamos las Facturas
        step = 1
        move_obj = self.env['account.move']
        for record in self:
            result = []

            invoicefrompicking_line_ids = record.invoicefrompicking_line_ids
            r_invoicefrompicking_line_ids = record.invoicefrompicking_line_ids

            devolucion = False
            # Quitamos las devolucion
            len_initial = len(invoicefrompicking_line_ids)
            if self.type == 'purchase':
                invoicefrompicking_line_ids = invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.picking_type_id.code == 'incoming')
                len_final = len(invoicefrompicking_line_ids)
                if len_final < len_initial:
                    devolucion = True

            if self.type == 'sale':
                invoicefrompicking_line_ids = invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.picking_type_id.code == 'outgoing')
                len_final = len(invoicefrompicking_line_ids)
                if len_final < len_initial:
                    devolucion = True

            billable = invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.state_invoice == 'invoiced')


            _logger.info("----1b------")
            _logger.info(billable)
            if invoicefrompicking_line_ids:
                if not billable:
                    partners = invoicefrompicking_line_ids.mapped('partner_id')
                    for partner in partners:
                        for line in invoicefrompicking_line_ids.filtered(lambda s: s.partner_id.id == partner.id):
                            if line.picking_id.state_invoice == 'to_invoice':
                                result = (record._prepare_invoice_values(result, line, line.partner_id, record.type, step))

                    for r in result:
                        _logger.info(r)
                        new_invoice = move_obj.create(r)
                        new_invoice._onchange_partner_id()

                    for l in invoicefrompicking_line_ids:
                        l.picking_id.state_invoice = 'invoiced'
                    record.write({
                        'state': 'process'
                    })
                else:
                    raise UserError('Hay albaranes que ya estan facturados, por favor realice la busqueda nuevamente *1')
            else:
                if not devolucion:
                    raise UserError('A - Debe generar una busqueda antes de facturar')


        # Facturamos las NC
        step = 2
        move_obj = self.env['account.move']
        for record in self:
            result = []

            invoicefrompicking_line_ids = record.invoicefrompicking_line_ids

            # Quitamos las devolucion
            if self.type == 'purchase':
                invoicefrompicking_line_ids = r_invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.picking_type_id.code == 'outgoing')
                _logger.info(invoicefrompicking_line_ids)


            if self.type == 'sale':
                invoicefrompicking_line_ids = r_invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.picking_type_id.code == 'incoming')

            billable = invoicefrompicking_line_ids.filtered(lambda s: s.picking_id.state_invoice == 'invoiced')

            if invoicefrompicking_line_ids:
                partners = invoicefrompicking_line_ids.mapped('partner_id')
                for partner in partners:
                    for line in invoicefrompicking_line_ids.filtered(lambda s: s.partner_id.id == partner.id):
                        if line.picking_id.state_invoice == 'to_invoice':
                            result = (record._prepare_invoice_values(result, line, line.partner_id, record.type, step))

                for r in result:
                    _logger.info(r)
                    new_invoice = move_obj.create(r)
                    new_invoice._onchange_partner_id()

                for l in invoicefrompicking_line_ids:
                    l.picking_id.state_invoice = 'invoiced'
                record.write({
                    'state': 'process'
                })

    def convert_to_draft(self):
        for record in self:
            for line in record.invoicefrompicking_line_ids:
                if line.picking_id.state_invoice == 'invoiced':
                    line.picking_id.state_invoice = 'to_invoice'
            for invoice in record.invoice_ids:
                invoice.unlink()
            record.write({
                'state': 'draft'
            })

    def approve_invoice_picking(self):
        for record in self:
            for invoice in record.invoice_ids:
                invoice.action_post()
                for line_invoice in invoice.invoice_line_ids:
                    if record.type == 'sale':
                        line_invoice.line_picking_id.sale_line_id.qty_invoiced = line_invoice.quantity
                    if record.type == 'purchase':
                        line_invoice.line_picking_id.purchase_line_id.qty_invoiced = line_invoice.quantity
            record.write({
                'state': 'approved'
            })

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            type_ifpm = values.get('type')

            if values.get('name', 'Nuevo') == 'Nuevo':
                if type_ifpm == 'sale':
                    values['name'] = self.env['ir.sequence'].next_by_code(
                        'out.invoice.from.picking.mass'
                    ) or 'Nuevo'
                else:
                    values['name'] = self.env['ir.sequence'].next_by_code(
                        'in.invoice.from.picking.mass'
                    ) or 'Nuevo'

        return super().create(vals_list)

class InvoiceFromPickingMassLine(models.Model):
    _name = 'invoice.from.picking.mass.line'
    _description = 'Invoice From Picking Line'

    picking_id = fields.Many2one('stock.picking', 'Nro. Doc.')
    partner_id = fields.Many2one('res.partner', 'Nombre R. Social')
    date = fields.Datetime(string='Fecha Pevista')
    origin = fields.Char('Su referencia')
    invoicefrompicking_id = fields.Many2one('invoice.from.picking.mass', 'Busqueda')
    state_invoice = fields.Selection([
        ('to_invoice', 'Por Facturar'),
        ('invoiced', 'Facturado'),
    ], 'Facturación', default='to_invoice', compute='_compute_state_invoice')

    def _compute_state_invoice(self):
        for line in self:
            line.state_invoice = line.picking_id.state_invoice

    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        for line in self:
            if line.picking_id:
                picking = line.picking_id
                line.partner_id = picking.partner_id.id
                line.date = picking.scheduled_date
                line.origin = picking.sale_id.client_order_ref


class InvoiceFromPickingMassLineAdd(models.Model):
    _name = 'invoice.from.picking.mass.line.add'
    _description = 'Invoice From Picking Line'

    picking_id = fields.Many2one('stock.picking', 'Nro. Doc.')
    partner_id = fields.Many2one('res.partner', 'Nombre R. Social')
    date = fields.Datetime(string='Fecha Pevista')
    origin = fields.Char('Su referencia')
    invoicefrompicking_id = fields.Many2one('invoice.from.picking.mass', 'Busqueda')
    state_invoice = fields.Selection([
        ('to_invoice', 'Por Facturar'),
        ('invoiced', 'Facturado'),
    ], 'Facturación', default='to_invoice', compute='_compute_state_invoice')
    account_move_line_ids = fields.Many2many('account.move.line', string='Lineas de Factura')


    def _compute_state_invoice(self):
        for line in self:
            line.state_invoice = line.picking_id.state_invoice


    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        for line in self:
            if line.picking_id:
                picking = line.picking_id
                line.partner_id = picking.partner_id.id
                line.date = picking.scheduled_date
                line.origin = picking.sale_id.client_order_ref
