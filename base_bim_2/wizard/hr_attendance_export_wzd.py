# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import xlwt
import base64
from io import BytesIO
from datetime import datetime


class HrAttendanceExportWzd(models.TransientModel):
    _name = 'hr.attendance.export.wzd'
    _description = 'Exportar Asistencias a Excel'


    type = fields.Selection(
        [('excel', 'Excel Básico')],
        string='Formato de Exportación',
        default='excel',
        required=True,
    )


    def action_export(self):
        if self.type != 'excel':
            raise UserError(_('Formato de exportación no soportado.'))

        self.ensure_one()

        # Obtener IDs seleccionados
        attendance_ids = self.env.context.get('active_ids', [])
        if not attendance_ids:
            raise UserError(_('No se han seleccionado registros de asistencia.'))

        attendances = self.env['hr.attendance'].browse(attendance_ids)
        if not attendances:
            raise UserError(_('No se encontraron registros de asistencia.'))

        # -------------------------------------------------------------
        #  Helper: convertir datetime Odoo → Local user → Excel float
        # -------------------------------------------------------------
        def to_excel_float(dt):
            """Convierte datetime aware de Odoo a float Excel (local user time)."""
            if not dt:
                return ""

            # Convertir a hora local del usuario
            local_dt = fields.Datetime.context_timestamp(self, dt)

            # Hacerlo naive para Excel
            local_dt = local_dt.replace(tzinfo=None)

            # Excel date base
            excel_base = datetime(1899, 12, 30)
            delta = local_dt - excel_base

            return delta.days + (delta.seconds / 86400)

        # -------------------------------------------------------------
        #  Crear Excel
        # -------------------------------------------------------------
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Horas')

        # Estilos
        header_style = xlwt.XFStyle()
        font = xlwt.Font()
        font.bold = True
        header_style.font = font

        borders = xlwt.Borders()
        borders.left = borders.right = borders.top = borders.bottom = xlwt.Borders.THIN
        header_style.borders = borders

        align = xlwt.Alignment()
        align.horz = xlwt.Alignment.HORZ_CENTER
        align.vert = xlwt.Alignment.VERT_CENTER
        header_style.alignment = align

        # Formato fecha
        date_style = xlwt.XFStyle()
        date_style.num_format_str = 'DD/MM/YYYY'
        date_style.borders = borders

        # Formato hora
        time_style = xlwt.XFStyle()
        time_style.num_format_str = 'HH:MM'
        time_style.borders = borders

        # Encabezados
        headers = ['Empleado', 'Dia', 'Entrada', 'Salida']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_style)

        worksheet.col(0).width = 256 * 30
        worksheet.col(1).width = 256 * 12
        worksheet.col(2).width = 256 * 10
        worksheet.col(3).width = 256 * 10

        # -------------------------------------------------------------
        #  Escribir líneas de asistencias
        # -------------------------------------------------------------
        row = 1
        for att in attendances.sorted(lambda a: (a.employee_id.name, a.check_in)):

            # Empleado
            worksheet.write(row, 0, att.employee_id.name or '')

            # Día
            if att.check_in:
                worksheet.write(row, 1, to_excel_float(att.check_in), date_style)
            else:
                worksheet.write(row, 1, '')

            # Entrada
            if att.check_in:
                worksheet.write(row, 2, to_excel_float(att.check_in), time_style)
            else:
                worksheet.write(row, 2, '')

            # Salida
            if att.check_out:
                worksheet.write(row, 3, to_excel_float(att.check_out), time_style)
            else:
                worksheet.write(row, 3, '')

            row += 1

        # -------------------------------------------------------------
        #  Guardar y descargar
        # -------------------------------------------------------------
        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        file_data = base64.b64encode(output.read())
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'asistencias.xls',
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.ms-excel',
            'res_model': 'hr.attendance.export.wzd',
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }