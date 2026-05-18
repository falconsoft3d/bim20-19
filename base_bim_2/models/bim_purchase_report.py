# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BimPurchaseReport(models.Model):
    _description = "Bim Purchase Report"
    _name = 'bim.purchase.report'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char('Name', copy=False)
    line_ids = fields.One2many('bim.purchase.report.line', 'report_id', 'Lines')
    company_id = fields.Many2one('res.company', 'Compañia', default=lambda self: self.env.company.id)
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user.id)
    purchase_ids = fields.Many2many('purchase.order', string='Ordenes de Compra')
    r_purchase_ids = fields.Text('Ordenes de Compra Repetidas')

    def calc(self):
        for report in self:
            report.line_ids.unlink()
            report.r_purchase_ids = ""

            if self.purchase_ids:
                purchase_ids = self.purchase_ids
            else:
                purchase_ids = self.env['purchase.order'].search([
                    ('state', 'in', ['purchase', 'done','cancel']),
                ])

            for purchase in purchase_ids:
                # Comprobamos si la orden de compra tine lineas repetidas, si es asi la sumo a la variable r_purchase_ids

                for l in purchase.order_line:
                    if len(purchase.order_line.filtered(lambda x: x.product_id.id == l.product_id.id)) > 1:
                        if report.r_purchase_ids:
                            report.r_purchase_ids += ', ' + str(purchase.name)
                        else:
                            report.r_purchase_ids = str(purchase.name)
                        break


                for line in purchase.order_line:
                    # Revisamos si tiene un despacho
                    stock_move_ids = self.env['stock.move'].search([
                        ('purchase_line_id', '=', line.id),
                        ('state', '=', 'done'),
                    ])


                    qty_invoiced = 0
                    price_unit = 0
                    account_move_line_ids = self.env['account.move.line'].search([
                                ('purchase_line_id', '=', line.id),
                            ])

                    if account_move_line_ids:
                        for account_move_line in account_move_line_ids:
                            qty_invoiced += account_move_line.quantity
                            price_unit = account_move_line.price_unit

                    if len(stock_move_ids) > 1:
                        for stock in stock_move_ids:
                            bim_purchase_report_line_id = self.env['bim.purchase.report.line'].create({
                                'report_id': report.id,
                                'purchase_id': purchase.id,
                                'partner_id': purchase.partner_id.id,
                                'product_id': line.product_id.id,
                                'oc_date' : purchase.create_date,
                                'resource_type' : "MAT" if line.product_id.type == 'product' else "SUBCONTRATO",
                                'concept_phase_id' : line.concept_phase_id.id,
                                'state' : purchase.state,
                                'qty' : line.product_qty,
                                'undm' : line.product_uom.name if line.product_uom else '',
                                'price_unit' : line.price_unit,
                                'subtotal' : line.price_subtotal,
                                'numer_stock_picking' : stock.picking_id.name,
                                'schedule_date' : stock.picking_id.scheduled_date,
                                'number_confim' : "",
                                'qty_valoration' : stock.quantity,
                                'price_valoration' : stock.price_unit,
                                'price_saldo' : line.price_unit,
                                'qty_invoiced' : qty_invoiced,
                                'price_invoiced' : price_unit,
                            })
                    else:
                        if len(purchase.purchase_valuation_ids) > 0:
                            # Tengo más de una valorizacion
                            for val in purchase.purchase_valuation_ids:
                                purchase_valuation_line_id = self.env['purchase.valuation.line'].search([
                                    ('valuation_id', '=', val.id),
                                    ('product_id', '=', line.product_id.id),
                                ],limit=1)

                                qty_valoration = 0
                                price_valoration = 0

                                if purchase_valuation_line_id:
                                    qty_valoration = purchase_valuation_line_id.product_qty
                                    price_valoration = purchase_valuation_line_id.price_unit


                                    bim_purchase_report_line_id = self.env['bim.purchase.report.line'].create({
                                        'report_id': report.id,
                                        'purchase_id': purchase.id,
                                        'partner_id': purchase.partner_id.id,
                                        'product_id': line.product_id.id,
                                        'oc_date' : purchase.create_date,
                                        'resource_type' : "MAT" if line.product_id.type == 'product' else "SUBCONTRATO",
                                        'concept_phase_id' : line.concept_phase_id.id,
                                        'state' : purchase.state,
                                        'qty' : line.product_qty,
                                        'undm' : line.product_uom.name if line.product_uom else '',
                                        'price_unit' : line.price_unit,
                                        'subtotal' : line.price_subtotal,
                                        'numer_stock_picking' : val.name,
                                        'schedule_date' : val.date,
                                        'begin_date' : val.begin_date,
                                        'number_valuation' : val.name,
                                        'end_date' : val.end_date,
                                        'number_confim' : "",
                                        'qty_valoration' : qty_valoration,
                                        'price_valoration' : price_valoration,
                                        'price_saldo' : line.price_unit,
                                        'qty_invoiced' : qty_invoiced,
                                        'price_invoiced' : price_unit,
                                        'closed_valuation' : val.purchase_id.closed_valuation,
                                    })

                        else:
                            # No tengo ninguna valorizacion
                            bim_purchase_report_line_id = self.env['bim.purchase.report.line'].create({
                                'report_id': report.id,
                                'purchase_id': purchase.id,
                                'partner_id': purchase.partner_id.id,
                                'product_id': line.product_id.id,
                                'oc_date' : purchase.create_date,
                                'resource_type' : "MAT" if line.product_id.type == 'product' else "SUBCONTRATO",
                                'concept_phase_id' : line.concept_phase_id.id,
                                'state' : purchase.state,
                                'qty' : line.product_qty,
                                'undm' : line.product_uom.name if line.product_uom else '',
                                'price_unit' : line.price_unit,
                                'subtotal' : line.price_subtotal,
                                'numer_stock_picking' : "",
                                'schedule_date' : False,
                                'number_confim' : "",
                                'qty_valoration' : 0,
                                'price_valoration' : 0,
                                'price_saldo' : line.price_unit,
                                'qty_invoiced' : qty_invoiced,
                                'price_invoiced' : price_unit,
                            })

                    if bim_purchase_report_line_id:
                        bim_purchase_report_line_id.tc = 1

                        try:
                            if account_move_line_ids:
                                move_id = account_move_line_ids[0].move_id
                                if move_id.currency_id != self.env.company.currency_id:
                                    bim_purchase_report_line_id.tc = move_id.currency_rate
                        except:
                            pass



        return True


class BimPurchaseReportLine(models.Model):
    _description = "Bim Purchase Report Line"
    _name = 'bim.purchase.report.line'

    report_id = fields.Many2one('bim.purchase.report', 'Report')
    purchase_id = fields.Many2one('purchase.order', 'NRO OC')
    partner_id = fields.Many2one('res.partner', 'PROVEEDOR')
    product_id = fields.Many2one('product.product', 'PRODUCTO')
    oc_date = fields.Date('FECHA OC')
    resource_type = fields.Char('TIPO DE RECURSO')
    concept_phase_id = fields.Many2one('concept.phase', 'FASE')
    currency_id = fields.Many2one('res.currency', related='purchase_id.currency_id', string='MONEDA')
    state = fields.Char('ESTADO')
    undm = fields.Char('UNDM')
    qty = fields.Float('CANTIDAD')
    price_unit = fields.Float('PRECIO UNITARIO OC')
    subtotal = fields.Float('TOTAL')
    numer_stock_picking = fields.Char('NUMERO DE INGRESO DE MERCANCIA')
    schedule_date = fields.Date('FECHA DE INGRESO DE MERCANCIA')
    number_valuation = fields.Char('NUMERO DE VALORIZACION')
    number_confim = fields.Char('NUMERO DE CONFORMIDAD')
    qty_valoration = fields.Float('CANTIDAD VALORADA')
    price_valoration = fields.Float('PRECIO UNITARIO VALORADO')
    val_subtotal = fields.Float('TOTAL VALORADO', compute='_compute_val_subtotal')
    price_saldo = fields.Float('PRECIO UNITARIO SALDO')
    total_saldo = fields.Float('TOTAL SALDO', compute='_compute_total_saldo')
    begin_date = fields.Date('FECHA INICIO')
    end_date = fields.Date('FECHA FIN')
    tc = fields.Float('TC', default=1)
    closed_valuation = fields.Boolean('ESTADO OCV', default=False)

    @api.depends('qty_valoration', 'price_valoration')
    def _compute_val_subtotal(self):
        for rec in self:
            rec.val_subtotal = rec.qty_valoration * rec.price_valoration

    qty_saldo = fields.Float('CANTIDAD SALDO', compute='_compute_saldo')


    def _compute_saldo(self):
        for rec in self:
            rec.qty_saldo = rec.qty - rec.qty_valoration

    @api.depends('qty_saldo', 'price_saldo')
    def _compute_total_saldo(self):
        for rec in self:
            if rec.closed_valuation:
                rec.total_saldo = 0
            else:
                rec.total_saldo = rec.qty_saldo * rec.price_saldo

    qty_invoiced = fields.Float('CANTIDAD FACTURADA')
    price_invoiced = fields.Float('PRECIO UNITARIO')
    subtotal_invoiced = fields.Float('TOTAL FACTURADO', compute='_compute_subtotal_invoiced')

    @api.depends('qty_invoiced', 'price_invoiced')
    def _compute_subtotal_invoiced(self):
        for rec in self:
            rec.subtotal_invoiced = rec.qty_invoiced * rec.price_invoiced
