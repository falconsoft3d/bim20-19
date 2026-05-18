import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import os
import tempfile
import csv
import xlrd
from odoo import fields, models, _, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)
import re
import io

MS_PREDECESSOR_MAPPING = {
    '0': 'ff',
    '1': 'fs',
    '2': 'sf',
    '3': 'ss',
}


class BimGanttImport(models.TransientModel):
    _name = 'bim.gantt.import'
    _description = 'Import Gantt'

    budget_id = fields.Many2one('bim.budget', 'Budget')
    filename = fields.Char('XML File Name')
    xml_file = fields.Binary('XML File')
    excel_file = fields.Binary('Excel File')
    csv_file = fields.Binary('Csv File')
    gantt_type = fields.Selection([
                                   ('ms', 'Microsoft Project'),
                                   ('csv', 'CSV'),
                                   ('excel','XLS (20/06/2024)'),
                                   ('2000','XLS (2000)'),
                                   ], 'Gantt Type', default='ms', required=True)
    create_missing = fields.Boolean()
    import_stages = fields.Boolean()
    stage_id = fields.Many2one('bim.budget.stage', 'Stage', domain="[('budget_id', '=', budget_id)]")
    allow_certification = fields.Boolean(related='budget_id.state_id.allow_certification')

    def action_import_gantt(self):
        self.budget_id.do_compute = False
        if self.gantt_type == 'ms':
            return self.load_gantt_ms()
        elif self.gantt_type == 'excel':
            return self.import_from_excel()
        elif self.gantt_type == '2000':
            return self.import_2000()
        else:
            return self.import_from_csv()

    def import_from_csv(self):
        if not self.csv_validator(self.filename):
            raise UserError(_("File should have .csv extension"))
        file_path = tempfile.gettempdir() + '/file.csv'
        data = self.csv_file
        f = open(file_path, 'wb')
        f.write(base64.b64decode(data))
        f.close()
        archive = csv.DictReader(open(file_path))

        ConceptObj = self.env['bim.concepts']

        archive_lines = []
        for line in archive:
            archive_lines.append(line)
        parent_chapter = False
        for line in archive_lines:
            code = str(line.get('Code', ""))
            type = str(line.get('Type', ""))
            start = str(line.get('Date Start', ""))
            end = str(line.get('Date End', ""))
            concept = str(line.get('Concept', ""))
            date_start = self.convert_date(start,concept)
            date_end = self.convert_date(end, concept)
            """
            if date_start > date_end:
                raise UserError(_("In Concept %s Date Start is bigger than Date End")%concept)
            """
            if type == "Chapter":
                chapter = ConceptObj.search([('code','=',code),('type','=','chapter'),('budget_id','=',self.budget_id.id)], order='sequence', limit=1)
                if chapter:
                    parent_chapter = chapter.id
                    chapter.acs_date_start = date_start
                    chapter.acs_date_end = date_end
            elif type == "Departure":
                departure = ConceptObj.search([('code','=',code),('type', '=', 'departure'), ('budget_id', '=', self.budget_id.id),
                                               ('parent_id', '=', parent_chapter)], order='sequence', limit=1)
                if departure:
                    departure.acs_date_start = date_start
                    departure.acs_date_end = date_end

    @api.model
    def csv_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension == '.csv' else False


    def load_gantt_ms(self):
        _logger.info('begin - load_gantt_ms')
        dt_format = '%Y-%m-%dT%H:%M:%S'
        working_hours = self.env.company.working_hours
        file_content = base64.b64decode(self.xml_file)
        content = BeautifulSoup(file_content, 'lxml')
        tasks = [task for task in content.find_all('task') if task.find('wbs')]
        concept_obj = self.env['bim.concepts']
        errors = []

        # vamos a poner las duraciones en dias
        # self.budget_id.type_duration = 'date'

        for task in sorted(tasks, key=lambda t: len(t.find('wbs').text.split('.'))):
            wbs = task.find('wbs')
            # Saltando las 2 primeras tareas
            if wbs and wbs.text in ['0', '1']:
                continue

            duration = 0
            try:
                t_duration = task.find('duration').text
                match = re.search(r'PT(\d+)H', t_duration)
                hours = int(match.group(1)) if match else 0
                duration = hours / working_hours if working_hours else 0
            except:
                pass

            concept_id = int(task.find('uid').text)
            concept = self.budget_id.concept_ids.filtered_domain(['&', '|', ('code', '=', wbs.text), ('export_tmp_id', '=', concept_id), ('type', 'in', ['chapter','departure'])])
            if len(concept) > 1:
                concept = concept[0]
            """
            if not concept and not self.create_missing:
                errors.append('<p>The XML file contains the task of ID %d, named %s, and it is not in the budget.</p>' % (concept_id, task.find('name').text))
                continue
            if not concept and self.create_missing:
                code = (wbs and wbs.text or '').split('.')
                concept = concept_obj.create({
                    'code': '.'.join(code),
                    'type': 'chapter' if len(code) <= 2 else 'departure',
                    'name': task.find('name').text,
                    'budget_id': self.budget_id.id,
                    'quantity': 1,
                    'acs_date_start': datetime.datetime.strptime(task.find('start').text, dt_format),
                    'acs_date_end': datetime.datetime.strptime(task.find('finish').text, dt_format),
                })
                if len(code) > 2:
                    parent_code = '.'.join(code[:-1])
                    parent_concept = self.budget_id.concept_ids.filtered_domain([('code', '=', parent_code)])
                    if len(parent_concept) == 1:
                        concept.parent_id = parent_concept

            if self.stage_id and task.find('percentcomplete') and (concept.type_cert == 'stage' or \
                (concept.type_cert != 'stage' and not concept.percent_cert)):
                if concept.type_cert != 'stage':
                    concept.type_cert = 'stage'
                    concept.onchange_type_cert()
                certif_percent = float(task.find('percentcomplete').text)
                if certif_percent:
                    total_cert = sum(concept.certification_stage_ids.mapped('certif_percent'))
                    if total_cert < certif_percent:
                        stage = concept.certification_stage_ids.filtered_domain([('stage_id', '=', self.stage_id.id)])
                        stage.certif_percent = certif_percent - total_cert + stage.certif_percent
                        stage.onchange_percent()
                        concept.update_amount()

            predecessors_vals = []
            predecessors = task.find_all('predecessorlink')
            for pred in predecessors:
                pred_concept_id = int(pred.find('predecessoruid').text)
                pred_concept = self.env['bim.concepts'].search([('budget_id', '=', self.budget_id.id),('export_tmp_id', '=', pred_concept_id), ('type', 'in', ['chapter','departure'])])
                if not pred_concept:
                    pred_name = 'N/A'
                    for ptask in tasks:
                        if ptask.find('uid').text == pred.find('predecessoruid').text:
                            pred_name = ptask.find('name').text
                            break
                    errors.append('<p>The XML file indicates to have the task of ID %d of name %s as a predecessor of the task of ID %d and name %s, and this predecessor does not exist in the budget.</p>' % (pred_concept_id, pred_name, concept_id, task.find('name').text))
                    continue
                predecessors_vals.append((0, 0, {
                    'name': pred_concept.id,
                    'difference': (float(pred.find('linklag').text) / 600 / working_hours) if working_hours else 0,
                    'pred_type': MS_PREDECESSOR_MAPPING.get(pred.find('type').text)
                }))
            concept.bim_predecessor_concept_ids.unlink()
            """

            concept.write({
                'acs_date_start': datetime.strptime(task.find('start').text, dt_format),
                'acs_date_end': datetime.strptime(task.find('finish').text, dt_format),
                'duration': duration,
            })
            concept.onchange_dates()
        if errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import with details',
                    'message': ''.join(errors) + '<b>Close the wizard to see the changes.</b>',
                    'sticky': True,
                    'type': 'warning',
                }
            }

        _logger.info('end - load_gantt_ms')
        budget_id = self.budget_id
        budget_id._compute_dates()
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def excel_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension in ['.xlsx','.xls'] else False



    def import_2000(self):
        """
        PARTIDA	NAT	UNIDAD	DESCRIPCION DE PARTIDA	MEDICION	PRECIO	IMPORTE
        01#			TRABAJOS PREVIOS
        01.01#			EXCAVACION
        01.01.0001			REPLANTEO	 1,00 	 825,00 	 825,00
        O00014	MO	h	Oficial de primera	 10,00 	 25,00 	 250,00
        M2345	MAT	M3	MADERA	 3,90 	 2,56 	 10,00
        EQU22222	EQUIPO	H	GRUA	 1,00 	 490,00 	 490,00
        %DESGASTE 	%		DESGASTE HERRAMIENTAS	 7,50 	 10,00 	 75,00
        TOTAL EXCAVACION			21,00 	 1.575,00
        """

        file = io.BytesIO(base64.b64decode(self.excel_file))
        workbook = xlrd.open_workbook(file_contents=file.read())
        sheet = workbook.sheet_by_index(0)
        n_rows = sheet.nrows
        n_cols = sheet.ncols

        last_bim_concept_id = False
        for row in range(1, n_rows):
            line = sheet.row(row)
            code = line[0].value
            if "#" not in code and len(line[1].value) == 0:
                acs_date_start = line[7].value
                acs_date_end = line[8].value
                code = line[0].value
                bim_concept_id = self.env['bim.concepts'].search(
                    [
                        ('budget_id', '=', self.budget_id.id),
                        ('code', '=', code),
                        ('type', 'in', ['departure'])
                    ])

                if bim_concept_id:
                    bim_concept_id.acs_date_start = self.convert_date(acs_date_start)
                    bim_concept_id.acs_date_end = self.convert_date(acs_date_end)
                    bim_concept_id.onchange_dates()




    def import_from_excel(self):
        if not self.excel_validator(self.filename):
            raise UserError(_("File must contain excel extension"))
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        ConceptObj = self.env['bim.concepts']
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))
        if not "Code" in first_row or not "Concept" in first_row or not "Type" in first_row or not "Begin" in first_row or not "End" in first_row:
            raise UserError(_("Document Budget Header is Wrong. It was expected to have Code, Concept, Type, Begin, End"))
        parent_chapter = False
        for count, row in enumerate(range(1, sheet.nrows), 2):
            val = {}
            for col in range(sheet.ncols):
                val[first_row[col]] = sheet.cell_value(row, col)

            if val['Type'] == "Chapter":
                chapter = ConceptObj.search([('code','=',val['Code']),('type','=','chapter'),('budget_id','=',self.budget_id.id)], order='sequence', limit=1)
                if chapter:
                    parent_chapter = chapter.id
                    chapter.acs_date_start = self.convert_date(val["Begin"])
                    chapter.acs_date_end = self.convert_date(val["End"])
            elif val['Type'] == "Departure":
                departure = ConceptObj.search([('code','=',val['Code']),('type', '=', 'departure'), ('budget_id', '=', self.budget_id.id),
                                               ('parent_id', '=', parent_chapter)], order='sequence', limit=1)
                if departure:
                    departure.acs_date_start = self.convert_date(val["Begin"])
                    departure.acs_date_end = self.convert_date(val["End"])

    def convert_date(self, date_str):
        if len(str(date_str)) > 0:
            if "/" in str(date_str) and date_str.strip():
                return datetime.strptime(date_str, '%d/%m/%Y')

            elif "-" in str(date_str) and date_str.strip():
                return datetime.strptime(date_str, '%d-%m-%Y')

            else:
                fecha_base = datetime(1899, 12, 30)
                days = int(float(date_str))
                fecha_convertida = fecha_base + timedelta(days=days)
                return fecha_convertida
        else:
            return False
