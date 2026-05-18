import base64
import csv
import os
import tempfile
import requests
from odoo import api
from odoo import fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

TEMPLATE_LINE_TYPES = {
    '3': 'M',
    '4': 'H',
    '5': 'Q',
    '6': 'A',
}

CONCEPT_TYPES = {
    '1': 'chapter',
    '2': 'departure',
    '3': 'material',
    '4': 'labor',
    '5': 'equip',
    '6': 'aux',
}


class BimConceptTemplateImport(models.TransientModel):
    _name = 'bim.concept.template.import'
    _description = 'Bim Concept Template Import'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    csv_url = fields.Char(string='CSV URL')
    import_type= fields.Selection([('apu_file','APUs File'),
                                   ('apu_url','APUs Url'),
                                   ('budget','Budget'),
                                   ('product','Product')
                                   ],string='Import Type',default='apu_file', required=True)
    action_type = fields.Selection([('add_update','Create and update resources'),('import_resource','Import resources')],string='Action Type',default='import_resource', required=True)
    product_id = fields.Many2one('product.product', string='Product', default=lambda self: self.env.ref('base_bim_2.default_product'))
    project_id = fields.Many2one('bim.project', string='Project')
    csv_file = fields.Binary('File')
    filename = fields.Char('File Name')

    @api.model
    def default_get(self, fields):
        res = super(BimConceptTemplateImport, self).default_get(fields)
        params = self.env['ir.config_parameter'].sudo()
        res['csv_url'] = params.get_param('bim.import.csv.url.parameter.raw')
        return res

    @api.model
    def csv_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension == '.csv' else False

    @api.onchange('import_type')
    def onchange_import_type(self):
        if self.import_type == 'product':
            self.action_type = 'add_update'

    def import_csv_from_url(self):
        _logger.info("import_csv_from_url")

        if self.import_type == 'apu_url':
            _logger.info("apu_url")
            document_data = self._get_document_data()
            _logger.info(document_data)
            self.import_concept_template(document_data)

        elif self.import_type == 'apu_file':
            _logger.info("apu_file")
            if not self.csv_file:
                raise UserError(_("No file uploaded or the file is empty."))
            if not self.csv_validator(self.filename):
                raise UserError(_("File should have .csv extension"))

            file_path = os.path.join(tempfile.gettempdir(), 'file.csv')
            decoded_content = base64.b64decode(self.csv_file)

            with open(file_path, 'wb') as f:
                f.write(decoded_content)
            try:
                with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
                    archive = csv.DictReader(csv_file)
                    document_data = [line for line in archive]
                    if not document_data:
                        raise UserError(_("The file does not contain valid data or is incorrectly formatted."))
                    self.import_concept_template(document_data)
            except Exception as e:
                _logger.error("Error processing the file: %s", str(e))
                raise UserError(_("An error occurred while processing the file: %s") % str(e))

        elif self.import_type == 'budget':
            _logger.info("budget")
            self.import_from_csv()

        elif self.import_type == 'product':
            _logger.info("product")
            self.import_product()


    def import_product(self):
        if not self.csv_validator(self.filename):
            raise UserError(_("File should have .csv extension"))
        file_path = tempfile.gettempdir() + '/file.csv'
        data = self.csv_file
        f = open(file_path, 'wb')
        f.write(base64.b64decode(data))
        f.close()
        archive = csv.DictReader(open(file_path))
        uom_obj = self.env['uom.uom']
        product_obj = self.env['product.product']
        archive_lines = []
        for line in archive:
            archive_lines.append(line)
        for line in archive_lines:
            try:
                if line.get('type') and line.get('type') in ('3','4','5'):
                    self._create_update_product(line,uom_obj,product_obj)
            except:
                raise UserError(_("Error importing data: %s")%data)

    def _create_update_product(self,data,uom_obj,product_obj):
        if data.get('type'):
            code = list(data.values())[0]
            uom = data.get('uom_id')
            if data.get('price'):
                try:
                    price = float(data.get('price'))
                except:
                    price = 0.0
                product = self._give_product(product_obj,code,data.get('name'),uom,price,uom_obj,data.get('type'))
                bim_type = TEMPLATE_LINE_TYPES.get(data.get('type'))
                product_type = 'product'
                if data.get('type') in ('4','5'):
                    product_type = 'service'
                product.resource_type = bim_type
                try:
                    product.type = product_type
                except:
                    pass


    def import_from_csv(self):
        if not self.csv_validator(self.filename):
            raise UserError(_("File should have .csv extension"))
        file_path = tempfile.gettempdir() + '/file.csv'
        data = self.csv_file
        f = open(file_path, 'wb')
        f.write(base64.b64decode(data))
        f.close()
        archive = csv.DictReader(open(file_path))
        concept_obj = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']
        product_obj = self.env['product.product']
        budget_obj = self.env['bim.budget']
        archive_lines = []
        for line in archive:
            archive_lines.append(line)
        budget = self._create_budget(budget_obj)
        for line in archive_lines:
            try:
                if line.get('type') and line.get('type') in ('1','2','3','4','5','6'):
                    self._create_budget_concept(line,concept_obj,budget,uom_obj,product_obj)
                if line.get('type') == '7' and line.get('parent') and line.get('name'):
                    concept = concept_obj.search([('code', '=', line.get('parent')),('budget_id','=',budget.id)],limit=1)
                    if concept:
                        if concept.note:
                            concept.note += "\n %s"%line.get('name')
                        else:
                            concept.note = line.get('name')
            except:
                raise UserError(_("Error importing data: %s")%data)
        budget.update_amount()

    def _create_budget(self,budget_obj):
        budget = budget_obj.create({'project_id': self.project_id.id,'currency_id': self.company_id.currency_id.id,'name': _("Imported from CSV")})
        return budget

    def _create_budget_concept(self,data,concept_obj,budget,uom_obj,product_obj):
        if data.get('type'):
            code = list(data.values())[0]
            parent_id = False
            data_type = data.get('type')
            type = CONCEPT_TYPES.get(data_type)
            if data.get('parent'):
                parent_id = concept_obj.search([('code','=',data.get('parent')),('budget_id','=',budget.id)],limit=1).id or False
            vals = {'code': code, 'name': data.get('name'), 'type': type, 'parent_id': parent_id, 'budget_id': budget.id}
            uom = data.get('uom_id')
            if uom:
                uom_id = uom_obj.search(['|', ('alt_names', 'ilike', uom), ('name', '=', uom)], limit=1)
                if uom_id:
                    vals.update({'uom_id': uom_id.id})
            if data_type == '2':
                if data.get('hours_day'):
                    vals.update({'hours_day': data.get('hours_day')})
                if data.get('performance'):
                    vals.update({'performance': data.get('performance')})
                if data.get('quantity'):
                    vals.update({'quantity': data.get('quantity')})
            if data_type in ('1','2'):
                concept_obj.create(vals)
            elif data_type in ('3','4','5','6'):
                if data.get('quantity'):
                    vals.update({'quantity': data.get('quantity')})
                if data.get('available'):
                    vals.update({'available': data.get('available')})
                if data.get('price'):
                    try:
                        price = float(data.get('price'))
                    except:
                        price = 0.0
                    vals.update({'amount_fixed': price})
                concept = concept_obj.create(vals)
                product = self._give_product(product_obj,code,data.get('name'),data.get('uom_id'),data.get('price'),uom_obj,data_type)
                if product:
                    concept.product_id = product.id

    def _get_document_data(self):
        _logger.info("get_document_data")

        document_header = []
        document_data = []
        response = requests.get(self.csv_url)  # self.csv_url debe contener el enlace "raw"

        if response.status_code == 200:
            # Lee el contenido del archivo CSV desde la URL
            lines = response.content.decode('utf-8-sig').splitlines()
            reader = csv.reader(lines)

            # Procesar cada línea del archivo
            for index, row in enumerate(reader):
                # La primera línea es el encabezado
                if index == 0:
                    document_header = row
                    _logger.info("Document Header: %s", document_header)
                else:
                    # Combina el encabezado con la fila actual para crear un diccionario
                    document_data.append(dict(zip(document_header, row)))
        else:
            raise UserError(_("Error getting CSV file from URL: %s") % self.csv_url)

        _logger.info("Document Data: %s", document_data)
        return document_data

    def import_concept_template(self, document_data):

        _logger.info("import_concept_template")

        template_obj = self.env['bim.concept.template']
        template_obj_line = self.env['bim.concept.template.line']
        group_obj = self.env['bim.concept.template.group']
        product_obj = self.env['product.product']
        uom_obj = self.env['uom.uom']
        for data in document_data:
            _logger.info(data)
            try:
                if data.get('type') and data.get('type') == '2':
                    self._create_concept_template(data,group_obj,template_obj,uom_obj)
                if data.get('type') and data.get('type') in ('3','4','5','6','7'):
                    self._create_concept_template_line(data,template_obj,template_obj_line,product_obj,uom_obj)
            except Exception:
                raise UserError(_("Error importing data: %s")%data)

    @staticmethod
    def _prepare_product_vals(code,name,uom_obj, uom, data_type):
        vals = {'default_code': code, 'name': name}
        if data_type == '3':
            vals.update({'type': 'product', 'resource_type': 'M'})
        elif data_type == '4':
            vals.update({'type': 'service', 'resource_type': 'H'})
        elif data_type == '5':
            vals.update({'type': 'service', 'resource_type': 'Q'})
        elif data_type == '6':
            vals.update({'type': 'service', 'resource_type': 'A'})
        if uom:
            uom_id = uom_obj.search(['|',('alt_names', 'ilike', uom),('name','=',uom)],limit=1)
            if uom_id:
                vals.update({'uom_id': uom_id.id, 'uom_po_id': uom_id.id})
        return vals

    @staticmethod
    def _prepare_line_vals(product, type, code, name, template,price):
        max_sequence = template.template_line_ids and max(template.template_line_ids.mapped('sequence')) or 10
        max_sequence +=1
        vals = {'type': TEMPLATE_LINE_TYPES[type], 'template_id': template.id,
                'product_id': product.id, 'name': name,'sequence':max_sequence,
                'code': code, 'uom_id': product.uom_id.id}
        if type in ('6') and price:
            vals.update({'price': price})
        return vals
    def _write_product_price(self, price, product):
        try:
            price = float(price)
        except:
            price = 0
        if self.company_id.type_work in ('costlist', 'cost'):
            product.with_company(self.company_id).standard_price = price
        else:
            product.list_price = price

    def _give_product(self,product_obj,code,name,uom,price,uom_obj,product_type):
        product = product_obj.search([('default_code', '=', code)],limit=1)
        if not product:
            if self.action_type == 'add_update':
                vals = self._prepare_product_vals(code,name,uom_obj, uom,product_type)
                product = product_obj.create(vals)
                self._write_product_price(price, product)
            else:
                product = self.product_id
        else:
            if self.action_type == 'add_update':
                product.name = name
                self._write_product_price(price, product)
        return product

    def _create_concept_template_line(self, data,template_obj,template_obj_line,product_obj,uom_obj):

        _logger.info("create_concept_template_line")
        _logger.info(data)

        code = data.get('code')
        parent = data.get('parent')
        name = data.get('name')
        type = data.get('type')
        uom = data.get('uom_id')
        price = data.get('price')
        quantity = data.get('quantity')
        available = data.get('available')

        _logger.info("code: %s, parent: %s, name: %s, type: %s, uom: %s, price: %s, quantity: %s, available: %s" % (code, parent, name, type, uom, price, quantity, available))

        if type in ('3','4','5','6') and code and parent and name:
            template = template_obj.search([('code', '=', parent)])
            product = self._give_product(product_obj,code,name,uom,price,uom_obj,type)
            if template and product:
                line = template_obj_line.search([('template_id', '=', template.id),('code','=',code)])
                vals = self._prepare_line_vals(product, type, code, name, template, price)
                if not line:
                    line = template_obj_line.create(vals)
                else:
                    line.write(vals)
                if type == '3' and quantity:
                    try:
                        quantity = float(quantity)
                    except:
                        quantity = 0
                    line.quantity = quantity
                if type in ('4','5') and available:
                    line.available = available
                line.onchange_product_id()
                if price:
                    try:
                        price = float(price)
                    except:
                        price = 0
                    line.price = price
                if uom:
                    uom_id = uom_obj.search(['|',('alt_names', 'ilike', uom),('name','=',uom)],limit=1)
                    if uom_id:
                        line.uom_id = uom_id.id

        if type == '7' and parent and name:
            template = template_obj.search([('code', '=', parent)],limit=1)
            if template:
               template.notes = name



    @staticmethod
    def _prepare_template_vals(code,name,group,subgroup, performance, hours_day):
        vals = {'code': code, 'name': name}
        if group:
            vals.update({'group_id':group.id if group else False})
        if subgroup:
            vals.update({'sub_group_id':subgroup.id if subgroup else False})
        if performance:
            vals.update({'performance': performance})
        if hours_day:
            vals.update({'hours_day': hours_day})
        return vals

    def _create_concept_template(self, data, group_obj,template_obj,uom_obj):
        group = False
        subgroup = False
        if data.get('group'):
            group = group_obj.search([('code', '=', data.get('group'))],limit=1)
            if not group:
                group = group_obj.create({'name': _("Group %s") % data.get('group'), 'code': data.get('group')})
        if data.get('sub_group'):
            subgroup = group_obj.search([('code', '=', data.get('sub_group'))],limit=1)
            if not subgroup:
                subgroup = group_obj.create(
                    {'name': _("Group %s") % data.get('sub_group'), 'code': data.get('sub_group'),
                     'parent_id': group.id if group else False})
        if data.get('code'):
            template = template_obj.search([('code', '=', data.get('code'))])
            # template.template_line_ids.unlink()
            vals = self._prepare_template_vals(data.get('code'), data.get('name'), group, subgroup,
                                               data.get('performance'), data.get('hours_day'))
            if not template:
                template = template_obj.create(vals)
            else:
                template.write(vals)
            if data.get('uom_id'):
                uom = data.get('uom_id')
                uom_id = uom_obj.search(['|', ('alt_names', 'ilike', uom), ('name', '=', uom)], limit=1)
                if uom_id:
                    template.uom_id = uom_id.id







