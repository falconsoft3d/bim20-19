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

    def _process_formula_for_import(self, formula):
        """
        Procesa una fórmula al importar desde Excel, agregando el símbolo '=' 
        si parece ser una fórmula técnica (contiene nombres técnicos en mayúsculas).
        """
        if not formula or not isinstance(formula, str):
            return ''
        
        formula = formula.strip()
        if not formula:
            return ''
            
        # Si ya tiene el símbolo '=', no hacer nada
        if formula.startswith('='):
            _logger.info(f"Fórmula ya tiene '=': {formula}")
            return formula
            
        # Detectar si es una fórmula técnica
        import re
        
        # 1. Buscar nombres técnicos en mayúsculas (al menos 2 caracteres)
        technical_names = re.findall(r'\b[A-Z][A-Z0-9_]*\b', formula)
        has_technical_names = len(technical_names) > 0
        
        # 2. Operadores matemáticos
        math_operators = ['+', '-', '*', '/', '(', ')']
        has_math_operators = any(op in formula for op in math_operators)
        
        # 3. Referencias con corchetes [modelo],(codigo)
        has_bracket_refs = bool(re.search(r'\[[^\]]+\],\([^)]+\)', formula))
        
        # 4. Detectar si es una referencia de modelo (tiene punto y no mayúsculas)
        has_model_reference = '.' in formula and not has_technical_names
        
        _logger.info(f"Analizando fórmula: '{formula}'")
        _logger.info(f"  - Nombres técnicos encontrados: {technical_names}")
        _logger.info(f"  - Tiene operadores matemáticos: {has_math_operators}")
        _logger.info(f"  - Tiene referencias con corchetes: {has_bracket_refs}")
        _logger.info(f"  - Es referencia de modelo: {has_model_reference}")
        
        # Decisión: agregar '=' si:
        # 1. Tiene referencias con corchetes (siempre fórmula técnica)
        # 2. Tiene nombres técnicos (sin importar si tiene operadores)
        # 3. NO es una referencia de modelo simple
        
        should_add_equals = False
        reason = ""
        
        if has_bracket_refs:
            should_add_equals = True
            reason = "tiene referencias con corchetes"
        elif has_technical_names and not has_model_reference:
            should_add_equals = True
            reason = f"tiene nombres técnicos: {', '.join(technical_names)}"
        elif has_model_reference:
            should_add_equals = False
            reason = "es referencia de modelo"
        
        if should_add_equals:
            result = '=' + formula
            _logger.info(f"  -> AGREGANDO '=' porque {reason}: '{result}'")
            return result
        else:
            _logger.info(f"  -> NO agregando '=' porque {reason}: '{formula}'")
            return formula

    def import_lines(self):
        """
        Importa las líneas desde el archivo Excel (.xls).
        """
        if not self.excel_file:
            raise ValidationError(_('Please select an Excel file to import.'))

        # Probar la función de procesamiento con algunos ejemplos
        test_formulas = [
            "VENTAS1*0.18", 
            "ITF", 
            "VENTAS1+ITF", 
            "bim.budget.amount_total_cd",
            "[bim.budget],(BB001)*-1",
            "([bim.budget],vtmat*VENTAS1/100"
        ]
        _logger.info("=== PROBANDO DETECCIÓN DE FÓRMULAS ===")
        for test_formula in test_formulas:
            result = self._process_formula_for_import(test_formula)
            _logger.info(f"TEST: '{test_formula}' -> '{result}'")
        _logger.info("=== FIN PRUEBAS ===")

        try:
            # Decodificar el archivo
            file_data = base64.b64decode(self.excel_file)
            
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
            
            # Log para debuggear los headers encontrados
            _logger.info(f"Headers encontrados: {headers}")
            _logger.info(f"Índices de columnas: {col_indices}")

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

                # Extraer datos de la fila - Solo campos de fórmulas
                line_data = {
                    'summary_id': self.summary_id.id,
                    'sequence': self._get_cell_value_xlrd(row, col_indices, 'Sequence', 10 * row_num),
                    'description': self._get_cell_value_xlrd(row, col_indices, 'Description', ''),
                    'tecnical_name': self._get_cell_value_xlrd(row, col_indices, 'Technical Name', ''),
                    'formula': self._process_formula_for_import(self._get_cell_value_xlrd(row, col_indices, 'Formula', '')),
                    'formula_mat': self._process_formula_for_import(self._get_cell_value_xlrd(row, col_indices, 'Formula MAT', '')),
                    'formula_mo': self._process_formula_for_import(self._get_cell_value_xlrd(row, col_indices, 'Formula MO', '')),
                    'formula_eq': self._process_formula_for_import(self._get_cell_value_xlrd(row, col_indices, 'Formula EQ', '')),
                    'formula_subc': self._process_formula_for_import(self._get_cell_value_xlrd(row, col_indices, 'Formula SUBC', '')),
                }

                # Log para debuggear los datos de cada línea - solo si hay fórmulas
                has_formulas = any([line_data.get('formula'), line_data.get('formula_mat'), 
                                  line_data.get('formula_mo'), line_data.get('formula_eq'), 
                                  line_data.get('formula_subc')])
                if has_formulas:
                    _logger.info(f"FILA CON FÓRMULAS {row_num}: {line_data}")
                    # Log específico para cada fórmula procesada
                    for formula_field in ['formula', 'formula_mat', 'formula_mo', 'formula_eq', 'formula_subc']:
                        if line_data.get(formula_field):
                            _logger.info(f"  {formula_field}: '{line_data[formula_field]}'")
                else:
                    _logger.info(f"Fila {row_num}: {line_data['description']} - Sin fórmulas")

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

    def _get_cell_value_xlrd(self, row, col_indices, column_name, default_value):
        """
        Obtiene el valor de una celda específica usando xlrd.
        """
        try:
            if column_name in col_indices:
                col_index = col_indices[column_name]
                if col_index < len(row) and row[col_index] is not None:
                    value = row[col_index]
                    
                    # Log detallado para todas las fórmulas
                    if column_name.startswith('Formula'):
                        _logger.info(f"LEYENDO CELDA {column_name}: valor='{value}' tipo={type(value)} es_vacio={value == 0.0 or value == ''}")
                    
                    # Para campos de fórmula, convertir siempre a string
                    if column_name.startswith('Formula') or column_name == 'Technical Name':
                        # Si es 0.0 (celda vacía en Excel), devolver string vacío
                        if value == 0.0 or value == '':
                            _logger.info(f"  -> Celda vacía para {column_name}, devolviendo string vacío")
                            return ''
                        result = str(value)
                        _logger.info(f"  -> Convirtiendo a string para {column_name}: '{result}'")
                        return result
                    
                    # Convertir tipos según sea necesario para otros campos
                    if isinstance(default_value, (int, float)):
                        try:
                            return float(value) if value else 0.0
                        except (ValueError, TypeError):
                            return 0.0
                    elif isinstance(default_value, str):
                        return str(value) if value else ''
                    else:
                        return value
            else:
                # Log cuando no se encuentra la columna
                if column_name.startswith('Formula'):
                    _logger.warning(f"Columna '{column_name}' no encontrada en col_indices: {list(col_indices.keys())}")
            return default_value
        except Exception as e:
            _logger.error(f"Error extrayendo {column_name}: {str(e)}")
            return default_value