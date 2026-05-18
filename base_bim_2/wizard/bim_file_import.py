import base64
import csv
import os
import tempfile

import xlrd
from odoo import api
from odoo import fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
import json

CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux'}


class BimFileImport(models.TransientModel):
    _name = 'bim.file.import'
    _description = 'Import BIM File'

    budget_id = fields.Many2one('bim.budget', 'Budget', domain="[('project_id', '=', project_id)]")
    filename = fields.Char('File Name')
    bim_file = fields.Binary('File', required=True)

    bim_type = fields.Selection([
                                 ('exjson','ExJson'),
                                 ('revit_en', 'Revit (Assembly Code, Count)'),
                                 ('revit_es', 'Revit (Código de montaje, Recuento)'),
                                 ('boq','Boq'),
                                 ], 'BIM File', default='exjson', required=True)


    project_id = fields.Many2one('bim.project', 'Project')
    import_type = fields.Selection([('update', 'Update budget'),('create', 'Create budget')], 'Import Type', default='update', required=True)
    from_action = fields.Boolean('From Action', default=False)
    def default_budget_name(self):
        return _("Bim Budget Import")

    budget_name = fields.Char('Budget Name', default=default_budget_name)
    boq_template_id = fields.Many2one('bim.boq.template', 'Boq Template')

    @api.model
    def file_validator(self, fileformat):
        name, extension = os.path.splitext(fileformat)
        return True if extension in ['.csv','.txt'] else False
    @api.model
    def file_excel_validator(self, fileformat):
        name, extension = os.path.splitext(fileformat)
        return True if extension in ['.xls','.xlsx'] else False

    def import_bim_file(self):
        if not self.bim_file:
            raise UserError(_("Please select a file"))

        if self.bim_type != 'exjson':
            budget_data, code_name, quantity_name = self._prepare_update_create_data()
            if not code_name or not quantity_name:
                raise UserError(_("Please select a valid file"))
            if self.import_type == 'update':
                log = self.update_budget_from_file(budget_data,code_name, quantity_name )
            else:
                log = self.create_budget_from_file(budget_data,code_name, quantity_name )
            if not self.budget_id.concept_ids:
                raise UserError(_("No concepts where found in the file"))
            if log != "":
                log = "%s %s"%(_("Concepts not found"),log[:-2])
            self.env['bim.budget.revit.import'].create({
                'budget_id': self.budget_id.id,
                'project_id': self.budget_id.project_id.id,
                'file': self.bim_file,
                'file_name': self.filename,
                'log': log,
            })
            return self.budget_id.action_view_budget()

        else:
            _logger.info("Importing from exjson")
            data_json = base64.b64decode(self.bim_file)
            json_data = json.loads(data_json)

            for concept in json_data['budgets'][0]['concepts']:
                _logger.info("=====")
                _logger.info(concept['price'])

                if concept['parent']:
                   parent_id = self.env['bim.concepts'].search([
                            ('code','=',concept['parent']),
                            ('budget_id','=',self.budget_id.id)], limit=1)


                new_concept = self.env['bim.concepts'].create({
                    'name': concept['name'],
                    'code': concept['code'],
                    'quantity': concept['quantity'],
                    'performance': concept['performance'],
                    'note': concept['note'],
                    'type': concept['type'],
                    'budget_id': self.budget_id.id,
                    'amount_type': concept['amount_type'],
                    'depreciation': concept['depreciation'],
                    'amount_fixed': float(concept['price']),
                    'parent_id': parent_id.id if concept['parent'] else False,
                })


            _logger.info(json_data)

    def _prepare_update_create_data(self):
        if self.bim_type == 'revit_en':
            return self._prepare_revit_update_create_data('Assembly Code', 'Count')
        elif self.bim_type == 'revit_es':
            return self._prepare_revit_update_create_data('Código de montaje', 'Recuento')
        else:
            return self._prepare_boq_update_create_data()

    def _validate_boq_template_and_document(self):
        if not self.boq_template_id:
            raise UserError(_("Please select a Boq Template"))
        if self.boq_template_id.type == 'csv' and not self.file_validator(self.filename):
            raise UserError(_("File must contain csv extension"))
        if self.boq_template_id.type == 'excel' and not self.file_excel_validator(self.filename):
            raise UserError(_("File must contain xls or xlsx extension"))
    def _prepare_boq_update_create_data(self):
        if self.bim_type == 'boq':
            self._validate_boq_template_and_document()
            quantity_name = self.boq_template_id.quantity_name
            code_name = self.boq_template_id.code_name
            file_type = self.boq_template_id.type
            if file_type == 'csv':
                return self._prepare_csv_update_create_data(code_name,quantity_name)
            else:
                return self._prepare_boq_excel_update_create_data(code_name,quantity_name)
        return [],False,False

    def _prepare_boq_excel_update_create_data(self, code_name,quantity_name):
        data = base64.b64decode(self.bim_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))
        data_list = []
        for count, row in enumerate(range(1, sheet.nrows), 2):
            val = {}
            for col in range(sheet.ncols):
                val[first_row[col]] = sheet.cell_value(row, col)
            data_list.append(val)
        return data_list, code_name, quantity_name

    def _prepare_revit_update_create_data(self, code_name, quantity_name):
        if not self.file_validator(self.filename):
            raise UserError(_("File must contain csv or txt extension"))
        return self._prepare_csv_update_create_data(code_name, quantity_name)

    def _prepare_csv_update_create_data(self, code_name, quantity_name):
        file_path = tempfile.gettempdir() + '/bim_file.csv'
        data = self.bim_file
        f = open(file_path, 'wb')
        try:
            f.write(base64.b64decode(data).decode("utf-8-sig", "ignore").encode("utf-8"))
            f.close()
            archive = csv.DictReader(open(file_path))
        except:
            raise UserError(_("There is an encoding error"))
        archive_lines = []
        codes = []
        for line in archive:
            self._validate_header_in_line(line, code_name, quantity_name)
            code = line.get(code_name)
            qty = line.get(quantity_name)
            if code != '' and qty != '':
                if code not in codes:
                    codes.append(code)
                    archive_lines.append(line)
                else:
                    for taken_line in archive_lines:
                        if taken_line[code_name] == line.get(code_name):
                            increment = float(line.get(quantity_name)) + float(taken_line[quantity_name])
                            taken_line[quantity_name] = str(increment)
                            break
        return archive_lines, code_name, quantity_name
    def _validate_header_in_line(self, line, code_name, quantity_name):
        if code_name not in line:
            raise UserError(_("Code name %s not found in file") % code_name)
        if quantity_name not in line:
            raise UserError(_("Quantity name %s not found in file") % quantity_name)

    def update_budget_from_file(self, archive_lines, code_name, quantity_name):
        concept_obj = self.env['bim.concepts']
        log = ''
        for line in archive_lines:
            self._validate_header_in_line(line, code_name, quantity_name)
            code = line.get(code_name)
            try:
                quantity = float(line.get(quantity_name))
            except:
                raise UserError(_("Quantity must be a number"))
            if code:
                possible_concept = concept_obj.search([('id_bim','=',code),('budget_id','=',self.budget_id.id)])
                if possible_concept:
                    for concept in possible_concept:
                        concept.quantity = quantity
                else:
                    concept_template = self.env['bim.concept.template'].search([('bim_id','=',code)])
                    if concept_template:
                        chapter =  self._get_chapter(concept_template, self.budget_id)
                        self._create_departure(chapter, concept_template, self.budget_id, quantity, code)
                    else:
                        log += "%s, "%code
        return log

    def create_budget_from_file(self,budget_data,code_name, quantity_name):
        concept_template_obj = self.env['bim.concept.template']
        budget_id = self.env['bim.budget'].create({
            'name': self.budget_name,
            'project_id': self.project_id.id,
            'currency_id': self.project_id.currency_id.id,
            })
        self.budget_id = budget_id.id
        log = ''
        for line in budget_data:
            self._validate_header_in_line(line, code_name, quantity_name)
            code = line.get(code_name)
            concept_template = concept_template_obj.search([('bim_id','=',code)])
            try:
                quantity = float(line.get(quantity_name))
            except:
                raise UserError(_("Quantity must be a number"))
            if code and concept_template:
                if concept_template:
                    chapter =  self._get_chapter(concept_template, budget_id)
                    self._create_departure(chapter, concept_template, budget_id, quantity, code)
                    budget_id.update_amount()
            else:
                log += "%s, "%code
        return log
    def _get_chapter(self, concept_template, budget):
        if concept_template.group_id:
            chapter = budget.concept_ids.filtered(lambda x: x.code == concept_template.group_id.code and x.type == 'chapter')
            if chapter:
                return chapter[0]
            return budget.concept_ids.create({
                'name': concept_template.group_id.name,
                'code': concept_template.group_id.code,
                'budget_id': budget.id,
                'sequence': max(budget.concept_ids.mapped('sequence')) + 1 if budget.concept_ids else 10,
                'type': 'chapter'})
        else:
            raise UserError(_("Concept template {} has no group").format(concept_template.name))
    def _create_departure(self, chapter, concept_template, budget_id, quantity, bim_id):
        departure = budget_id.concept_ids.create({
            'name': concept_template.name,
            'budget_id': budget_id.id,
            'parent_id' : chapter.id,
            'code': concept_template.code,
            'quantity': quantity,
            'id_bim': bim_id,
            'uom_id': concept_template.uom_id.id if concept_template.uom_id else False,
            'performance': concept_template.performance,
            'note': concept_template.notes,
            'type': 'departure'})
        for line in concept_template.template_line_ids:
            vals = {
                'budget_id': budget_id.id,
                'parent_id': departure.id,
                'name': line.name,
                'code': line.code,
                'quantity': line.quantity,
                'amount_fixed': line.price,
                'available': line.available,
                'product_id': line.product_id.id if line.product_id else False,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'type': CONCEPT_TYPE[line.type],
                'concept_template_line_id': line.id,
            }
            departure.child_ids.create(vals)
