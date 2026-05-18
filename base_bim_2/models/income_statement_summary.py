# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re
import logging
import base64
import io
import xlsxwriter
import xlwt
from datetime import datetime

_logger = logging.getLogger(__name__)

class IncomeStatementSummary(models.Model):
    _description = "Income Statement Summary"
    _name = 'income.statement.summary'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char('Code', default="New", copy=False)
    title = fields.Char('Title', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    date_from = fields.Date('Date From', default=fields.Date.context_today)
    date_to = fields.Date('Date To', default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many('income.statement.summary.line', 'summary_id', string='Lines', copy=True)
    budget_id = fields.Many2one('bim.budget', string='Budget')

    def action_confirm(self):
        self.state = 'confirmed'

    def action_draft(self):
        self.state = 'draft'

    def action_cancel(self):
        self.state = 'cancelled'

    def get_column_visibility_context(self):
        """
        Retorna un contexto que indica qué columnas deben ocultarse porque están vacías.
        """
        lines = self.line_ids
        hide_mo = not any(abs(line.mo) > 0.01 for line in lines)
        hide_mat = not any(abs(line.mat) > 0.01 for line in lines)
        hide_eq = not any(abs(line.eq) > 0.01 for line in lines)
        hide_subc = not any(abs(line.subc) > 0.01 for line in lines)
        
        return {
            'hide_mo_columns': hide_mo,
            'hide_mat_columns': hide_mat,
            'hide_eq_columns': hide_eq,
            'hide_subc_columns': hide_subc,
        }

    def action_view_with_optimal_columns(self):
        """
        Abre la vista del formulario con las columnas vacías ocultas automáticamente.
        """
        context = dict(self.env.context or {})
        context.update(self.get_column_visibility_context())
        
        return {
            'type': 'ir.actions.act_window',
            'name': self.title or self.name,
            'res_model': 'income.statement.summary',
            'res_id': self.id,
            'view_mode': 'form',
            'context': context,
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('income.statement.summary') or 'New'
        return super().create(vals_list)

    def _clean_formula_for_excel(self, formula):
        """
        Limpia una fórmula para exportar a Excel, quitando el símbolo '=' de fórmulas técnicas.
        """
        if not formula:
            return ''
        
        formula = formula.strip()
        # Si la fórmula empieza con '=', quitarlo para Excel
        if formula.startswith('='):
            return formula[1:]
        
        return formula

    def export_lines_to_excel(self):
        """
        Exporta las líneas del resumen a un archivo Excel.
        """
        try:
            # Intentar usar xlsxwriter primero
            import xlsxwriter
            return self._export_with_xlsxwriter()
        except ImportError:
            try:
                # Si no está disponible, usar xlwt
                import xlwt
                return self._export_with_xlwt()
            except ImportError:
                raise ValidationError(_('Neither xlsxwriter nor xlwt libraries are installed. Please install one of them to export Excel files.'))

    def export_report_to_excel(self):
        """
        Exporta un reporte completo con datos calculados a Excel.
        Incluye todas las columnas excepto nombre técnico y fórmulas.
        """
        try:
            # Intentar usar xlsxwriter primero
            import xlsxwriter
            return self._export_report_with_xlsxwriter()
        except ImportError:
            try:
                # Si no está disponible, usar xlwt
                import xlwt
                return self._export_report_with_xlwt()
            except ImportError:
                raise ValidationError(_('Neither xlsxwriter nor xlwt libraries are installed. Please install one of them to export Excel files.'))

    def _export_with_xlsxwriter(self):
        """
        Exporta usando xlsxwriter (preferido para escritura).
        """
        import xlsxwriter
        
        # Crear un archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Income Statement Lines')

        # Definir formatos
        header_format = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'bg_color': '#4F81BD',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00'
        })

        # Escribir encabezados - Solo campos de fórmulas
        headers = [
            'Sequence', 'Description', 'Technical Name', 'Formula', 'Formula MAT', 
            'Formula MO', 'Formula EQ', 'Formula SUBC'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            if col == 1:  # Description column
                worksheet.set_column(col, col, 30)
            elif col == 2:  # Technical Name column
                worksheet.set_column(col, col, 20)
            elif col >= 3:  # Formula columns
                worksheet.set_column(col, col, 25)
            else:
                worksheet.set_column(col, col, 12)

        # Escribir datos de las líneas - Solo campos de fórmulas
        row = 1
        for line in self.line_ids.sorted('sequence'):
            worksheet.write(row, 0, line.sequence, number_format)
            worksheet.write(row, 1, line.description or '', data_format)
            worksheet.write(row, 2, line.tecnical_name or '', data_format)
            worksheet.write(row, 3, self._clean_formula_for_excel(line.formula), data_format)
            worksheet.write(row, 4, self._clean_formula_for_excel(line.formula_mat), data_format)
            worksheet.write(row, 5, self._clean_formula_for_excel(line.formula_mo), data_format)
            worksheet.write(row, 6, self._clean_formula_for_excel(line.formula_eq), data_format)
            worksheet.write(row, 7, self._clean_formula_for_excel(line.formula_subc), data_format)
            row += 1

        # Agregar información del resumen en la parte inferior
        row += 2
        worksheet.write(row, 0, 'Summary Information', header_format)
        row += 1
        worksheet.write(row, 0, 'Code:', data_format)
        worksheet.write(row, 1, self.name, data_format)
        row += 1
        worksheet.write(row, 0, 'Title:', data_format)
        worksheet.write(row, 1, self.title, data_format)
        row += 1
        worksheet.write(row, 0, 'Budget:', data_format)
        worksheet.write(row, 1, self.budget_id.name if self.budget_id else '', data_format)
        row += 1
        worksheet.write(row, 0, 'Export Date:', data_format)
        worksheet.write(row, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_format)

        workbook.close()
        output.seek(0)

        # Crear el archivo adjunto
        filename = f"income_statement_lines_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _export_with_xlwt(self):
        """
        Exporta usando xlwt (alternativa para formato .xls).
        """
        import xlwt

        # Crear un nuevo workbook
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Income Statement Lines')

        # Definir estilos
        # Estilo para encabezados
        header_style = xlwt.XFStyle()
        header_font = xlwt.Font()
        header_font.bold = True
        header_font.colour_index = xlwt.Style.colour_map['white']
        header_style.font = header_font
        
        header_pattern = xlwt.Pattern()
        header_pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        header_pattern.pattern_fore_colour = xlwt.Style.colour_map['blue']
        header_style.pattern = header_pattern
        
        header_alignment = xlwt.Alignment()
        header_alignment.horz = xlwt.Alignment.HORZ_CENTER
        header_alignment.vert = xlwt.Alignment.VERT_CENTER
        header_style.alignment = header_alignment

        # Estilo para datos de texto
        data_style = xlwt.XFStyle()
        data_alignment = xlwt.Alignment()
        data_alignment.horz = xlwt.Alignment.HORZ_LEFT
        data_style.alignment = data_alignment

        # Estilo para números
        number_style = xlwt.XFStyle()
        number_style.num_format_str = '#,##0.00'
        number_alignment = xlwt.Alignment()
        number_alignment.horz = xlwt.Alignment.HORZ_RIGHT
        number_style.alignment = number_alignment

        # Escribir encabezados - Solo campos de fórmulas
        headers = [
            'Sequence', 'Description', 'Technical Name', 'Formula', 'Formula MAT', 
            'Formula MO', 'Formula EQ', 'Formula SUBC'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_style)
            if col == 1:  # Description column
                worksheet.col(col).width = 8000
            elif col == 2:  # Technical Name column
                worksheet.col(col).width = 5000
            elif col >= 3:  # Formula columns
                worksheet.col(col).width = 6000
            else:
                worksheet.col(col).width = 3000

        # Escribir datos de las líneas - Solo campos de fórmulas
        row = 1
        for line in self.line_ids.sorted('sequence'):
            worksheet.write(row, 0, line.sequence, number_style)
            worksheet.write(row, 1, line.description or '', data_style)
            worksheet.write(row, 2, line.tecnical_name or '', data_style)
            worksheet.write(row, 3, self._clean_formula_for_excel(line.formula), data_style)
            worksheet.write(row, 4, self._clean_formula_for_excel(line.formula_mat), data_style)
            worksheet.write(row, 5, self._clean_formula_for_excel(line.formula_mo), data_style)
            worksheet.write(row, 6, self._clean_formula_for_excel(line.formula_eq), data_style)
            worksheet.write(row, 7, self._clean_formula_for_excel(line.formula_subc), data_style)
            row += 1

        # Agregar información del resumen
        row += 2
        worksheet.write(row, 0, 'Summary Information', header_style)
        
        row += 1
        worksheet.write(row, 0, 'Code:', data_style)
        worksheet.write(row, 1, self.name, data_style)
        row += 1
        worksheet.write(row, 0, 'Title:', data_style)
        worksheet.write(row, 1, self.title, data_style)
        row += 1
        worksheet.write(row, 0, 'Budget:', data_style)
        worksheet.write(row, 1, self.budget_id.name if self.budget_id else '', data_style)
        row += 1
        worksheet.write(row, 0, 'Export Date:', data_style)
        worksheet.write(row, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_style)

        # Guardar en memoria
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        # Crear el archivo adjunto
        filename = f"income_statement_lines_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.ms-excel'
        })

        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def import_lines_from_excel(self):
        """
        Abre un wizard para importar líneas desde un archivo Excel.
        """
        return {
            'name': _('Import Lines from Excel'),
            'type': 'ir.actions.act_window',
            'res_model': 'income.statement.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_summary_id': self.id}
        }

    def _export_report_with_xlsxwriter(self):
        """
        Exporta reporte completo usando xlsxwriter - todas las columnas excepto técnico y fórmulas.
        Solo muestra columnas que tienen al menos un valor diferente de 0.
        """
        import xlsxwriter
        import io
        import base64
        from datetime import datetime

        # Crear un archivo en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Income Statement Report')

        # Definir formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right',
            'border': 1
        })
        
        percent_format = workbook.add_format({
            'num_format': '0.00%',
            'align': 'right',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'align': 'left',
            'border': 1
        })

        # Determinar qué columnas mostrar basándose en si tienen valores diferentes de 0
        lines = self.line_ids
        show_mo = any(abs(line.mo) > 0.01 for line in lines)
        show_mat = any(abs(line.mat) > 0.01 for line in lines)
        show_eq = any(abs(line.eq) > 0.01 for line in lines)
        show_subc = any(abs(line.subc) > 0.01 for line in lines)

        # Construir encabezados dinámicamente
        headers = ['Sequence', 'Description', 'Total', 'Total %']
        column_widths = [12, 30, 15, 12]
        
        if show_mo:
            headers.extend(['MO', 'MO %'])
            column_widths.extend([15, 12])
        if show_mat:
            headers.extend(['MAT', 'MAT %'])
            column_widths.extend([15, 12])
        if show_eq:
            headers.extend(['EQ', 'EQ %'])
            column_widths.extend([15, 12])
        if show_subc:
            headers.extend(['SUBC', 'SUBC %'])
            column_widths.extend([15, 12])
        
        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, column_widths[col])

        # Escribir datos de las líneas
        row = 1
        for line in self.line_ids.sorted('sequence'):
            col = 0
            worksheet.write(row, col, line.sequence, number_format)
            col += 1
            worksheet.write(row, col, line.description or '', data_format)
            col += 1
            worksheet.write(row, col, line.total, number_format)
            col += 1
            worksheet.write(row, col, line.percent_total / 100, percent_format)
            col += 1
            
            if show_mo:
                worksheet.write(row, col, line.mo, number_format)
                col += 1
                worksheet.write(row, col, line.percent_mo / 100, percent_format)
                col += 1
            if show_mat:
                worksheet.write(row, col, line.mat, number_format)
                col += 1
                worksheet.write(row, col, line.percent_mat / 100, percent_format)
                col += 1
            if show_eq:
                worksheet.write(row, col, line.eq, number_format)
                col += 1
                worksheet.write(row, col, line.percent_eq / 100, percent_format)
                col += 1
            if show_subc:
                worksheet.write(row, col, line.subc, number_format)
                col += 1
                worksheet.write(row, col, line.percent_subc / 100, percent_format)
                col += 1
            row += 1

        

        workbook.close()
        output.seek(0)

        # Crear el archivo adjunto
        filename = f"income_statement_report_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _export_report_with_xlwt(self):
        """
        Exporta reporte completo usando xlwt - todas las columnas excepto técnico y fórmulas.
        Solo muestra columnas que tienen al menos un valor diferente de 0.
        """
        import xlwt
        import io
        import base64
        from datetime import datetime

        # Crear libro y hoja de trabajo
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Income Statement Report')

        # Definir estilos
        header_style = xlwt.XFStyle()
        header_font = xlwt.Font()
        header_font.bold = True
        header_font.colour_index = xlwt.Style.colour_map['white']
        header_style.font = header_font
        
        header_pattern = xlwt.Pattern()
        header_pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        header_pattern.pattern_fore_colour = xlwt.Style.colour_map['blue']
        header_style.pattern = header_pattern
        
        header_alignment = xlwt.Alignment()
        header_alignment.horz = xlwt.Alignment.HORZ_CENTER
        header_alignment.vert = xlwt.Alignment.VERT_CENTER
        header_style.alignment = header_alignment

        # Estilo para datos de texto
        data_style = xlwt.XFStyle()
        data_alignment = xlwt.Alignment()
        data_alignment.horz = xlwt.Alignment.HORZ_LEFT
        data_style.alignment = data_alignment

        # Estilo para números
        number_style = xlwt.XFStyle()
        number_style.num_format_str = '#,##0.00'
        number_alignment = xlwt.Alignment()
        number_alignment.horz = xlwt.Alignment.HORZ_RIGHT
        number_style.alignment = number_alignment

        # Estilo para porcentajes
        percent_style = xlwt.XFStyle()
        percent_style.num_format_str = '0.00%'
        percent_alignment = xlwt.Alignment()
        percent_alignment.horz = xlwt.Alignment.HORZ_RIGHT
        percent_style.alignment = percent_alignment

        # Determinar qué columnas mostrar basándose en si tienen valores diferentes de 0
        lines = self.line_ids
        show_mo = any(abs(line.mo) > 0.01 for line in lines)
        show_mat = any(abs(line.mat) > 0.01 for line in lines)
        show_eq = any(abs(line.eq) > 0.01 for line in lines)
        show_subc = any(abs(line.subc) > 0.01 for line in lines)

        # Construir encabezados dinámicamente
        headers = ['Sequence', 'Description', 'Total', 'Total %']
        column_widths = [3000, 8000, 4000, 3000]
        
        if show_mo:
            headers.extend(['MO', 'MO %'])
            column_widths.extend([4000, 3000])
        if show_mat:
            headers.extend(['MAT', 'MAT %'])
            column_widths.extend([4000, 3000])
        if show_eq:
            headers.extend(['EQ', 'EQ %'])
            column_widths.extend([4000, 3000])
        if show_subc:
            headers.extend(['SUBC', 'SUBC %'])
            column_widths.extend([4000, 3000])
        
        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_style)
            worksheet.col(col).width = column_widths[col]

        # Escribir datos de las líneas
        row = 1
        for line in self.line_ids.sorted('sequence'):
            col = 0
            worksheet.write(row, col, line.sequence, number_style)
            col += 1
            worksheet.write(row, col, line.description or '', data_style)
            col += 1
            worksheet.write(row, col, line.total, number_style)
            col += 1
            worksheet.write(row, col, line.percent_total / 100, percent_style)
            col += 1
            
            if show_mo:
                worksheet.write(row, col, line.mo, number_style)
                col += 1
                worksheet.write(row, col, line.percent_mo / 100, percent_style)
                col += 1
            if show_mat:
                worksheet.write(row, col, line.mat, number_style)
                col += 1
                worksheet.write(row, col, line.percent_mat / 100, percent_style)
                col += 1
            if show_eq:
                worksheet.write(row, col, line.eq, number_style)
                col += 1
                worksheet.write(row, col, line.percent_eq / 100, percent_style)
                col += 1
            if show_subc:
                worksheet.write(row, col, line.subc, number_style)
                col += 1
                worksheet.write(row, col, line.percent_subc / 100, percent_style)
                col += 1
            row += 1

        # Agregar información del resumen
        row += 2
        worksheet.write(row, 0, 'Report Information', header_style)
        
        row += 1
        worksheet.write(row, 0, 'Code:', data_style)
        worksheet.write(row, 1, self.name, data_style)
        row += 1
        worksheet.write(row, 0, 'Title:', data_style)
        worksheet.write(row, 1, self.title, data_style)
        row += 1
        worksheet.write(row, 0, 'Budget:', data_style)
        worksheet.write(row, 1, self.budget_id.name if self.budget_id else '', data_style)
        row += 1
        worksheet.write(row, 0, 'Report Date:', data_style)
        worksheet.write(row, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data_style)
        
        # Agregar información sobre columnas ocultas
        hidden_columns = []
        if not show_mo:
            hidden_columns.append('MO')
        if not show_mat:
            hidden_columns.append('MAT')
        if not show_eq:
            hidden_columns.append('EQ')
        if not show_subc:
            hidden_columns.append('SUBC')
        
        if hidden_columns:
            row += 1
            worksheet.write(row, 0, 'Hidden Columns (all zeros):', data_style)
            worksheet.write(row, 1, ', '.join(hidden_columns), data_style)

        # Guardar en memoria
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        # Crear el archivo adjunto
        filename = f"income_statement_report_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.ms-excel'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def calculate(self):
        """
        Calcula los valores de las líneas basándose en las fórmulas definidas.
        Las fórmulas pueden contener:
        - Referencias a modelos: modelo.campo
        - Operaciones matemáticas: +, -, *, /, ()
        - Funciones agregadas: sum(), count(), avg()
        - Referencias a nombres técnicos: =VENTAS1+ITF
        """
        for record in self:
            # Primero validar todas las fórmulas
            self._validate_formulas(record)
            
            # PASO 1: Calcular columna TOTAL usando la fórmula principal
            _logger.info("=== CALCULATING TOTAL COLUMN ===")
            self._calculate_main_formula_column(record)
            
            # PASO 2: Calcular cada columna específica independientemente
            _logger.info("=== CALCULATING SPECIFIC COLUMNS ===")
            
            # Inicializar todas las columnas específicas en 0 antes de calcular
            for line in record.line_ids:
                line.mo = 0.0
                line.mat = 0.0 
                line.eq = 0.0
                line.subc = 0.0
            
            # 2. Calcular MAT independientemente
            self._calculate_column_set(record, 'mat', 'formula_mat')
            
            # 3. Calcular MO independientemente  
            self._calculate_column_set(record, 'mo', 'formula_mo')
            
            # 4. Calcular EQ independientemente
            self._calculate_column_set(record, 'eq', 'formula_eq')
            
            # 5. Calcular SUBC independientemente
            self._calculate_column_set(record, 'subc', 'formula_subc')
            
            # PASO 3: Calcular porcentajes después de tener todos los valores
            _logger.info("=== CALCULATING PERCENTAGES ===")
            self._calculate_percentages(record)
            
            _logger.info("=== CALCULATION COMPLETED ===")

    def _calculate_main_formula_column(self, record):
        """
        Calcula la columna Total usando las fórmulas principales de cada línea.
        """
        # Obtener líneas ordenadas por secuencia
        lines = record.line_ids.sorted('sequence')
        
        # Separar líneas por tipo de fórmula
        model_formula_lines = []
        technical_formula_lines = []
        no_formula_lines = []
        
        for line in lines:
            if line.formula:
                if line.formula.strip().startswith('='):
                    technical_formula_lines.append(line)
                else:
                    model_formula_lines.append(line)
            else:
                no_formula_lines.append(line)
                line.total = 0.0  # Sin fórmula = 0
        
        # Primero calcular líneas con fórmulas de modelo (no dependen de otras líneas)
        for line in model_formula_lines:
            try:
                result = self._evaluate_formula(line.formula, record, 'total')
                line.total = result
                _logger.info(f"Model formula '{line.formula}' evaluated to: {result}")
            except Exception as e:
                _logger.error(f"Error evaluating model formula '{line.formula}': {str(e)}")
                raise ValidationError(_("Error in formula '%s': %s") % (line.formula, str(e)))
        
        # Luego calcular fórmulas técnicas para la columna Total
        self._calculate_technical_formulas(record, technical_formula_lines)

    def _calculate_technical_formulas(self, record, technical_formula_lines, column_field='total'):
        """
        Calcula las fórmulas que usan nombres técnicos de otras líneas.
        Esto se hace en múltiples iteraciones para resolver dependencias.
        """
        if not technical_formula_lines:
            return
            
        # Crear diccionario con valores actuales de todas las líneas usando la columna especificada
        line_values = {}
        for line in record.line_ids:
            if line.tecnical_name:
                line_values[line.tecnical_name] = getattr(line, column_field, 0.0)
        
        # Iterar hasta que todos los valores se estabilicen
        max_iterations = len(technical_formula_lines) * 2
        for iteration in range(max_iterations):
            any_change = False
            
            for line in technical_formula_lines:
                if line.tecnical_name and line.formula:
                    try:
                        formula = line.formula[1:].strip()  # Quitar el =

                        # PASO A: Procesar referencias con corchetes dentro de la fórmula técnica
                        evaluated_formula = formula
                        bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
                        bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
                        bracket_refs = []
                        for m in re.finditer(bracket_field_pattern, evaluated_formula):
                            bracket_refs.append(m.group(0))
                        for m in re.finditer(bracket_code_pattern, evaluated_formula):
                            bracket_refs.append(m.group(0))
                        for bracket_ref in bracket_refs:
                            if '(' in bracket_ref and ')' in bracket_ref:
                                val = self._get_bracket_asset_value(bracket_ref, record)
                            else:
                                val = self._get_bracket_model_value(bracket_ref, record)
                            evaluated_formula = evaluated_formula.replace(bracket_ref, str(val))

                        # PASO B: Reemplazar nombres técnicos con valores actuales
                        for tech_name, value in line_values.items():
                            if tech_name != line.tecnical_name:  # No usar su propio valor
                                pattern = r'\b' + re.escape(tech_name) + r'\b'
                                evaluated_formula = re.sub(pattern, str(value), evaluated_formula)

                        # Evaluar la expresión
                        allowed_names = {
                            "__builtins__": {},
                            "abs": abs,
                            "round": round,
                            "min": min,
                            "max": max,
                        }
                        result = eval(evaluated_formula, allowed_names)
                        new_value = float(result) if result is not None else 0.0
                        
                        # Verificar si el valor cambió significativamente
                        current_value = getattr(line, column_field, 0.0)
                        if abs(current_value - new_value) > 0.01:
                            setattr(line, column_field, new_value)
                            line_values[line.tecnical_name] = new_value
                            any_change = True
                            
                        _logger.info(f"Technical formula '{line.formula}' evaluated to: {new_value}")
                        
                    except Exception as e:
                        _logger.error(f"Error evaluating technical formula '{line.formula}': {str(e)}")
                        raise ValidationError(_("Error in technical formula '%s': %s") % (line.formula, str(e)))
            
            # Si no hubo cambios en esta iteración, hemos terminado
            if not any_change:
                break

    def _calculate_column_set(self, record, column_field, formula_field):
        """
        Calcula un juego de columnas (ej: MAT) completamente independiente.
        Cada juego tiene su propio contexto de nombres técnicos.
        """
        _logger.info(f"=== CALCULATING COLUMN SET: {column_field.upper()} ===")
        lines = record.line_ids.sorted('sequence')
        
        # Separar líneas con fórmulas técnicas y normales para esta columna
        technical_lines = []
        model_lines = []
        
        for line in lines:
            formula = getattr(line, formula_field, False)
            if formula and formula.strip():
                if formula.strip().startswith('='):
                    technical_lines.append(line)
                    _logger.info(f"Technical formula in {column_field}: {line.description} = {formula}")
                else:
                    model_lines.append(line)
                    _logger.info(f"Model formula in {column_field}: {line.description} = {formula}")
            else:
                # Sin fórmula específica para esta columna, mantener en 0
                setattr(line, column_field, 0.0)
        
        # 1. Calcular fórmulas de modelo primero
        for line in model_lines:
            formula = getattr(line, formula_field)
            try:
                result = self._evaluate_formula(formula, record, column_field)
                setattr(line, column_field, result)
                _logger.info(f"Model formula '{formula}' in {column_field} = {result}")
            except Exception as e:
                _logger.error(f"Error in model formula '{formula}' for {column_field}: {str(e)}")
                raise ValidationError(_("Error in %s model formula '%s': %s") % (column_field.upper(), formula, str(e)))
        
        # 2. Calcular fórmulas técnicas con contexto independiente para esta columna
        if technical_lines:
            self._calculate_column_technical_formulas_independent(record, technical_lines, column_field, formula_field)

    def _calculate_column_technical_formulas_independent(self, record, technical_lines, column_field, formula_field):
        """
        Calcula las fórmulas técnicas específicas de una columna de manera completamente independiente.
        """
        _logger.info(f"CALCULATING technical formulas for {column_field} with {len(technical_lines)} formulas")
        
        # Crear diccionario con valores de líneas para esta columna específica
        line_values = {}
        
        # Inicializar valores de líneas para esta columna
        for line in record.line_ids:
            if line.tecnical_name:
                # Solo usar el valor actual de la columna específica
                current_value = getattr(line, column_field, 0.0)
                line_values[line.tecnical_name] = current_value
                _logger.info(f"Column {column_field}: {line.tecnical_name} initial = {current_value}")
        
        # Iterar hasta que todos los valores se estabilicen
        max_iterations = len(technical_lines) * 3
        for iteration in range(max_iterations):
            any_change = False
            _logger.info(f"Column {column_field} - Iteration {iteration + 1}")
            
            for line in technical_lines:
                if line.tecnical_name:
                    formula = getattr(line, formula_field)
                    if formula and formula.strip().startswith('='):
                        try:
                            # Evaluar la fórmula técnica sin el =
                            formula_without_equals = formula[1:].strip()
                            
                            # Evaluar usando nombres técnicos con valores de la columna específica
                            result = self._evaluate_technical_name_formula_for_column(
                                formula_without_equals, record, column_field, line_values
                            )
                            new_value = float(result) if result is not None else 0.0
                            
                            # Verificar si el valor cambió significativamente
                            current_value = getattr(line, column_field, 0.0)
                            if abs(current_value - new_value) > 0.01:
                                setattr(line, column_field, new_value)
                                line_values[line.tecnical_name] = new_value
                                any_change = True
                                _logger.info(f"Column {column_field}: {line.tecnical_name} changed from {current_value} to {new_value}")
                            
                        except Exception as e:
                            _logger.error(f"Error evaluating {column_field} technical formula '{formula}': {str(e)}")
                            setattr(line, column_field, 0.0)
                            line_values[line.tecnical_name] = 0.0
            
            # Si no hubo cambios en esta iteración, hemos terminado
            if not any_change:
                _logger.info(f"Column {column_field} calculation completed after {iteration + 1} iterations")
                break

    def _evaluate_technical_name_formula_for_column(self, formula, summary_record, column_field, line_values):
        """
        Evalúa una fórmula técnica específica para una columna, usando solo los valores de esa columna.
        """
        # PASO 1: Procesar referencias con corchetes ANTES de procesar nombres técnicos
        bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
        bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
        
        # Usar finditer para obtener las coincidencias completas
        bracket_references = []
        for match in re.finditer(bracket_field_pattern, formula):
            bracket_references.append(match.group(0))
        for match in re.finditer(bracket_code_pattern, formula):
            bracket_references.append(match.group(0))
        
        # Reemplazar referencias con corchetes por sus valores
        evaluated_formula = formula
        for bracket_ref in bracket_references:
            if '(' in bracket_ref and ')' in bracket_ref:
                # Formato [modelo],(código) - buscar asset específico
                value = self._get_bracket_asset_value(bracket_ref, summary_record)
            else:
                # Formato [modelo],campo - referencia normal
                value = self._get_bracket_model_value(bracket_ref, summary_record)
            evaluated_formula = evaluated_formula.replace(bracket_ref, str(value))
        
        # PASO 2: Reemplazar nombres técnicos con valores de la columna específica
        for tech_name, value in line_values.items():
            # Usar regex para reemplazar solo palabras completas
            pattern = r'\b' + re.escape(tech_name) + r'\b'
            evaluated_formula = re.sub(pattern, str(value), evaluated_formula)
        
        # PASO 3: Evaluar la expresión matemática
        try:
            allowed_names = {
                "__builtins__": {},
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
            }
            result = eval(evaluated_formula, allowed_names)
            return float(result) if result is not None else 0.0
        except Exception as e:
            _logger.error(f"Error evaluating column technical formula '{formula}' -> '{evaluated_formula}': {str(e)}")
            raise ValidationError(_("Error in column %s technical formula '%s': %s") % (column_field.upper(), formula, str(e)))





    def _validate_formulas(self, record):
        """
        Valida que las fórmulas tengan el formato correcto antes de evaluarlas.
        """
        for line in record.line_ids:
            if line.formula:
                formula = line.formula.strip()
                
                # Si es una fórmula técnica (empieza con =)
                if formula.startswith('='):
                    self._validate_technical_formula(formula[1:], line, record)
                else:
                    # Validar fórmula de modelo
                    # IMPORTANTE: Primero buscar referencias con corchetes ANTES de reemplazar comas
                    
                    # Primero buscar y validar referencias con corchetes: [modelo],campo y [modelo],(código)
                    bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
                    bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
                    
                    bracket_field_references = re.findall(bracket_field_pattern, formula)
                    bracket_code_references = re.findall(bracket_code_pattern, formula)
                    bracket_references = bracket_field_references + bracket_code_references
                    
                    # Validar referencias con corchetes
                    for bracket_ref in bracket_references:
                        # Extraer el modelo del corchete
                        model_match = re.search(r'\[([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*)\]', bracket_ref)
                        if model_match:
                            model_name = model_match.group(1)
                            # Verificar que el modelo existe
                            if model_name not in self.env:
                                raise ValidationError(
                                    _("Model '%s' not found in line '%s'. Please check the model name.") 
                                    % (model_name, line.description)
                                )
                            
                            # Si es formato con código, validar que sea bim.budget
                            if '(' in bracket_ref and ')' in bracket_ref:
                                if model_name != 'bim.budget':
                                    raise ValidationError(
                                        _("Asset syntax [model],(code) only supported for bim.budget model in line '%s'") 
                                        % line.description
                                    )
                    
                    # Remover referencias con corchetes para buscar referencias de modelo normales
                    formula_without_brackets = formula
                    for bracket_ref in bracket_references:
                        formula_without_brackets = formula_without_brackets.replace(bracket_ref, '')
                    
                    # AHORA reemplazar comas por puntos en la fórmula sin corchetes
                    formula_without_brackets = formula_without_brackets.replace(',', '.')
                    
                    # Validar que contenga al menos un punto para separar modelo.campo
                    if '.' not in formula_without_brackets and not any(op in formula_without_brackets for op in ['+', '-', '*', '/', '(', ')']):
                        # Solo validar si no hay referencias con corchetes
                        if not bracket_references:
                            raise ValidationError(
                                _("Invalid formula format in line '%s'. Use format 'model.field' (e.g., 'bim.budget.amount_total_cd') or technical formula '=VENTAS1+10'") 
                                % line.description
                            )
                    
                    # Buscar referencias a modelos normales en la fórmula sin referencias con corchetes
                    # Patrón más estricto: debe tener al menos un punto Y el primer segmento debe ser un modelo válido
                    model_pattern = r'([a-zA-Z_][a-zA-Z0-9_.]*\.[a-zA-Z_][a-zA-Z0-9_]*)'
                    potential_references = re.findall(model_pattern, formula_without_brackets)
                    
                    # Filtrar solo las referencias que realmente parecen modelos Odoo (con punto en el nombre del modelo)
                    model_references = []
                    for ref in potential_references:
                        parts = ref.split('.')
                        # Un modelo Odoo típico tiene formato 'modulo.modelo' (ej: bim.budget, sale.order)
                        # Verificar que el primer segmento contiene al menos un punto o es un modelo conocido
                        model_name = '.'.join(parts[:-1])
                        if '.' in model_name or model_name in ['res', 'ir', 'mail', 'base']:
                            model_references.append(ref)
                    
                    # Validar cada referencia de modelo normal
                    for ref in model_references:
                            
                        parts = ref.split('.')
                        if len(parts) < 2:
                            raise ValidationError(
                                _("Invalid model reference '%s' in line '%s'. Use format 'model.field'") 
                                % (ref, line.description)
                            )
                        
                        model_name = '.'.join(parts[:-1])
                        field_name = parts[-1]
                        
                        # Verificar que el modelo existe
                        if model_name not in self.env:
                            raise ValidationError(
                                _("Model '%s' not found in line '%s'. Please check the model name.") 
                                % (model_name, line.description)
                            )
            
            # Validar también las fórmulas de las columnas específicas
            column_formulas = [
                ('formula_mat', 'MAT'),
                ('formula_mo', 'MO'),
                ('formula_eq', 'EQ'),
                ('formula_subc', 'SUBC')
            ]
            
            for formula_field, column_name in column_formulas:
                formula = getattr(line, formula_field, False)
                if formula and formula.strip():
                    formula = formula.strip()
                    
                    # Si es una fórmula técnica (empieza con =)
                    if formula.startswith('='):
                        self._validate_technical_formula(formula[1:], line, record)
                    else:
                        # Usar la misma validación que para la fórmula principal
                        # Buscar referencias con corchetes
                        bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
                        bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
                        
                        bracket_field_references = re.findall(bracket_field_pattern, formula)
                        bracket_code_references = re.findall(bracket_code_pattern, formula)
                        bracket_references = bracket_field_references + bracket_code_references
                        
                        # Validar referencias con corchetes
                        for bracket_ref in bracket_references:
                            model_match = re.search(r'\[([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*)\]', bracket_ref)
                            if model_match:
                                model_name = model_match.group(1)
                                if model_name not in self.env:
                                    raise ValidationError(
                                        _("Model '%s' not found in %s formula of line '%s'. Please check the model name.") 
                                        % (model_name, column_name, line.description)
                                    )
                                
                                if '(' in bracket_ref and ')' in bracket_ref:
                                    if model_name != 'bim.budget':
                                        raise ValidationError(
                                            _("Asset syntax [model],(code) only supported for bim.budget model in %s formula of line '%s'") 
                                            % (column_name, line.description)
                                        )

    def _validate_technical_formula(self, formula, current_line, record):
        """
        Valida una fórmula técnica que usa nombres técnicos.
        """
        # Obtener todos los nombres técnicos disponibles
        available_names = []
        for line in record.line_ids:
            if line.tecnical_name and line.id != current_line.id:
                available_names.append(line.tecnical_name)

        # Para evitar confundir referencias con corchetes (ej. [bim.budget],(HAD00007))
        # eliminarlas temporalmente antes de buscar nombres técnicos
        tmp_formula = formula
        # Remover referencias con corchetes [model],field y [model],(CODE)
        bracket_pattern = r"\[[^\]]+\],(\w+|\([^)]+\))"
        tmp_formula = re.sub(bracket_pattern, '', tmp_formula)
        # Remover referencias modelo.campo para evitar falsos positivos
        model_pattern = r'([a-zA-Z_][a-zA-Z0-9_.]*\.[a-zA-Z_][a-zA-Z0-9_]*)'
        tmp_formula = re.sub(model_pattern, '', tmp_formula)

        # Buscar referencias a nombres técnicos en la fórmula limpia
        tech_name_pattern = r'\b([A-Z_][A-Z0-9_]*)\b'
        referenced_names = re.findall(tech_name_pattern, tmp_formula)

        # Validar que todos los nombres referenciados existen
        for name in referenced_names:
            if name not in available_names and not name.isdigit():
                # Verificar si es una función matemática válida
                if name not in ['ABS', 'ROUND', 'MIN', 'MAX']:
                    raise ValidationError(
                        _("Technical name '%s' not found in line '%s'. Available names: %s") 
                        % (name, current_line.description, ', '.join(available_names))
                    )

        # Validar que la fórmula solo contenga caracteres válidos
        import string
        allowed_chars = string.ascii_letters + string.digits + '._+-*/()[], ='
        if any(char not in allowed_chars for char in formula):
            raise ValidationError(
                _("Technical formula in line '%s' contains invalid characters. Only letters, numbers, dots, math operators, and brackets are allowed.") 
                % current_line.description
            )

    def _evaluate_formula(self, formula, summary_record, column_field='total'):
        """
        Evalúa una fórmula y retorna el resultado numérico.
        
        Args:
            formula: La fórmula a evaluar
            summary_record: El registro del resumen
            column_field: Campo de columna ('total', 'mo', 'mat', 'eq', 'subc')
        
        Ejemplos de fórmulas soportadas:
        - bim.budget.amount_total_cd
        - account.move.amount_total * 1.21
        - sum(sale.order.amount_total)
        - (bim.budget.amount_planned + bim.budget.amount_extra) / 2
        - =VENTAS1+ITF (usando nombres técnicos de otras líneas)
        - =VENTAS1*0.18 (operaciones con nombres técnicos)
        """
        if not formula or not formula.strip():
            return 0.0
            
        # Limpiar la fórmula - NO reemplazar comas aún para preservar sintaxis con corchetes
        formula = formula.strip()
        
        # Si la fórmula empieza con "=" es una fórmula con referencias a nombres técnicos
        if formula.startswith('='):
            return self._evaluate_technical_name_formula(formula[1:], summary_record, column_field)
        
        # Buscar todas las referencias en la fórmula
        # Primero manejar referencias con corchetes: [modelo],campo y [modelo],(código)
        bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
        bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
        
        # Usar finditer para obtener las coincidencias completas, no solo los grupos
        bracket_references = []
        for match in re.finditer(bracket_field_pattern, formula):
            bracket_references.append(match.group(0))  # group(0) es la coincidencia completa
        for match in re.finditer(bracket_code_pattern, formula):
            bracket_references.append(match.group(0))  # group(0) es la coincidencia completa
        
        # Crear un diccionario para reemplazar las referencias por valores
        replacements = {}
        
        # Procesar referencias con corchetes
        for bracket_ref in bracket_references:
            if '(' in bracket_ref and ')' in bracket_ref:
                # Formato [modelo],(código) - buscar asset específico
                value = self._get_bracket_asset_value(bracket_ref, summary_record)
            else:
                # Formato [modelo],campo - referencia normal
                value = self._get_bracket_model_value(bracket_ref, summary_record)
            replacements[bracket_ref] = str(value)
        
        # Remover referencias con corchetes para buscar referencias de modelo normales
        formula_without_brackets = formula
        for bracket_ref in bracket_references:
            formula_without_brackets = formula_without_brackets.replace(bracket_ref, '__BRACKET_REF__')
        
        # AHORA reemplazar comas por puntos en la fórmula sin corchetes
        formula_without_brackets = formula_without_brackets.replace(',', '.')
        
        # Buscar referencias a modelos normales en la fórmula sin referencias con corchetes
        # Patrón más estricto: debe tener al menos un punto Y el primer segmento debe ser un modelo válido
        model_pattern = r'([a-zA-Z_][a-zA-Z0-9_.]*\.[a-zA-Z_][a-zA-Z0-9_]*)'
        potential_references = re.findall(model_pattern, formula_without_brackets)
        
        # Filtrar solo las referencias que realmente parecen modelos Odoo (con punto en el nombre del modelo)
        model_references = []
        for ref in potential_references:
            parts = ref.split('.')
            # Un modelo Odoo típico tiene formato 'modulo.modelo' (ej: bim.budget, sale.order)
            # Verificar que el primer segmento contiene al menos un punto o es un modelo conocido
            model_name = '.'.join(parts[:-1])
            if '.' in model_name or model_name in ['res', 'ir', 'mail', 'base']:
                model_references.append(ref)
        
        # Procesar referencias de modelo normales
        for ref in model_references:
            value = self._get_model_field_value(ref, summary_record)
            replacements[ref] = str(value)
        
        # Reemplazar las referencias en la fórmula
        evaluated_formula = formula
        for ref, value in replacements.items():
            evaluated_formula = evaluated_formula.replace(ref, value)
        
        # AHORA reemplazar comas por puntos para operaciones decimales
        evaluated_formula = evaluated_formula.replace(',', '.')
        
        # Evaluar funciones agregadas si existen
        evaluated_formula = self._evaluate_aggregate_functions(evaluated_formula, summary_record)
        
        # Evaluar la expresión matemática final
        try:
            # Usar eval de forma segura solo con operaciones matemáticas básicas
            allowed_names = {
                "__builtins__": {},
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "len": len,
            }
            result = eval(evaluated_formula, allowed_names)
            return float(result) if result is not None else 0.0
        except Exception as e:
            _logger.error(f"Error evaluating mathematical expression '{evaluated_formula}': {str(e)}")
            raise ValidationError(_("Invalid mathematical expression: %s") % evaluated_formula)

    def _evaluate_technical_name_formula(self, formula, summary_record, column_field='total', line_values=None):
        """
        Evalúa una fórmula que usa nombres técnicos de otras líneas y/o referencias con corchetes.
        
        Args:
            formula: La fórmula a evaluar
            summary_record: El registro del resumen
            column_field: Campo de columna ('total', 'mo', 'mat', 'eq', 'subc')
        
        Ejemplos:
        - VENTAS1+ITF (usa columna especificada)
        - VENTAS1*0.18
        - (VENTAS1+VENTAS2)*1.21
        - [bim.budget],(HAD00007)*2
        - VENTAS1+[bim.budget],amount_total_cd
        """
        
        # PASO 1: Procesar referencias con corchetes ANTES de procesar nombres técnicos
        bracket_field_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],[a-zA-Z_][a-zA-Z0-9_]*'
        bracket_code_pattern = r'\[[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*\],\([A-Z0-9_]+\)'
        
        # Usar finditer para obtener las coincidencias completas
        bracket_references = []
        for match in re.finditer(bracket_field_pattern, formula):
            bracket_references.append(match.group(0))
        for match in re.finditer(bracket_code_pattern, formula):
            bracket_references.append(match.group(0))
        
        # Reemplazar referencias con corchetes por sus valores
        evaluated_formula = formula
        for bracket_ref in bracket_references:
            if '(' in bracket_ref and ')' in bracket_ref:
                # Formato [modelo],(código) - buscar asset específico
                value = self._get_bracket_asset_value(bracket_ref, summary_record)
            else:
                # Formato [modelo],campo - referencia normal
                value = self._get_bracket_model_value(bracket_ref, summary_record)
            evaluated_formula = evaluated_formula.replace(bracket_ref, str(value))
        
        # PASO 2: Si no se pasa line_values, crear un diccionario con los valores de líneas por nombre técnico
        if line_values is None:
            lines = summary_record.line_ids.sorted('sequence')
            line_values = {}
            
            # Obtener valores de líneas usando la columna especificada
            for line in lines:
                if line.tecnical_name:
                    # Usar el valor de la columna especificada
                    value = getattr(line, column_field, 0.0)
                    line_values[line.tecnical_name] = value
        
        # PASO 3: Reemplazar nombres técnicos con valores de la columna especificada
        for tech_name, value in line_values.items():
            # Usar regex para reemplazar solo palabras completas
            pattern = r'\b' + re.escape(tech_name) + r'\b'
            evaluated_formula = re.sub(pattern, str(value), evaluated_formula)
        
        # PASO 4: Evaluar la expresión matemática
        try:
            allowed_names = {
                "__builtins__": {},
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
            }
            result = eval(evaluated_formula, allowed_names)
            return float(result) if result is not None else 0.0
        except Exception as e:
            _logger.error(f"Error evaluating technical formula '{formula}' -> '{evaluated_formula}': {str(e)}")
            raise ValidationError(_("Error in technical formula '%s': %s") % (formula, str(e)))

    def _get_model_field_value(self, model_field_ref, summary_record):
        """
        Obtiene el valor de un campo de un modelo específico.
        
        Args:
            model_field_ref (str): Referencia en formato 'modelo.campo' o '[modelo],campo'
            summary_record: Registro del resumen para obtener contexto (fechas, budget, etc.)
        
        Returns:
            float: Valor del campo
        
        Formatos soportados:
        - bim.budget.amount_total_cd (formato normal)
        - [bim.budget],amount_total_cd (formato con corchetes para evitar ambigüedades)
        """
        try:
            # Verificar si es el formato especial con corchetes
            if '[' in model_field_ref and '],' in model_field_ref:
                if '(' in model_field_ref and ')' in model_field_ref:
                    # Formato [modelo],(código)
                    return self._get_bracket_asset_value(model_field_ref, summary_record)
                else:
                    # Formato [modelo],campo
                    return self._get_bracket_model_value(model_field_ref, summary_record)
            
            parts = model_field_ref.split('.')
            if len(parts) < 2:
                raise ValidationError(_("Invalid model reference format: %s") % model_field_ref)
            
            model_name = '.'.join(parts[:-1])
            field_name = parts[-1]
            
            # Verificar si el modelo existe
            if model_name not in self.env:
                raise ValidationError(_("Model '%s' not found") % model_name)
            
            model = self.env[model_name]
            
            # Si es bim.budget y tenemos un budget_id específico, usar ese registro directamente
            if model_name == 'bim.budget' and summary_record.budget_id:
                budget_record = summary_record.budget_id
                if field_name in budget_record._fields:
                    field_value = getattr(budget_record, field_name, 0)
                    if isinstance(field_value, (int, float)):
                        return field_value
                    elif hasattr(field_value, 'id'):  # Many2one field
                        return 1  # Contar como 1 si existe la relación
                    else:
                        return 0.0
                else:
                    raise ValidationError(_("Field '%s' not found in model '%s'") % (field_name, model_name))
            
            # Para otros modelos, construir dominio de búsqueda
            domain = self._build_domain_for_model(model_name, summary_record)
            
            # Buscar registros
            records = model.search(domain)
            
            if not records:
                _logger.warning(f"No records found for model '{model_name}' with domain {domain}")
                return 0.0
            
            # Verificar si el campo existe en el modelo
            if field_name not in model._fields:
                raise ValidationError(_("Field '%s' not found in model '%s'") % (field_name, model_name))
            
            # Si hay múltiples registros, sumar los valores del campo
            total_value = 0.0
            for record in records:
                field_value = getattr(record, field_name, 0)
                if isinstance(field_value, (int, float)):
                    total_value += field_value
                elif hasattr(field_value, 'id'):  # Many2one field
                    total_value += 1  # Contar como 1 si existe la relación
            
            return total_value
            
        except Exception as e:
            _logger.error(f"Error getting value for '{model_field_ref}': {str(e)}")
            raise ValidationError(_("Error accessing '%s': %s") % (model_field_ref, str(e)))

    def _get_bracket_model_value(self, model_field_ref, summary_record):
        """
        Obtiene el valor de un modelo usando la sintaxis [modelo],campo.
        
        Args:
            model_field_ref (str): Referencia en formato '[modelo],campo'
            summary_record: Registro del resumen
            
        Returns:
            float: Valor del campo del modelo
            
        Ejemplo:
            [bim.budget],amount_total_cd - Busca el campo amount_total_cd del modelo bim.budget
        """
        try:
            # Extraer el modelo y campo usando corchetes (solo formato [modelo],campo, no códigos)
            bracket_pattern = r'\[([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*)\],([a-zA-Z_][a-zA-Z0-9_]+)$'
            match = re.search(bracket_pattern, model_field_ref)
            
            if not match:
                raise ValidationError(_("Invalid bracket model reference format: %s. Use [model],field") % model_field_ref)
            
            model_name = match.group(1)
            field_name = match.group(2)
            
            # Usar la misma lógica que _get_model_field_value pero with la referencia construida
            constructed_ref = f"{model_name}.{field_name}"
            return self._get_model_field_value(constructed_ref, summary_record)
            
        except ValidationError:
            raise
        except Exception as e:
            _logger.error(f"Error getting bracket model value for '{model_field_ref}': {str(e)}")
            return 0.0

    def _get_bracket_asset_value(self, model_field_ref, summary_record):
        """
        Obtiene el valor de un asset específico usando la sintaxis [modelo],(código).
        
        Args:
            model_field_ref (str): Referencia en formato '[modelo],(código)'
            summary_record: Registro del resumen
            
        Returns:
            float: Valor del asset
            
        Ejemplo:
            [bim.budget],(HAD00007) - Busca el asset con código HAD00007 en bim.budget.assets
        """
        try:
            # Extraer el modelo y código usando corchetes
            bracket_asset_pattern = r'\[([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*)\],\(([A-Z0-9_]+)\)'
            match = re.search(bracket_asset_pattern, model_field_ref)
            
            if not match:
                raise ValidationError(_("Invalid bracket asset reference format: %s. Use [model],(code)") % model_field_ref)
            
            model_name = match.group(1)
            asset_code = match.group(2)
            
            # Validar que el modelo es bim.budget
            if model_name != 'bim.budget':
                raise ValidationError(_("Asset syntax [model],(code) only supported for bim.budget model"))
            
            if not summary_record.budget_id:
                _logger.warning(f"No budget specified for asset code '{asset_code}'")
                return 0.0
            
            # Verificar si el modelo bim.budget.assets existe
            if 'bim.budget.assets' not in self.env:
                raise ValidationError(_("Model 'bim.budget.assets' not found"))
            
            # Primero buscar el asset en bim.assets por el código
            if 'bim.assets' not in self.env:
                raise ValidationError(_("Model 'bim.assets' not found"))
            
            # Buscar el asset por su código/name
            asset_master = self.env['bim.assets'].search([('name', '=', asset_code)], limit=1)
            
            if not asset_master:
                _logger.warning(f"Asset with code '{asset_code}' not found in bim.assets")
                return 0.0
            
            # Ahora buscar la relación en bim.budget.assets
            asset_domain = [
                ('budget_id', '=', summary_record.budget_id.id),
                ('asset_id', '=', asset_master.id)  # Asumo que el campo de relación se llama asset_id
            ]
            
            asset_record = self.env['bim.budget.assets'].search(asset_domain, limit=1)
            
            if not asset_record:
                _logger.warning(f"Asset '{asset_code}' not found in budget '{summary_record.budget_id.name}'")
                return 0.0
            
            # SIEMPRE usar el campo 'value' primero, luego otros campos como fallback
            if 'value' in asset_record._fields:
                field_value = getattr(asset_record, 'value', 0)
                if isinstance(field_value, (int, float)):
                    return field_value
            
            # Solo como fallback, verificar otros campos comunes (pero NO total)
            value_fields = ['haber', 'debe', 'amount', 'price', 'cost', 'amount_total']
            
            for field in value_fields:
                if field in asset_record._fields:
                    field_value = getattr(asset_record, field, 0)
                    if isinstance(field_value, (int, float)) and field_value != 0:
                        return field_value
            
            # Si no se encuentra ningún campo de valor, usar el primer campo numérico disponible
            for field_name, field_obj in asset_record._fields.items():
                if field_obj.type in ['float', 'monetary'] and field_name not in ['id', 'sequence', 'total']:
                    field_value = getattr(asset_record, field_name, 0)
                    if isinstance(field_value, (int, float)) and field_value != 0:
                        return field_value
            
            _logger.warning(f"Asset '{asset_code}' found but no numeric value fields available")
            return 0.0
            
        except ValidationError:
            raise
        except Exception as e:
            _logger.error(f"Error getting bracket asset value for '{model_field_ref}': {str(e)}")
            return 0.0

    def _build_domain_for_model(self, model_name, summary_record):
        """
        Construye un dominio de búsqueda para el modelo basado en el contexto del resumen.
        
        Args:
            model_name (str): Nombre del modelo
            summary_record: Registro del resumen
            
        Returns:
            list: Dominio de búsqueda
        """
        domain = []
        
        # Agregar filtros de fecha si están disponibles
        if summary_record.date_from and summary_record.date_to:
            # Intentar diferentes campos de fecha comunes
            date_fields = ['date', 'create_date', 'write_date', 'date_order', 'date_invoice']
            
            model = self.env[model_name]
            for date_field in date_fields:
                if date_field in model._fields:
                    domain.extend([
                        (date_field, '>=', summary_record.date_from),
                        (date_field, '<=', summary_record.date_to)
                    ])
                    break
        
        # Agregar filtro de compañía si existe en el modelo
        if summary_record.company_id:
            model = self.env[model_name]
            if 'company_id' in model._fields:
                domain.append(('company_id', '=', summary_record.company_id.id))
        
        # Agregar filtro de presupuesto si está disponible y es relevante
        if summary_record.budget_id and model_name in ['bim.budget', 'bim.concepts', 'bim.object']:
            if model_name == 'bim.budget':
                domain.append(('id', '=', summary_record.budget_id.id))
            elif 'budget_id' in self.env[model_name]._fields:
                domain.append(('budget_id', '=', summary_record.budget_id.id))
        
        # Agregar filtros específicos por modelo
        domain.extend(self._get_model_specific_domain(model_name, summary_record))
        
        return domain

    def _get_model_specific_domain(self, model_name, summary_record):
        """
        Retorna dominios específicos para ciertos modelos.
        """
        domain = []
        
        if model_name == 'account.move':
            # Solo facturas confirmadas
            domain.append(('state', '=', 'posted'))
            
        elif model_name == 'sale.order':
            # Solo órdenes de venta confirmadas
            domain.append(('state', 'in', ['sale', 'done']))
            
        elif model_name == 'purchase.order':
            # Solo órdenes de compra confirmadas
            domain.append(('state', 'in', ['purchase', 'done']))
            
        elif model_name.startswith('bim.'):
            # Para modelos BIM, filtrar por estado activo si existe
            model = self.env[model_name]
            if 'active' in model._fields:
                domain.append(('active', '=', True))
            if 'state' in model._fields:
                # Excluir estados cancelados/borrador dependiendo del modelo
                if model_name in ['bim.budget', 'bim.object']:
                    domain.append(('state', '!=', 'cancel'))
        
        return domain

    def _evaluate_aggregate_functions(self, formula, summary_record):
        """
        Evalúa funciones agregadas como sum(), count(), avg() en la fórmula.
        """
        # Patrón para funciones agregadas: función(modelo.campo)
        function_pattern = r'(sum|count|avg|min|max)\(([^)]+)\)'
        
        def replace_function(match):
            func_name = match.group(1)
            param = match.group(2).strip()
            
            try:
                if func_name == 'sum':
                    return str(self._get_model_field_value(param, summary_record))
                elif func_name == 'count':
                    # Para count, solo necesitamos el número de registros
                    parts = param.split('.')
                    model_name = '.'.join(parts[:-1])
                    domain = self._build_domain_for_model(model_name, summary_record)
                    count = self.env[model_name].search_count(domain)
                    return str(count)
                elif func_name == 'avg':
                    total = self._get_model_field_value(param, summary_record)
                    parts = param.split('.')
                    model_name = '.'.join(parts[:-1])
                    domain = self._build_domain_for_model(model_name, summary_record)
                    count = self.env[model_name].search_count(domain)
                    return str(total / count if count > 0 else 0)
                elif func_name in ['min', 'max']:
                    # Para min/max necesitamos obtener todos los valores
                    parts = param.split('.')
                    model_name = '.'.join(parts[:-1])
                    field_name = parts[-1]
                    domain = self._build_domain_for_model(model_name, summary_record)
                    records = self.env[model_name].search(domain)
                    values = [getattr(r, field_name, 0) for r in records if isinstance(getattr(r, field_name, 0), (int, float))]
                    if values:
                        return str(min(values) if func_name == 'min' else max(values))
                    return '0'
            except Exception as e:
                _logger.error(f"Error evaluating function {func_name}({param}): {str(e)}")
                return '0'
        
        return re.sub(function_pattern, replace_function, formula)

    def _calculate_percentages(self, record):
        """
        Calcula los porcentajes de cada columna basándose en la primera fila (típicamente Ventas).
        """
        # Obtener las líneas ordenadas por secuencia
        lines = record.line_ids.sorted('sequence')
        
        if not lines:
            return
        
        # Usar la primera fila como base para los cálculos de porcentaje
        first_line = lines[0]
        base_total = first_line.total
        base_mo = first_line.mo
        base_mat = first_line.mat
        base_eq = first_line.eq
        base_subc = first_line.subc
        
        # Calcular porcentajes para cada línea basándose en la primera fila
        for i, line in enumerate(lines):
            # La primera fila (índice 0) siempre tiene 0% en todos los campos
            if i == 0:
                line.percent_total = 0.0
                line.percent_mo = 0.0
                line.percent_mat = 0.0
                line.percent_eq = 0.0
                line.percent_subc = 0.0
            else:
                # Para las demás filas, calcular porcentajes basándose en la primera fila
                # Porcentaje de Total basado en la primera fila
                if base_total != 0:
                    line.percent_total = (line.total / base_total) * 100
                else:
                    line.percent_total = 0.0
                
                # Porcentaje de MO basado en la primera fila
                if base_mo != 0:
                    line.percent_mo = (line.mo / base_mo) * 100
                else:
                    line.percent_mo = 0.0 if line.mo == 0 else 100.0
                
                # Porcentaje de MAT basado en la primera fila
                if base_mat != 0:
                    line.percent_mat = (line.mat / base_mat) * 100
                else:
                    line.percent_mat = 0.0 if line.mat == 0 else 100.0
                
                # Porcentaje de EQ basado en la primera fila
                if base_eq != 0:
                    line.percent_eq = (line.eq / base_eq) * 100
                else:
                    line.percent_eq = 0.0 if line.eq == 0 else 100.0
                
                # Porcentaje de SUBC basado en la primera fila
                if base_subc != 0:
                    line.percent_subc = (line.subc / base_subc) * 100
                else:
                    line.percent_subc = 0.0 if line.subc == 0 else 100.0


class IncomeStatementSummaryLine(models.Model):
    _description = "Income Statement Summary Line"
    _name = 'income.statement.summary.line'

    summary_id = fields.Many2one('income.statement.summary', string='Income Statement Summary', required=True, ondelete='cascade')
    description = fields.Char('Description', required=True)
    formula = fields.Text('FT')
    formula_mo = fields.Text('FMO')
    formula_mat = fields.Text('FMAT')
    formula_eq = fields.Text('FEQ')
    formula_subc = fields.Text('FSUBC')
    sequence = fields.Float('Sequence', default=1)
    tecnical_name = fields.Char('Tecnical Name')

    total = fields.Float('Total')
    percent_total = fields.Float('Total %')

    mo = fields.Float('MO')
    percent_mo = fields.Float('MO %')

    mat = fields.Float('MAT')
    percent_mat = fields.Float('MAT %')

    eq = fields.Float('EQ')
    percent_eq = fields.Float('EQ %')

    subc = fields.Float('SUBC')
    percent_subc = fields.Float('SUBC %')

    @api.onchange('description')
    def onchange_name(self):
        for line in self:
            if line.description:
                line.tecnical_name = line.description.upper().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "").replace("/", "").replace("\\", "").replace(".", "").replace("*", "").replace("+", "").replace("&", "")
            else:
                line.tecnical_name = False

    @api.constrains('formula')
    def _check_formula_format(self):
        """
        Valida el formato básico de las fórmulas al guardar.
        """
        for line in self:
            if line.formula:
                formula = line.formula.strip()
                
                # Si es una fórmula técnica (empieza con =)
                if formula.startswith('='):
                    tech_formula = formula[1:].strip()
                    # Verificar que no esté vacía
                    if not tech_formula:
                        raise ValidationError(
                            _("Technical formula in line '%s' cannot be empty after '='") 
                            % line.description
                        )
                    
                    # Verificar caracteres válidos para fórmulas técnicas
                    import string
                    allowed_chars = string.ascii_letters + string.digits + '._+-*/()[], ='
                    if any(char not in allowed_chars for char in tech_formula):
                        raise ValidationError(
                            _("Technical formula in line '%s' contains invalid characters. Only letters, numbers, dots, math operators, and brackets are allowed.") 
                            % line.description
                        )
                else:
                    # Fórmula de modelo - convertir comas a puntos PERO preservar sintaxis con corchetes
                    # Detectar referencias con corchetes ANTES del reemplazo
                    bracket_pattern = r'\[([^\]]+)\],(\w+|\([^)]+\))'
                    bracket_matches = list(re.finditer(bracket_pattern, formula))
                    
                    # Aplicar reemplazo de comas solo en partes que NO son referencias con corchetes
                    if bracket_matches:
                        # Hay referencias con corchetes - procesar cuidadosamente
                        result_formula = ""
                        last_end = 0
                        
                        for match in bracket_matches:
                            # Agregar texto antes del corchete (con reemplazo de comas)
                            before_bracket = formula[last_end:match.start()]
                            result_formula += before_bracket.replace(',', '.')
                            
                            # Agregar la referencia con corchetes SIN modificar
                            result_formula += match.group(0)
                            last_end = match.end()
                        
                        # Agregar texto después del último corchete (con reemplazo de comas)
                        after_bracket = formula[last_end:]
                        result_formula += after_bracket.replace(',', '.')
                        
                        formula = result_formula
                    else:
                        # No hay referencias con corchetes - reemplazo normal
                        formula = formula.replace(',', '.')
                    
                    # Verificar formato básico
                    if formula and '.' not in formula and not any(op in formula for op in ['+', '-', '*', '/', '(', ')']):
                        raise ValidationError(
                            _("Invalid formula format in line '%s'. Use format 'model.field' (e.g., 'bim.budget.amount_total_cd') or technical formula '=VENTAS1+10'") 
                            % line.description
                        )
                    
                    # Verificar que no tenga caracteres extraños
                    import string
                    allowed_chars = string.ascii_letters + string.digits + '._+-*/()[], ='
                    if any(char not in allowed_chars for char in formula):
                        raise ValidationError(
                            _("Formula in line '%s' contains invalid characters. Only letters, numbers, dots, math operators, and brackets are allowed.") 
                            % line.description
                        )