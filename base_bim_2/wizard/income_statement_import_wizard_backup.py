# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import base64
import io
import xlrd
import logging

_logger = logging.getLogger(__name__)

class IncomeStatementImportWizard(models.TransientModel):
    _name = 'income.statement.import.wizard'
    _description = 'Import Income Statement Lines from Excel'

    summary_id = fields.Many2one('income.statement.summary', string='Income Statement Summary', required=True)
    excel_file = fields.Binary(string='Excel File', required=True)
    filename = fields.Char(string='Filename')
    replace_existing = fields.Boolean(string='Replace Existing Lines', default=True,
                                     help="If checked, existing lines will be deleted before importing. Otherwise, new lines will be added.")

    def import_lines(self):
        """
        Importa las líneas desde el archivo Excel (.xls).
        """
        if not self.excel_file:
            raise ValidationError(_('Please select an Excel file to import.'))

        try:
            # Decodificar el archivo
            file_data = base64.b64decode(self.excel_file)
            file_like = io.BytesIO(file_data)
            
            # Abrir el archivo Excel usando xlrd
            workbook = xlrd.open_workbook(file_contents=file_data)
            
            # Buscar la hoja de datos
            worksheet = None
            sheet_names = workbook.sheet_names()
            
            for sheet_name in sheet_names:
                if 'Income Statement Lines' in sheet_name or 'Lines' in sheet_name:
                    worksheet = workbook.sheet_by_name(sheet_name)
                    break
            
            if not worksheet:
                # Si no encuentra la hoja específica, usar la primera
                worksheet = workbook.sheet_by_index(0)

            # Leer encabezados (primera fila)
            headers = []
            if worksheet.nrows > 0:
                for col in range(worksheet.ncols):
                    cell_value = worksheet.cell_value(0, col)
                    headers.append(str(cell_value) if cell_value else '')

            # Verificar que tenemos los encabezados mínimos necesarios
            required_headers = ['Description']
            for req_header in required_headers:
                if req_header not in headers:
                    raise ValidationError(_('Missing required column: %s') % req_header)

            # Mapear índices de columnas
            col_indices = {}
            for i, header in enumerate(headers):
                if header:
                    col_indices[header] = i

            # Si se seleccionó reemplazar, eliminar líneas existentes
            if self.replace_existing:
                self.summary_id.line_ids.unlink()

            # Leer datos línea por línea
            imported_count = 0
            for row_num in range(1, worksheet.nrows):  # Empezar desde la fila 1 (después de headers)
                # Leer todas las celdas de la fila
                row = []
                for col in range(worksheet.ncols):
                    try:
                        cell_value = worksheet.cell_value(row_num, col)
                        row.append(cell_value)
                    except xlrd.XLRDError:
                        row.append('')

                # Verificar si la fila tiene datos
                if not any(row):
                    continue

                # Verificar si llegamos a la sección de información del resumen
                if row and str(row[0]).strip() == 'Summary Information':
                    break

                # Extraer datos de la fila
                line_data = {
                    'summary_id': self.summary_id.id,
                    'sequence': self._get_cell_value_xlrd(row, col_indices, 'Sequence', 10 * row_num),
                    'description': self._get_cell_value_xlrd(row, col_indices, 'Description', ''),
                    'formula': self._get_cell_value_xlrd(row, col_indices, 'Formula', ''),
                    'total': self._get_cell_value_xlrd(row, col_indices, 'Total', 0.0),
                    'percent_total': self._get_cell_value_xlrd(row, col_indices, 'Total %', 0.0),
                    'mo': self._get_cell_value_xlrd(row, col_indices, 'MO', 0.0),
                    'percent_mo': self._get_cell_value_xlrd(row, col_indices, 'MO %', 0.0),
                    'mat': self._get_cell_value_xlrd(row, col_indices, 'MAT', 0.0),
                    'percent_mat': self._get_cell_value_xlrd(row, col_indices, 'MAT %', 0.0),
                    'eq': self._get_cell_value_xlrd(row, col_indices, 'EQ', 0.0),
                    'percent_eq': self._get_cell_value_xlrd(row, col_indices, 'EQ %', 0.0),
                    'subc': self._get_cell_value_xlrd(row, col_indices, 'SUBC', 0.0),
                    'percent_subc': self._get_cell_value_xlrd(row, col_indices, 'SUBC %', 0.0),
                }

                # Verificar que al menos tenga descripción
                if not line_data['description']:
                    continue

                # Crear la línea
                self.env['income.statement.summary.line'].create(line_data)
                imported_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Successful'),
                    'message': _('%d lines imported successfully.') % imported_count,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Error importing Excel file: {str(e)}")
            raise ValidationError(_('Error importing file: %s') % str(e))
                    col_indices[header] = i

            # Si se seleccionó reemplazar, eliminar líneas existentes
            if self.replace_existing:
                self.summary_id.line_ids.unlink()

            # Leer datos línea por línea
            imported_count = 0
            for row_num, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                # Verificar si la fila tiene datos
                if not any(row):
                    continue

                # Verificar si llegamos a la sección de información del resumen
                if row[0] and str(row[0]).strip() == 'Summary Information':
                    break

                # Extraer datos de la fila
                line_data = {
                    'summary_id': self.summary_id.id,
                    'sequence': self._get_cell_value(row, col_indices, 'Sequence', 10 * (row_num - 1)),
                    'description': self._get_cell_value(row, col_indices, 'Description', ''),
                    'formula': self._get_cell_value(row, col_indices, 'Formula', ''),
                    'total': self._get_cell_value(row, col_indices, 'Total', 0.0),
                    'percent_total': self._get_cell_value(row, col_indices, 'Total %', 0.0),
                    'mo': self._get_cell_value(row, col_indices, 'MO', 0.0),
                    'percent_mo': self._get_cell_value(row, col_indices, 'MO %', 0.0),
                    'mat': self._get_cell_value(row, col_indices, 'MAT', 0.0),
                    'percent_mat': self._get_cell_value(row, col_indices, 'MAT %', 0.0),
                    'eq': self._get_cell_value(row, col_indices, 'EQ', 0.0),
                    'percent_eq': self._get_cell_value(row, col_indices, 'EQ %', 0.0),
                    'subc': self._get_cell_value(row, col_indices, 'SUBC', 0.0),
                    'percent_subc': self._get_cell_value(row, col_indices, 'SUBC %', 0.0),
                }

                # Verificar que al menos tenga descripción
                if not line_data['description']:
                    continue

                # Crear la línea
                self.env['income.statement.summary.line'].create(line_data)
                imported_count += 1

            workbook.close()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Successful'),
                    'message': _('%d lines imported successfully.') % imported_count,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Error importing Excel file: {str(e)}")
            raise ValidationError(_('Error importing file: %s') % str(e))

    def _get_cell_value(self, row, col_indices, column_name, default_value):
        """
        Obtiene el valor de una celda específica.
        """
        try:
            if column_name in col_indices:
                col_index = col_indices[column_name]
                if col_index < len(row) and row[col_index] is not None:
                    value = row[col_index]
                    
                    # Convertir tipos según sea necesario
                    if isinstance(default_value, (int, float)):
                        try:
                            return float(value) if value else 0.0
                        except (ValueError, TypeError):
                            return 0.0
                    elif isinstance(default_value, str):
                        return str(value) if value else ''
                    else:
                        return value
            return default_value
        except Exception:
            return default_value