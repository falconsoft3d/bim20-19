# coding: utf-8
import base64
import logging
import xlwt
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from io import BytesIO
from datetime import datetime, date, timedelta
_logger = logging.getLogger(__name__)

class BimAnalysisWizard(models.TransientModel):
    _name = 'bim.analysis.wizard'
    _description = 'Buget Resource Report'

    def _default_budget(self):
        return self.env['bim.budget'].browse(self._context.get('active_id'))

    budget_id = fields.Many2one('bim.budget', "Budget", required=True, default=_default_budget)
    type = fields.Selection([
                    ('resources_for_stage', 'Resources For Stage'),
                    ('amount_resources_stages', 'Amount of Resources by stages'),
                    ('general_cash_flow', 'General Cash Flow'),
                    ('report_by_purchase_invoice_lines', 'Reporte por Líneas de Facturas de Compras'),
                ], string='Tipo', default='resources_for_stage')



    """
    02 Importe de Recursos por Etapa
    """
    def amount_resources_stages(self):
        if not self.budget_id:
            raise ValidationError(_('You must select a budget.'))

        if not self.budget_id.stage_ids:
            raise ValidationError(_('The budget has no stages.'))

        budget = self.budget_id

        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet('Importe de Recursos por Etapa')
        file_name = 'importe_recursos_etapa_' + str(budget.name).replace(" ", "_")
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on; align: wrap yes, horiz center')
        style_border_table_details_chapters = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details_departed = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')

        worksheet.write_merge(0, 0, 0, 11, _("Análisis de Recursos por Etapa"), style_title)
        worksheet.write_merge(1,1,0,2, _("Proyecto"))
        worksheet.write_merge(1,1,3,5, budget.name)
        worksheet.write_merge(1,1,6,8, _("Fecha de Impresión"))
        worksheet.write_merge(2,2,0,2, budget.project_id.nombre)
        worksheet.write_merge(2,2,3,5, budget.code)
        worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'))


        row = 4
        total = 0
        column = 0
        worksheet.write(row, column, _("Code"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Name"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("U.M"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Importe."), style_border_table_top)


        # stage
        for stage in budget.stage_ids:
            column += 1
            name_p = stage.name.replace("Stage","Etapa")
            __date_stop = stage.date_stop.strftime('%d-%m-%Y') if stage.date_stop else "-"
            worksheet.write(row, column, "P." + name_p + " ("+ __date_stop +") ", style_border_table_top)
            column += 1
            worksheet.write(row, column, "R." + name_p, style_border_table_top)

        column += 1
        worksheet.write(row, column, _("R. Total"), style_border_table_top)


        resource_ids = budget.concept_ids.filtered(lambda c: c.type in ['labor', 'equip', 'material'])


        for resource in resource_ids:
            column2 = 0
            row += 1
            worksheet.write(row, 0, resource.code, style_border_table_details_departed)
            worksheet.write(row, 1, resource.product_id.display_name, style_border_table_details_departed)
            worksheet.write(row, 2, resource.uom_id.name if resource.uom_id else "-", style_border_table_details_departed)
            worksheet.write(row, 3, resource.balance * resource.parent_id.quantity, style_border_table_details_departed)

            # stage
            column2 += 3
            total = 0

            for stage in budget.stage_ids:
                column2 += 1
                date_start = stage.date_start.strftime('%d-%m-%Y') if stage.date_start else "-"
                date_stop = stage.date_stop.strftime('%d-%m-%Y') if stage.date_stop else "-"

                departure_ids = self.env['bim.concepts'].search([
                                    ('budget_id', '=', budget.id),
                                    ('acs_date_end', '>=', stage.date_stop),
                                    ('acs_date_end', '<=', stage.date_stop),
                                ])

                qty_resource = 0
                if departure_ids:
                    for departure in departure_ids:
                        concept_ids = self.env['bim.concepts'].search([
                            ('parent_id', '=', departure.id),
                            ('id', '=', resource.id),
                        ])
                        for concept in concept_ids:
                            qty_resource += concept.balance * concept.parent_id.quantity



                worksheet.write(row, column2, qty_resource , style_border_table_details_departed)
                column2 += 1


                # real
                resource_qty = 0
                if resource.type in ['material', 'equip']:
                    # Asientos Contables
                    entry_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['entry'])
                    ])

                    # Facturas de Proveedor
                    in_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['in_invoice'])
                    ])


                    # Rectificativa de Facturas de Proveedor
                    refund_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['in_refund'])
                    ])

                    # Picking
                    stock_move_ids = self.env['stock.move'].search([
                        ('picking_id.bim_concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('picking_id.bim_budget_id', '=', budget.id),
                        ('picking_id.bim_project_id', '=', budget.project_id.id),
                        ('picking_id.state', '=', 'done'),
                        ('picking_id.include_for_bim', '=', True),
                        ('picking_id.date_done', '>=', stage.date_start),
                        ('picking_id.date_done', '<=', stage.date_stop)
                    ])

                    if in_account_move_line_ids or refund_account_move_line_ids or stock_move_ids or entry_account_move_line_ids:
                        resource_qty = sum(stock_move_ids.mapped('subtotal'))  + sum(entry_account_move_line_ids.mapped('price_subtotal')) + sum(in_account_move_line_ids.mapped('price_subtotal')) - sum(refund_account_move_line_ids.mapped('price_subtotal'))
                        total += resource_qty
                        _logger.info('total: %s', total)



                if resource.type == 'labor':
                    arra_ = [
                        ('budget_id', '=', budget.id),
                        ('concept_id', '=', resource.parent_id.id),
                        ('check_out', '>=', stage.date_start),
                        ('check_out', '<=', stage.date_stop),
                    ]

                    hr_attendance_ids = self.env['hr.attendance'].search(arra_)

                    if hr_attendance_ids:
                        resource_qty = sum(hr_attendance_ids.mapped('attendance_cost'))
                        total += resource_qty

                        _logger.info('2 resource product_id: %s', resource.product_id.display_name)
                        _logger.info('2 total: %s', total)

                worksheet.write(row, column2, resource_qty , style_border_table_details_departed)


            column2 += 1
            worksheet.write(row, column2, total, style_border_table_details_departed)



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
            'target': "self",
            'no_destroy': False,
        }



    """
    01 Análisis de Recursos por Etapa
    """
    def resources_for_stage(self):
        if not self.budget_id:
            raise ValidationError(_('You must select a budget.'))

        if not self.budget_id.stage_ids:
            raise ValidationError(_('The budget has no stages.'))

        budget = self.budget_id

        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet('Análisis de Recursos por Etapa')
        file_name = 'recursos_por_etapa_' + str(budget.name).replace(" ", "_")
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on; align: wrap yes, horiz center')
        style_border_table_details_chapters = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details_departed = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')

        worksheet.write_merge(0, 0, 0, 11, _("Análisis de Recursos por Etapa"), style_title)
        worksheet.write_merge(1,1,0,2, _("Proyecto"))
        worksheet.write_merge(1,1,3,5, budget.name)
        worksheet.write_merge(1,1,6,8, _("Fecha de Impresión"))
        worksheet.write_merge(2,2,0,2, budget.project_id.nombre)
        worksheet.write_merge(2,2,3,5, budget.code)
        worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'))


        row = 4
        total = 0
        column = 0
        worksheet.write(row, column, _("Code"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Name"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("U.M"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("P. Cant."), style_border_table_top)


        # stage
        for stage in budget.stage_ids:
            column += 1
            name_p = stage.name.replace("Stage","Etapa")
            __date_stop = stage.date_stop.strftime('%d-%m-%Y') if stage.date_stop else "-"
            worksheet.write(row, column, "P." + name_p + " ("+ __date_stop +") ", style_border_table_top)
            column += 1
            worksheet.write(row, column, "R." + name_p, style_border_table_top)

        column += 1
        worksheet.write(row, column, _("R. Total"), style_border_table_top)


        resource_ids = budget.concept_ids.filtered(lambda c: c.type in ['labor', 'equip', 'material'])


        for resource in resource_ids:
            column2 = 0
            row += 1
            worksheet.write(row, 0, resource.code, style_border_table_details_departed)
            worksheet.write(row, 1, resource.product_id.display_name, style_border_table_details_departed)
            worksheet.write(row, 2, resource.uom_id.name if resource.uom_id else "-", style_border_table_details_departed)
            worksheet.write(row, 3, resource.quantity * resource.parent_id.quantity, style_border_table_details_departed)

            # stage
            column2 += 3
            total = 0

            for stage in budget.stage_ids:
                column2 += 1
                date_start = stage.date_start.strftime('%d-%m-%Y') if stage.date_start else "-"
                date_stop = stage.date_stop.strftime('%d-%m-%Y') if stage.date_stop else "-"

                departure_ids = self.env['bim.concepts'].search([
                                    ('budget_id', '=', budget.id),
                                    ('acs_date_end', '>=', stage.date_stop),
                                    ('acs_date_end', '<=', stage.date_stop),
                                ])

                qty_resource = 0
                if departure_ids:
                    for departure in departure_ids:
                        concept_ids = self.env['bim.concepts'].search([
                            ('parent_id', '=', departure.id),
                            ('id', '=', resource.id),
                        ])
                        for concept in concept_ids:
                            qty_resource += concept.quantity * concept.parent_id.quantity



                worksheet.write(row, column2, qty_resource , style_border_table_details_departed)
                column2 += 1


                # real
                resource_qty = 0
                if resource.type in ['material', 'equip']:
                    entry_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['entry'])
                    ])


                    in_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['in_invoice'])
                    ])


                    refund_account_move_line_ids = self.env['account.move.line'].search([
                        ('concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('budget_id', '=', budget.id),
                        ('project_id', '=', budget.project_id.id),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.include_for_bim', '=', True),
                        ('move_id.invoice_date', '>=', stage.date_start),
                        ('move_id.invoice_date', '<=', stage.date_stop),
                        ('move_id.move_type', 'in', ['in_refund'])
                    ])

                    # Picking
                    stock_move_ids = self.env['stock.move'].search([
                        ('picking_id.bim_concept_id', '=', resource.parent_id.id),
                        ('product_id', '=', resource.product_id.id),
                        ('picking_id.bim_budget_id', '=', budget.id),
                        ('picking_id.bim_project_id', '=', budget.project_id.id),
                        ('picking_id.state', '=', 'done'),
                        ('picking_id.include_for_bim', '=', True),
                        ('picking_id.date_done', '>=', stage.date_start),
                        ('picking_id.date_done', '<=', stage.date_stop)
                    ])

                    if in_account_move_line_ids or refund_account_move_line_ids or stock_move_ids or entry_account_move_line_ids:
                        resource_qty = sum(stock_move_ids.mapped('quantity')) + sum(entry_account_move_line_ids.mapped('quantity')) + sum(in_account_move_line_ids.mapped('quantity')) - sum(refund_account_move_line_ids.mapped('quantity'))
                        total += resource_qty


                if resource.type == 'labor':
                    arra_ = [
                        ('budget_id', '=', budget.id),
                        ('concept_id', '=', resource.parent_id.id),
                        ('check_out', '>=', stage.date_start),
                        ('check_out', '<=', stage.date_stop),
                    ]

                    _logger.info('arra_: %s', arra_)

                    hr_attendance_ids = self.env['hr.attendance'].search(arra_)

                    _logger.info('hr_attendance_ids: %s', hr_attendance_ids)
                    _logger.info(resource.product_id.display_name)

                    if hr_attendance_ids:
                        resource_qty = sum(hr_attendance_ids.mapped('worked_hours'))
                        total += resource_qty

                worksheet.write(row, column2, resource_qty , style_border_table_details_departed)


            column2 += 1
            worksheet.write(row, column2, total, style_border_table_details_departed)



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
            'target': "self",
            'no_destroy': False,
        }


    """
    01 Report by purchase invoice lines
    """
    def report_by_purchase_invoice_lines(self):
        if not self.budget_id:
            raise ValidationError(_('You must select a budget.'))

        budget = self.budget_id

        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet('Reporte Por líneas de Facturas de Compras')
        file_name = 'reporte_linea_actura' + str(budget.name).replace(" ", "_")
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on; align: wrap yes, horiz center')
        style_border_table_details_chapters = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details_departed = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')

        worksheet.write_merge(0, 0, 0, 11, _("Reporte Por líneas de Facturas de Compras"), style_title)
        worksheet.write_merge(1,1,0,2, _("Proyecto"))
        worksheet.write_merge(1,1,3,5, budget.name)
        worksheet.write_merge(1,1,6,8, _("Fecha de Impresión"))
        worksheet.write_merge(2,2,0,2, budget.project_id.nombre)
        worksheet.write_merge(2,2,3,5, budget.code)
        worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'))


        row = 4
        total = 0
        column = 0
        worksheet.write(row, column, _("Código Capítulo"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Capítulo"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Código Partida"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Partida"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Cantidad"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Presupuesto"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Factura"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Proveedor"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Cantidad Real"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Costo"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Importe Real"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Diferencia"), style_border_table_top)


        departure_ids = budget.concept_ids.filtered(lambda c: c.type in ['departure'])


        for departure in departure_ids:
            column2 = 0
            row += 1
            worksheet.write(row, 0, departure.parent_id.code, style_border_table_details_departed)
            worksheet.write(row, 1, departure.parent_id.name, style_border_table_details_departed)
            worksheet.write(row, 2, departure.code, style_border_table_details_departed)
            worksheet.write(row, 3, departure.name, style_border_table_details_departed)
            worksheet.write(row, 4, departure.quantity, style_border_table_details_departed)
            worksheet.write(row, 5, departure.sale_amount, style_border_table_details_departed)
            worksheet.write(row, 6, "", style_border_table_details_departed)
            worksheet.write(row, 7, "", style_border_table_details_departed)
            worksheet.write(row, 8, "", style_border_table_details_departed)
            worksheet.write(row, 9, "", style_border_table_details_departed)



            # Buscamos las lineas de facturas con ese concepto
            account_move_line_ids = self.env['account.move.line'].search([
                ('concept_id', '=', departure.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.include_for_bim', '=', True),
                ('move_id.move_type', 'in', ['in_invoice'])
            ])

            if account_move_line_ids:
                _logger.info('account_move_line_ids: %s', account_move_line_ids)
                sum_price_subtotal = sum(account_move_line_ids.mapped('price_subtotal'))
                worksheet.write(row, 10, sum_price_subtotal, style_border_table_details_departed)
                worksheet.write(row, 11, departure.sale_amount - sum_price_subtotal, style_border_table_details_departed)

                for line in account_move_line_ids:
                    row += 1
                    worksheet.write(row, 0, departure.parent_id.code, style_border_table_details_departed)
                    worksheet.write(row, 1, departure.parent_id.name, style_border_table_details_departed)
                    worksheet.write(row, 2, departure.code, style_border_table_details_departed)
                    worksheet.write(row, 3, departure.name, style_border_table_details_departed)
                    worksheet.write(row, 4, "", style_border_table_details_departed)
                    worksheet.write(row, 5, "", style_border_table_details_departed)
                    worksheet.write(row, 6, line.move_id.name, style_border_table_details_departed)
                    worksheet.write(row, 7, line.move_id.partner_id.name, style_border_table_details_departed)
                    worksheet.write(row, 8, line.quantity, style_border_table_details_departed)
                    worksheet.write(row, 9, line.price_unit, style_border_table_details_departed)
                    worksheet.write(row, 10, line.price_subtotal, style_border_table_details_departed)
                    worksheet.write(row, 11, "", style_border_table_details_departed)
            else:
                worksheet.write(row, 10, "", style_border_table_details_departed)
                worksheet.write(row, 11, "", style_border_table_details_departed)

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
            'target': "self",
            'no_destroy': False,
        }




    """
    01 Análisis de Recursos por Etapa
    """
    def general_cash_flow(self):
        if not self.budget_id:
            raise ValidationError(_('You must select a budget.'))

        if not self.budget_id.stage_ids:
            raise ValidationError(_('The budget has no stages.'))

        budget = self.budget_id

        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet('Análisis de Flujo de Caja')
        file_name = 'flujo_caja_' + str(budget.name).replace(" ", "_")
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on; align: wrap yes, horiz center')
        style_border_table_details_chapters = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details_departed = xlwt.easyxf('borders: bottom thin; pattern:')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')

        worksheet.write_merge(0, 0, 0, 11, _("Flujo de Caja"), style_title)
        worksheet.write_merge(1,1,0,2, _("Proyecto"))
        worksheet.write_merge(1,1,3,5, budget.name)
        worksheet.write_merge(1,1,6,8, _("Fecha de Impresión"))
        worksheet.write_merge(2,2,0,2, budget.project_id.nombre)
        worksheet.write_merge(2,2,3,5, budget.code)
        worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'))


        row = 4
        total = 0
        column = 0
        worksheet.write(row, column, _("Code"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Name"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Category"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Journal"), style_border_table_top)
        column += 1
        worksheet.write(row, column, _("Type"), style_border_table_top)


        # stage
        for stage in budget.stage_ids:
            column += 1
            name_p = stage.name.replace("Stage","Etapa")
            __date_stop = stage.date_stop.strftime('%d-%m-%Y') if stage.date_stop else "-"
            worksheet.write(row, column, name_p, style_border_table_top)

        column += 1

        bim_cash_flow_ids = self.env['bim.cash.flow'].search([
            ('bim_budget_id', '=', budget.id),
        ])


        arr_total_stage = {}
        for cash in bim_cash_flow_ids:
            column2 = 0
            row += 1
            worksheet.write(row, 0, cash.name, style_border_table_details_departed)
            worksheet.write(row, 1, cash.note, style_border_table_details_departed)
            worksheet.write(row, 2, cash.bim_cash_flow_category_id.name, style_border_table_details_departed)
            worksheet.write(row, 3, cash.journal_id.name, style_border_table_details_departed)
            worksheet.write(row, 4, "Gasto" if cash.type == 'expense' else "Ingreso" , style_border_table_details_departed)

            # stage
            column2 += 4
            total = 0


            for stage in budget.stage_ids:
                column2 += 1
                if stage == cash.bim_budget_stage_id:
                    worksheet.write(row, column2, cash.budgeted_signed, style_border_table_details_departed)
                    if stage.id not in arr_total_stage:
                        arr_total_stage[stage.id] = 0
                    arr_total_stage[stage.id] += cash.budgeted_signed
                else:
                    worksheet.write(row, column2, 0, style_border_table_details_departed)



        _logger.info('arr_total_stage: %s', arr_total_stage)

        row += 1
        column = 0
        worksheet.write(row, column, _("Suma"), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)

        for stage in budget.stage_ids:
            column += 1
            if stage.id in arr_total_stage:
                worksheet.write(row, column, arr_total_stage[stage.id], style_border_table_details_departed)
            else:
                worksheet.write(row, column, 0, style_border_table_details_departed)

        row += 1
        column = 0
        worksheet.write(row, column, _("Acumulado"), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)
        column += 1
        worksheet.write(row, column, _(""), style_border_table_details_departed)

        accumulate = 0
        for stage in budget.stage_ids:
            column += 1
            if stage.id in arr_total_stage:
                accumulate += arr_total_stage[stage.id]
                worksheet.write(row, column, accumulate, style_border_table_details_departed)
            else:
                worksheet.write(row, column, 0, style_border_table_details_departed)



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
            'target': "self",
            'no_destroy': False,
        }


    def report_xls(self):
        _logger.info('report_xls')

        if self.type == 'resources_for_stage':
            return self.resources_for_stage()

        if self.type == 'amount_resources_stages':
            return self.amount_resources_stages()

        if self.type == 'general_cash_flow':
            return self.general_cash_flow()

        if self.type == 'report_by_purchase_invoice_lines':
            return self.report_by_purchase_invoice_lines()
