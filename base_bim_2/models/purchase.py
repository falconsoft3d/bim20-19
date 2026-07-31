# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
import base64
import io
import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    bim_requisition_id = fields.Many2one('bim.purchase.requisition', 'Requisition', copy=False)
    bim_service_id = fields.Many2one('bim.purchase.services', 'Services', copy=False)
    part_id = fields.Many2one('bim.part', 'Report', copy=False)
    project_id = fields.Many2one('bim.project', 'Project', tracking=True, copy=False,
    domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', copy=False,
    ondelete="restrict", domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', copy=False,
    ondelete="restrict", domain="[('budget_id','=',budget_id),('type','=','departure')]")
    margin = fields.Float('Margin (%)', default=0)
    place_of_delivery_id = fields.Many2one('res.partner', 'Place of Delivery')
    closed_valuation = fields.Boolean('Closed Valuation', default=False)

    purchase_valuation_ids = fields.One2many('purchase.valuation', 'purchase_id', string='Purchase Valuation')
    purchase_valuation_count = fields.Integer(compute='_compute_purchase_valuation_count', string='Purchase Valuation Count')

    payment_schedule_ids = fields.One2many('bim.payment.schedule', 'purchase_id', string='Programación de Pagos')
    payment_schedule_count = fields.Integer(compute='_compute_payment_schedule_count', string='Programaciones de Pagos')

    amount_paid = fields.Monetary(
        'Pagado', compute='_compute_payment_schedule_amounts',
        currency_field='currency_id',
        help='Suma de importes de programaciones de pago en estado Hecho')
    amount_pending = fields.Monetary(
        'Pendiente', compute='_compute_payment_schedule_amounts',
        currency_field='currency_id',
        help='Total pendiente de pago (Total - Pagado)')

    @api.depends('purchase_valuation_ids')
    def _compute_purchase_valuation_count(self):
        for purchase in self:
            purchase.purchase_valuation_count = len(purchase.purchase_valuation_ids)

    @api.depends('payment_schedule_ids')
    def _compute_payment_schedule_count(self):
        for purchase in self:
            purchase.payment_schedule_count = len(purchase.payment_schedule_ids)

    @api.depends('payment_schedule_ids.importe_a_pagar', 'payment_schedule_ids.state', 'amount_total')
    def _compute_payment_schedule_amounts(self):
        for purchase in self:
            paid = sum(
                s.importe_a_pagar
                for s in purchase.payment_schedule_ids
                if s.state == 'done'
            )
            purchase.amount_paid = paid
            purchase.amount_pending = purchase.amount_total - paid

    def action_view_purchase_valuation(self):
        action = self.env.ref('base_bim_2.purchase_valuation_action').sudo().read()[0]
        action['domain'] = [('purchase_id', '=', self.id)]
        action['context'] = {'default_purchase_id': self.id}
        return action

    def action_view_payment_schedule(self):
        action = self.env.ref('base_bim_2.bim_payment_schedule_action').sudo().read()[0]
        action['domain'] = [('purchase_id', '=', self.id)]
        action['context'] = {'default_purchase_id': self.id}
        return action

    def action_open_payment_schedule_wizard(self):
        self.ensure_one()
        return {
            'name': _('Programar pagos'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.payment.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def action_export_cash_flow_xlsx(self):
        if not self:
            raise UserError(_('Seleccione al menos una orden de compra.'))

        try:
            import xlsxwriter
        except ImportError as error:
            raise UserError(_('No está instalada la librería xlsxwriter.')) from error

        def month_key(value):
            return value.year, value.month

        def invoice_moves(order):
            return order.order_line.invoice_lines.mapped('move_id').filtered(
                lambda move: move.move_type == 'in_invoice' and move.state != 'cancel')

        months = set()
        order_invoices = {}
        for order in self:
            months.update(
                month_key(schedule.fecha_prevista)
                for schedule in order.payment_schedule_ids
                if schedule.fecha_prevista
            )
            moves = invoice_moves(order)
            order_invoices[order.id] = moves
            months.update(
                month_key(invoice.invoice_date or invoice.date)
                for invoice in moves
                if invoice.invoice_date or invoice.date
            )
        months = sorted(months)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Flujo de caja')
        header_format = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FFFFFF',
        })
        text_format = workbook.add_format({
            'border': 1, 'valign': 'vcenter',
        })
        money_format = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00',
        })
        month_format = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'text_wrap': True,
        })
        percentage_format = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00%',
        })
        date_format = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy',
        })
        total_format = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter',
            'bg_color': '#D9EAD3', 'num_format': '#,##0.00',
        })
        total_percentage_format = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter',
            'bg_color': '#D9EAD3', 'num_format': '0.00%',
        })
        total_text_format = workbook.add_format({
            'bold': True, 'border': 1, 'valign': 'vcenter', 'bg_color': '#D9EAD3',
        })
        month_names = (
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
        )
        headers = [
            'PO', 'Importe', 'Fecha PO', 'Descripción', 'Proveedor',
            'Fecha entrega según PO', 'Forma de pago', 'Comentarios', 'FACTURA',
        ]
        for column, header in enumerate(headers):
            worksheet.merge_range(0, column, 1, column, header, header_format)
        month_start_column = len(headers)
        for offset, (year, month) in enumerate(months):
            column = month_start_column + offset * 2
            worksheet.merge_range(
                0, column, 0, column + 1,
                '%s %s' % (month_names[month - 1], year), header_format)
            worksheet.write(1, column, 'Importe', header_format)
            worksheet.write(1, column + 1, '%', header_format)
        total_column = month_start_column + len(months) * 2
        worksheet.merge_range(0, total_column, 1, total_column, 'Total programado', header_format)
        worksheet.merge_range(0, total_column + 1, 1, total_column + 1, '% programado', header_format)
        worksheet.set_row(0, 25)
        worksheet.set_row(1, 20)
        worksheet.set_column(0, 0, 14)
        worksheet.set_column(1, 1, 15)
        worksheet.set_column(2, 2, 14)
        worksheet.set_column(3, 3, 42)
        worksheet.set_column(4, 4, 25)
        worksheet.set_column(5, 5, 20)
        worksheet.set_column(6, 6, 24)
        worksheet.set_column(7, 7, 30)
        worksheet.set_column(8, 8, 24)
        if months:
            worksheet.set_column(month_start_column, total_column - 1, 14)
        worksheet.set_column(total_column, total_column, 17)
        worksheet.set_column(total_column + 1, total_column + 1, 14)
        worksheet.freeze_panes(2, 3)

        monthly_totals = {month: 0.0 for month in months}
        total_order_amount = 0.0
        total_scheduled_amount = 0.0
        for row, order in enumerate(self.sorted(lambda purchase: purchase.name), start=2):
            product_line = order.order_line.filtered(lambda line: not line.display_type)[:1]
            payment_term = order.partner_id.property_supplier_payment_term_id or order.payment_term_id
            comments = '\n'.join(filter(None, order.payment_schedule_ids.mapped('notas')))
            invoices = order_invoices[order.id]
            invoice_references = ', '.join(
                filter(None, invoices.mapped('name') or invoices.mapped('ref')))
            worksheet.write(row, 0, order.name or '', text_format)
            worksheet.write_number(row, 1, order.amount_total, money_format)
            worksheet.write_datetime(row, 2, fields.Datetime.to_datetime(order.date_order), date_format)
            worksheet.write(row, 3, product_line.name if product_line else '', text_format)
            worksheet.write(row, 4, order.partner_id.display_name or '', text_format)
            if order.date_planned:
                worksheet.write_datetime(row, 5, fields.Datetime.to_datetime(order.date_planned), date_format)
            else:
                worksheet.write_blank(row, 5, None, date_format)
            worksheet.write(row, 6, payment_term.display_name if payment_term else '', text_format)
            worksheet.write(row, 7, comments, text_format)
            worksheet.write(row, 8, invoice_references, text_format)
            total_order_amount += order.amount_total

            payments_by_month = {}
            for schedule in order.payment_schedule_ids.filtered('fecha_prevista'):
                key = month_key(schedule.fecha_prevista)
                payment = payments_by_month.setdefault(key, {'amount': 0.0, 'percentage': 0.0})
                payment['amount'] += schedule.importe_a_pagar
                payment['percentage'] += (
                    schedule.importe_a_pagar / order.amount_total * 100.0
                    if order.amount_total else 0.0
                )
            scheduled_amount = sum(payment['amount'] for payment in payments_by_month.values())
            scheduled_percentage = scheduled_amount / order.amount_total if order.amount_total else 0.0
            for offset, month in enumerate(months):
                payment = payments_by_month.get(month)
                column = month_start_column + offset * 2
                if payment:
                    worksheet.write_number(row, column, payment['amount'], money_format)
                    worksheet.write_number(row, column + 1, payment['percentage'] / 100.0, percentage_format)
                    monthly_totals[month] += payment['amount']
                else:
                    worksheet.write_blank(row, column, None, month_format)
                    worksheet.write_blank(row, column + 1, None, percentage_format)
            worksheet.write_number(row, total_column, scheduled_amount, money_format)
            worksheet.write_number(row, total_column + 1, scheduled_percentage, percentage_format)
            total_scheduled_amount += scheduled_amount

        total_row = len(self) + 2
        worksheet.write(total_row, 0, 'TOTALES', total_text_format)
        worksheet.write_number(total_row, 1, total_order_amount, total_format)
        for column in range(2, month_start_column):
            worksheet.write_blank(total_row, column, None, total_text_format)
        for offset, month in enumerate(months):
            column = month_start_column + offset * 2
            monthly_amount = monthly_totals[month]
            monthly_percentage = monthly_amount / total_order_amount if total_order_amount else 0.0
            worksheet.write_number(total_row, column, monthly_amount, total_format)
            worksheet.write_number(total_row, column + 1, monthly_percentage, total_percentage_format)
        worksheet.write_number(total_row, total_column, total_scheduled_amount, total_format)
        worksheet.write_number(
            total_row,
            total_column + 1,
            total_scheduled_amount / total_order_amount if total_order_amount else 0.0,
            total_percentage_format,
        )

        workbook.close()
        filename = 'reporte_flujo_de_caja_%s.xlsx' % datetime.now().strftime('%Y%m%d_%H%M%S')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': self[0].id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }


    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.project_id:
            res.update({
                'bim_project_id': self.project_id.id,
                'bim_purchase_id': self.id,
            })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        if self.env.context.get('origin_po_id'):
            origin_po_id = self.env['purchase.order'].browse(self.env.context.get('origin_po_id'))
            if origin_po_id and origin_po_id.project_id:
                orders.project_id = origin_po_id.project_id.id
                orders.budget_id = origin_po_id.budget_id.id
                orders.concept_id = origin_po_id.concept_id.id
        return orders

    def action_margin_budget(self):
        if not self.budget_id:
            raise UserError(_("You must select a budget"))
        if self.budget_id:
            for line in self.order_line:
                product = line.product_id
                concept_ids = self.env['bim.concepts'].search([
                                            ('budget_id','=',self.budget_id.id),
                                            ('product_id','=',product.id)
                                        ])
                if concept_ids:
                    for concept in concept_ids:
                        if self.margin > 0:
                            concept.amount_fixed =  line.price_unit / ( 1 - (self.margin/100))
                        else:
                            concept.amount_fixed = line.price_unit

            # show alert message
            message = "The budget has been updated with the new product prices"
            self.message_post(body=message)
        return True

    def verify_bim_purchase_limit(self):
        for purchase in self:
            if purchase.project_id and purchase.project_id.limit_purchase and (not self.env.user.has_group('base_bim_2.group_manager_bim') or not self.env.user.has_group('base_bim_2.group_bim_purchase_not_limit')):
                for line in purchase.order_line.filtered_domain([('display_type','=',False)]):
                    line.verify_product_purchase_limit()

    def button_confirm(self):
        if self.project_id:
            if not self.project_id.state_id.create_purchase_order:
                raise UserError(_("You can't confirm a purchase order in a project that is not in the state 'Create Purchase Orders'"))

            if self.budget_id:
                if not self.budget_id.state_id.allow_supplier_purchase:
                    raise UserError(_("You can't confirm a purchase order in a budget that is not in the state 'Allow Supplier Purchase'"))

        self.verify_bim_purchase_limit()
        result = super(PurchaseOrder, self).button_confirm()

        for pick in self.picking_ids:
            pick.bim_purchase_id = self.id
            pick.bim_project_id = self.project_id.id
            pick.bim_budget_id = self.budget_id.id
            pick.bim_concept_id = self.concept_id.id

            for line in pick.move_ids:
                if line.purchase_line_id:
                    line.concept_phase_id = line.purchase_line_id.concept_phase_id.id


        for order in self:
            if order.bim_requisition_id:
                project = order.bim_requisition_id.project_id
                for pick in order.picking_ids:
                    pick.bim_project_id = project.id
                    pick.place_of_delivery_id = order.place_of_delivery_id.id
                    if not pick.bim_requisition_id:
                        pick.bim_requisition_id = order.bim_requisition_id.id

        if self.project_id:
            try:
                history_obj = self.env['bim.product.purchase']
                for line in self.order_line:
                    vals = {
                        'template_id': line.product_id.product_tmpl_id.id,
                        'product_id': line.product_id.id,
                        'date': date.today(),
                        'project_id': self.project_id.id,
                        'purchase_price': line.price_unit,
                        'purchase_id': self.id,
                        'supplier_id': self.partner_id.id,
                        'quantity': line.product_qty
                    }
                    history_obj.create(vals)
            except Exception as e:
                _logger.error(e)

        # Vamos a colocarle el proyecto al albaran de entrada
        try:
            if self.project_id and self.picking_ids:
                for picking in self.picking_ids:
                    picking.bim_project_id = self.project_id.id

        except Exception as e:
            _logger.error(e)

        return result

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            used_project_warehouse = self.company_id.use_project_warehouse
            if used_project_warehouse and self.project_id.warehouse_id:
                picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.project_id.warehouse_id.id),('code','=','incoming')],limit=1)
                if picking_type_id:
                    self.picking_type_id = picking_type_id

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.project_id:
            values.update({
                'project_id': self.project_id.id or False,
                'budget_id': self.budget_id.id or False,
                'concept_id': self.concept_id.id or False,
                'include_for_bim': self.company_id.bim_include_invoice_purchase,
                'invoice_date':  date.today(),
            })
        return values


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    bim_req_line_id = fields.Many2one('product.list', 'Requisition Line')
    project_id = fields.Many2one('bim.project', 'Project',
                 related='order_id.project_id', store=True)
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')
    partner_id = fields.Many2one('res.partner', 'Supplier', related='order_id.partner_id', store=True)

    qty_valoration = fields.Float('Qty Valoration', compute='_compute_qty_valoration')
    price_valoration = fields.Float('Price Valoration', compute='_compute_qty_valoration')
    total_oc_valoration = fields.Float('Total Valoration', compute='_compute_qty_valoration')
    qty_saldo = fields.Float('Qty Saldo', compute='_compute_qty_valoration')
    total_saldo = fields.Float('Total Saldo', compute='_compute_qty_valoration')
    percent_val = fields.Float('% Val', compute='_compute_qty_valoration')

    qty_invoice = fields.Float('Qty Invoice', compute='_compute_qty_invoice')
    price_unit_invoice = fields.Float('Price Unit Invoice', compute='_compute_qty_invoice')
    total_invoice = fields.Float('Total Invoice', compute='_compute_qty_invoice')
    state = fields.Selection(related='order_id.state', store=True)


    def _compute_qty_invoice(self):
        for rec in self:
            invoice_line = rec.env['account.move.line'].search([
                        ('purchase_line_id','=',rec.id),
                    ],limit=1)

            if invoice_line:
                rec.qty_invoice = invoice_line.quantity
                rec.price_unit_invoice = invoice_line.price_unit
                rec.total_invoice = invoice_line.price_subtotal
            else:
                rec.qty_invoice = 0
                rec.price_unit_invoice = 0
                rec.total_invoice = 0


    def _compute_qty_valoration(self):
        for rec in self:
            purchase_valuation_line = rec.env['purchase.valuation.line'].search([
                        ('purchase_id','=',rec.order_id.id),
                        ('product_id','=',rec.product_id.id),
                    ],limit=1)

            if purchase_valuation_line:
                rec.qty_valoration = purchase_valuation_line.product_qty
                rec.price_valoration = purchase_valuation_line.price_unit
                rec.total_oc_valoration = purchase_valuation_line.product_qty * purchase_valuation_line.price_unit
                rec.qty_saldo = rec.product_qty - rec.qty_valoration
                rec.total_saldo = rec.price_subtotal - rec.total_oc_valoration
                rec.percent_val = (rec.qty_valoration / rec.product_qty) * 100 if rec.product_qty > 0 else 0
            else:
                rec.qty_valoration = 0
                rec.price_valoration = 0
                rec.total_oc_valoration = 0
                rec.qty_saldo = rec.product_qty
                rec.total_saldo = rec.price_subtotal
                rec.percent_val = 0


    @api.onchange('product_id')
    def _onchange_concepts(self):
        for line in self:
            if line.order_id.project_id and line.order_id.project_id.analytic_id:
                line.analytic_distribution = {str(line.order_id.project_id.analytic_id.id): 100}

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move)
        values.update({
            'project_id': self.order_id.project_id.id or False,
            'budget_id': self.order_id.budget_id.id or False,
            'concept_phase_id' : self.concept_phase_id.id or False,
        })

        if self.order_id.project_id.analytic_id:
            analytic_distribution = {str(self.order_id.project_id.analytic_id.id): 100}
            values.update({
                'analytic_distribution': analytic_distribution or False,
            })
        return values

    def verify_product_purchase_limit(self):
        if not self.product_id or not self.order_id.project_id:
            return
        query = """select max(amount_fixed) from bim_concepts where project_id = {} and 
                    type not in ('chapter','departure') and product_id = {}
                    """.format(str(self.order_id.project_id.id),str(self.product_id.id))
        self.env.cr.execute(query)
        if self.env.cr.rowcount:
            max_price = self.env.cr.dictfetchall()
            price = max_price[0]['max']
            if price and price < self.price_unit:
                raise UserError(_("Max price for product %s is %s %s. Purchase price must be under that price")%(self.product_id.display_name,str(price),self.company_id.currency_id.symbol))

