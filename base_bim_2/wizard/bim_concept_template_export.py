import base64
import os
import json
import logging
import requests
from odoo import api
from odoo import fields, models, _
from io import BytesIO
from odoo.tools.misc import xlwt
_logger = logging.getLogger(__name__)

TEMPLATE_LINE_TYPES = {
    'M': '3',
    'H': '4',
    'Q': '5',
    'A': '6',
}

CONCEPT_TYPES = {
    'chapter': '1',
    'departure': '2',
    'material': '3',
    'labor': '4',
    'equip': '5',
    'aux': '6',
}


class BimConceptTemplateExport(models.TransientModel):
    _name = 'bim.concept.template.export'
    _description = 'Bim Concept Template export'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    export_type = fields.Selection([
                                    ('concept_template', 'Concept Template'),
                                    ('budget', 'Budget'),
                                    ('budget_2000', 'Budget 2000'),
                                    ('product','Product'),
                                    ('exjson','ExJson')
                                    ],
                                    string='Export Type',
                                    required=True,
                                    default='exjson')
    concept_template_ids = fields.Many2many('bim.concept.template', string='Concept Template')
    product_template_ids = fields.Many2many('product.template', string='Product Templates')
    budget_id = fields.Many2one('bim.budget')
    price_type = fields.Selection([('price', 'Price'), ('cost', 'Cost')], string='Price Type', default='cost')

    @api.model
    def default_get(self, fields):
        res = super(BimConceptTemplateExport, self).default_get(fields)
        if self._context.get('active_model') == 'bim.concept.template':
            res['concept_template_ids'] = self._context.get('active_ids')
            res['export_type'] = 'concept_template'
        elif self._context.get('active_model') == 'bim.budget':
            res['budget_id'] = self._context.get('active_id')
            res['export_type'] = 'budget'
        elif self._context.get('active_model') == 'product.template':
            res['product_template_ids'] = self._context.get('active_ids')
            res['export_type'] = 'product'
        return res

    @api.model
    def csv_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension == '.csv' else False


    def export_2000(self, budget):
        pass


    def export_csv_from_url(self):
        data = "code,group,sub_group,parent,type,name,url,provider,available,quantity,performance,hours_day,uom_id,price,\n"
        csv = False
        if self.export_type == 'concept_template':
            data = self.export_concept_template(data)
            file_name =  _("Concept Templates")
            csv = True

        elif self.export_type == 'budget_2000':
            _logger.info('BEGIN : Exporting Budget 2000 %s', self.budget_id.name)

            workbook = xlwt.Workbook(encoding="utf-8")
            worksheet = workbook.add_sheet(_("Product"))
            file_name = _("budget_2000")
            style_border_table_top = xlwt.easyxf(
                'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
            style_border_table_details = xlwt.easyxf('borders: bottom thin;')
            style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

            worksheet.write(0, 0, _("PARTIDA"), style_border_table_top)
            worksheet.write(0, 1, _("NAT"), style_border_table_top)
            worksheet.write(0, 2, _("UNIDAD"), style_border_table_top)
            worksheet.write(0, 3, _("DESCRIPCION DE PARTIDA"), style_border_table_top)
            worksheet.write(0, 4, _("MEDICION"), style_border_table_top)
            worksheet.write(0, 5, _("PRECIO"), style_border_table_top)
            worksheet.write(0, 6, _("IMPORTE"), style_border_table_top)
            worksheet.write(0, 7, _("INICIO"), style_border_table_top)
            worksheet.write(0, 8, _("FIN"), style_border_table_top)
            worksheet.write(0, 9, _("RENDIMIENTO"), style_border_table_top)
            worksheet.write(0, 10, _("DURACION"), style_border_table_top)


            style = style_border_table_details
            bim_concepts_ids = self.budget_id.concept_ids

            row = 1
            for concept in bim_concepts_ids:
                _logger.info('Concept %s', concept.name)
                code = concept.code
                if concept.type == 'chapter':
                    code = code + '#'


                if concept.type == 'material':
                    nat = "MAT"
                elif concept.type == 'labor':
                    nat = "MO"
                elif concept.type == 'equip':
                    nat = "EQUIPO"
                elif concept.type == 'aux':
                    nat = "%"
                else:
                    nat = ""

                uom = concept.uom_id.name if concept.uom_id else ''

                worksheet.write(row, 0, code or '', style)
                worksheet.write(row, 1, nat, style)
                worksheet.write(row, 2, uom, style)
                worksheet.write(row, 3, concept.name, style)
                worksheet.write(row, 4, concept.quantity, style)
                worksheet.write(row, 5, concept.amount_compute, style)
                worksheet.write(row, 6, concept.balance, style)
                worksheet.write(row, 7, concept.acs_date_start.strftime('%d/%m/%Y') if concept.acs_date_start else '', style)
                worksheet.write(row, 8, concept.acs_date_end.strftime('%d/%m/%Y') if concept.acs_date_end else '', style)
                worksheet.write(row, 9, concept.performance, style)
                worksheet.write(row, 10, concept.duration, style)
                row += 1

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



            _logger.info('END : Exporting Budget 2000')

            return {
                'type': "ir.actions.act_url",
                'url': "web/content/?model=ir.attachment&id=" + str(
                    doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
                'no_destroy': False,
            }

        elif self.export_type == 'budget':
            data = self.export_budget_to_csv(data)
            file_name = _("Budget %s") % self.budget_id.name
            csv = True
        elif self.export_type == 'product':
            data = self.export_product_templates_to_csv(data)
            file_name = _("Products")
            csv = True
        elif self.export_type == 'exjson':
            file_name = str(self.budget_id.id) + "_" + self.budget_id.name.replace(' ','_')
            budget_data = {
                'id' : self.budget_id.project_id.id,
                'code' : self.budget_id.project_id.name,
                'name': self.budget_id.project_id.nombre,
                'version': "1.0.0",
                'company': self.budget_id.company_id.name,
                'vat': self.budget_id.company_id.vat,
                'author' : self.budget_id.user_id.name,
                'email' : self.budget_id.company_id.email,
                'phone' : self.budget_id.company_id.phone,
                'type' : 'project',
                'origin' : self.budget_id.project_id.name,

            }

            budget_data['budgets'] = [
                {
                    'id' : self.budget_id.id,
                    'code' : self.budget_id.code,
                    'name' : self.budget_id.name,
                    'currency' : self.budget_id.currency_id.name,
                    'description' : '-',
                    'template' : self.budget_id.template_id.id,
                    'concepts': [],
                    }
            ]

            #['budgets']['concepts']
            concept_ids = sorted(self.budget_id.concept_ids, key=lambda concept: concept.id)
            for concept in concept_ids:
                concept_data = {
                    'id' : concept.id,
                    'code' : concept.code,
                    'name' : concept.name,
                    'product' : concept.product_id.id,
                    'type' : concept.type,
                    'quantity' : concept.quantity,
                    'price' : concept.quantity,
                    'amount_type' : concept.amount_type,
                    'parent' : concept.parent_id.code,
                    'performance' : concept.performance,
                    'depreciation' : concept.depreciation,
                    'note' : concept.note,
                    'date_start' : str(concept.acs_date_start),
                    'date_end' : str(concept.acs_date_end),
                    }
                budget_data['budgets'][0]['concepts'].append(concept_data)







            json_data = json.dumps(budget_data)
            data_b64 = base64.encodebytes(json_data.encode('utf-8'))
            doc = self.env['ir.attachment'].create({
                'name': '%s.exjson' %file_name,
                'datas': data_b64,
            })
            return {
                'type': "ir.actions.act_url",
                'url': "web/content/?model=ir.attachment&id=" + str(
                    doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
                'target': "current",
                'no_destroy': False,
            }

        if csv:
            data_b64 = base64.encodebytes(data.encode('utf-8'))
            doc = self.env['ir.attachment'].create({
                'name': '%s.csv' %file_name,
                'datas': data_b64,
            })

            return {
                'type': "ir.actions.act_url",
                'url': "web/content/?model=ir.attachment&id=" + str(
                    doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
                'target': "current",
                'no_destroy': False,
            }

    @staticmethod
    def _write_concept_template_info(concept_template, data, type=2):
        code = concept_template.code
        group = concept_template.group_id.code if concept_template.group_id else ''
        sub_group = concept_template.sub_group_id.code if concept_template.sub_group_id else ''
        performance = concept_template.performance
        quantity = concept_template.quantity
        hours_day = concept_template.hours_day
        name = concept_template.name
        uom_id = concept_template.uom_id.name.replace('²', '2').replace('³', '3') if concept_template.uom_id else ''

        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += "%s,%s,%s,,%s,%s,,,,%s,%s,%s,%s,,\n" % (
           code, group, sub_group, type, name, quantity, performance, hours_day,uom_id)
        return data

    @staticmethod
    def _write_concept_template_line_info(line, data, type):
        code = line.code
        parent = line.template_id.code if line.template_id else ''
        quantity = line.quantity
        name = line.name
        uom_id = line.uom_id.name.replace('²', '2').replace('³', '3') if line.uom_id else ''
        price = line.price
        available = line.available

        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += "%s,,,%s,%s,%s,,,%s,%s,,,%s,%s,\n" % (
           code, parent, type, name, available, quantity, uom_id, price)
        return data

    @staticmethod
    def _write_concept_template_note(concept_template, data, type):
        parent = concept_template.code if concept_template.code else ''
        name = concept_template.notes

        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += ",,,%s,%s,%s,,,,,,,,,\n" % (parent, type, name)
        return data

    @staticmethod
    def _write_concept_note(concept, data, type):
        parent = concept.code if concept.code else ''
        name = concept.note

        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += ",,,%s,%s,%s,,,,,,,,,\n" % (parent, type, name)
        return data

    @staticmethod
    def _write_budget_concept_info(concept, data, type):
        code = concept.code
        performance = concept.performance if type == '2' else ''
        hours_day = concept.hours_day if type == '2' else ''
        quantity = concept.quantity if type not in ('1','7') else ''
        available = concept.available if type not in ('1','2','7') else ''
        name = concept.name
        uom_id = concept.uom_id.name.replace('²', '2').replace('³', '3') if concept.uom_id else ''
        price = concept.amount_fixed if type not in ('1','2','7') else ''
        parent = concept.parent_id.code if concept.parent_id else ''

        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += "%s,,,%s,%s,%s,,,%s,%s,%s,%s,%s,%s,\n" % (
           code, parent,type, name,available, quantity, performance, hours_day,uom_id,price)
        return data

    def _write_product_template_info(self, product, data):
        code = product.default_code if product.default_code else ''
        name = product.name
        uom_id = product.uom_id.name.replace('²', '2').replace('³', '3') if product.uom_id else ''
        price = product.list_price if self.price_type == 'price' else product.with_company(self.company_id).standard_price
        type = TEMPLATE_LINE_TYPES[product.resource_type]
        # code, group, sub_group, parent, type, name, url, provider, available, quantity, performance, hours_day, uom_id, price
        data += "%s,,,,%s,%s,,,,,,,%s,%s,\n" % (code,type, name, uom_id, price)
        return data

    def export_concept_template(self, data):
        for concept_template in self.concept_template_ids:
            data = self._write_concept_template_info(concept_template, data)
            for line in concept_template.template_line_ids:
                data = self._write_concept_template_line_info(line, data, TEMPLATE_LINE_TYPES[line.type])
            if concept_template.notes:
                data = self._write_concept_template_note(concept_template, data, '7')
        return data

    def export_product_templates_to_csv(self, data):
        for template in self.product_template_ids:
            data = self._write_product_template_info(template, data)
        return data

    def export_budget_to_csv(self, data):
        exported_concepts = []
        for concept in self.budget_id.concept_ids.filtered_domain([('parent_id', '=', False)]):
            exported_concepts.append(concept.id)
            data = self._write_recursive(concept, data)
        return data

    def _write_recursive(self, concept, data):
        data = self._write_budget_concept_info(concept, data, CONCEPT_TYPES[concept.type])
        for child in concept.child_ids:
            data = self._write_recursive(child, data)
        if concept.note:
            data = self._write_concept_note(concept, data, '7')
        return data


