# -*- coding: utf-8 -*-
from odoo import api, fields, models,_
import base64
from odoo.exceptions import UserError, ValidationError
import xlrd
import os
RESOURSES = ['MO','MAT','EQUIPO','OTROS','%','SC']
import ast

import logging
_logger = logging.getLogger(__name__)

class WorkDatabaseConceptImporter(models.Model):
    _description = "Work Database Concept Importer"
    _name = 'work.database.concept.importer'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char('Code', default="New", tracking=True, copy=False)
    project_id = fields.Many2one('bim.project', 'Project', tracking=True, ondelete='cascade')
    excel_file = fields.Binary('Excel File', required=True)
    filename = fields.Char('File name')
    state = fields.Selection(
        [
            ('to_execute', 'To execute'),
            ('ongoing', 'In process'),
            ('done', 'Done'),
            ('error', 'Error'),
            ('canceled', 'Canceled')
        ], 'Status',
        default='to_execute', tracking=True)
    error = fields.Text(readonly=True)
    budget_id = fields.Many2one('bim.budget', 'Created budget', readonly=True, ondelete='cascade', copy=False)

    budget_name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', 'Responsible', readonly=True, required=True,
                              default=lambda self: self.env.user)
    version = fields.Selection([('1000', 'Mode 1000'),
                                ('2000', 'Mode 2000'),
                                ('2000-APU', '2000-APU'),
                                ('3000', 'Mode 3000'),
                                ('template_xls', 'Template XLS'),
                                ], 'Version', default='2000', required=True,
                               tracking=True)
    product_id = fields.Many2one('product.product', 'Default product',
                                 default=lambda self: self.env.ref('base_bim_2.default_product',
                                                                   raise_if_not_found=False))

    template_id = fields.Many2one('bim.template.xls', 'Template XLS')

    category_id = fields.Many2one('product.category')

    create_all_products = fields.Boolean('Create non-existent products')
    product_cost_or_price = fields.Selection([('price', 'Price'), ('cost', 'Product Cost')],
                                             string='Assign to', default='cost')

    uom_id = fields.Many2one('uom.uom', 'Unit of Measure')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    def action_to_cancel(self):
        self.state = 'canceled'

    def action_to_execute(self):
        self.state = 'to_execute'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('work.database.concept.importer') or 'New'
        return super().create(vals_list)

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            budget_count = self.project_id.budget_count + 1
            self.budget_name = _("Budget: {} {}").format(budget_count, self.project_id.name)
        else:
            self.budget_name = _("Budget")


    @api.model
    def excel_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension in ['.xlsx','.xls'] else False

    def action_import_concepts(self):
        if not self.excel_validator(self.filename):
            raise UserError(_("File must contain excel extension"))
        if self.version == '2000':
            return self.import_2000_template()
        elif self.version == '3000':
            return self.import_3000_template()
        elif self.version == '1000':
            return self.import_1000_template()
        elif self.version == 'template_xls':
            return self.import_template_xls()
        elif self.version == '2000-APU':
            return self.import_apu_2000()


    @api.model
    def validate_extesion_file_excel(self, filename):
        name = os.path.splitext(filename)[1]
        return (True, name) if name in ['.xls','.xlsx'] else False



    def import_template_xls(self):
        _logger.info("BEGIN import_template_xls")

        if not self.validate_extesion_file_excel(self.filename):
            raise UserError(_("File must contain excel extension"))

        if not self.template_id:
            raise UserError(_("Template not found"))

        "[DEPARTURE,PARTIDA];[PARENT,PADRE];[TYPE,NAT];[UOM,UNIDAD];[NAME,DESCRIPCION DE PARTIDA];[QTY,MEDICION];[PRICE,PRECIO];[AMOUNT,IMPORTE]"

        required_fields = ['DEPARTURE', 'PARENT', 'TYPE', 'UOM', 'NAME', 'QTY', 'PRICE', 'AMOUNT']

        for field in required_fields:
            if field not in self.template_id.code:
                raise UserError(_("Please check template header in position: {}").format(field))

        array_code = self.template_id.code.split(';')
        array_code = [x.replace('[','').replace(']','') for x in array_code]


        departure = ""
        parent = ""
        type = ""
        uom = ""
        name = ""
        qty = ""
        price = ""
        amount = ""


        for a in array_code:
            if 'DEPARTURE' in a:
                departure = a.split(',')[1]
            if 'PARENT' in a:
                parent = a.split(',')[1]
            if 'TYPE' in a:
                type = a.split(',')[1]
            if 'UOM' in a:
                uom = a.split(',')[1]
            if 'NAME' in a:
                name = a.split(',')[1]
            if 'QTY' in a:
                qty = a.split(',')[1]
            if 'PRICE' in a:
                price = a.split(',')[1]
            if 'AMOUNT' in a:
                amount = a.split(',')[1]



        if not self.budget_id:
            new_budget = self.env['bim.budget'].create({'name': self.budget_name,
                                                        'project_id': self.project_id.id,
                                                        'currency_id': self.project_id.currency_id.id
                                                        })
            self.budget_id = new_budget.id

        concept_obj = self.env['bim.concepts']
        product_obj = self.env['product.product']
        uom_obj = self.env['uom.uom']
        line_count = 1
        last_departure = False

        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []

        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))

        cont = 0
        for count, row in enumerate(range(1, sheet.nrows), 2):
            try:
                val = {}
                cont += 1
                for col in range(sheet.ncols):
                    val[first_row[col]] = sheet.cell_value(row, col)

                _logger.info("val: {}".format(val))

                _departure = str(val.get(departure)).strip()
                _parent = str(val.get(parent)).strip()
                _type = str(val.get(type)).strip()
                _uom = str(val.get(uom)).strip()
                _name = str(val.get(name)).strip()
                _qty = val.get(qty)
                _price = val.get(price)
                _amount = val.get(amount)


                uom_id = self.env['uom.uom'].search(['|', ('name', '=', _uom), ('alt_names', 'ilike', _uom)], limit=1)
                if not uom_id:
                    uom_id = self.env['uom.uom'].search([], limit=1)



                if _type == "Mano de Obra" or _type == "MO":
                    __type = "labor"
                elif _type == "Materiales" or _type == "MAT":
                    __type = "material"
                elif _type == "Equipos" or _type == "EQUIPO":
                    __type = "equip"
                elif _type == "CAPITULO":
                    __type = "chapter"
                elif _type == "PARTIDA":
                    __type = "departure"
                else:
                    __type = "departure"

                # revisamos si concepto existe
                concept_id = concept_obj.search([('code', '=', _departure),
                                               ('budget_id', '=', self.budget_id.id)])


                parent_id = concept_obj.search([('code', '=', _parent),
                                               ('budget_id', '=', self.budget_id.id)])

                if not concept_id:
                    product_id = False
                    product_id = product_obj.search(['|', ('default_code', '=', _departure), ('barcode', '=', _departure)],
                                                 limit=1)
                    if not product_id:
                        product_id = product_obj.search([('name', '=', _name)], limit=1)

                    if not product_id:
                        # Lo creamos
                        if __type == "material" or __type == "equip" or __type == "labor":

                            ptype = 'product' if __type == "material" else 'service'
                            resource_type = 'M' if __type == "material" else 'Q' if __type == "equip" else 'H'

                            product_id = product_obj.create({
                                'name': _name,
                                'list_price': _price,
                                'type': ptype,
                                'standard_price': _price,
                                'default_code': _departure,
                                'uom_id': uom_id.id if uom_id else False,
                                'uom_id': uom_id.id if uom_id else False,
                                'resource_type': resource_type,
                            })

                    if __type == "chapter":
                        _qty = 1

                    if __type == "departure" and _qty == 0:
                        _qty = 1

                    con_val = {
                        'code': _departure,
                        'name': _name,
                        'uom_id': uom_id.id if uom_id else False,
                        'budget_id': self.budget_id.id,
                        'type': __type,
                        'product_id': product_id.id if product_id else False,
                        'quantity': _qty,
                        'amount_fixed': _price,
                    }
                    concept_id = concept_obj.create(con_val)

                if parent_id:
                    concept_id.parent_id = parent_id.id

            except Exception as exp:
                _logger.info("Error: {}".format(exp))
                raise UserError(exp)








        _logger.info("END import_template_xls")




    def import_3000_template(self):
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))

        if first_row[0] != "COD":
            raise UserError(_("Please check template header in position: {}").format(0))

        if first_row[1] != "RUBRO":
            raise UserError(_("Please check template header in position: {}").format(1))

        if first_row[2] != "U":
            raise UserError(_("Please check template header in position: {}").format(2))

        if first_row[3] != "CANTIDAD":
            raise UserError(_("Please check template header in position: {}").format(3))

        if first_row[4] != "UNITARIO":
            raise UserError(_("Please check template header in position: {}").format(4))

        if first_row[5] != "SUBTOTAL":
            raise UserError(_("Please check template header in position: {}").format(5))


        new_budget = self.env['bim.budget'].create({'name': self.budget_name,
                                                    'project_id': self.project_id.id,
                                                    'currency_id': self.project_id.currency_id.id
                                                    })
        self.budget_id = new_budget.id

        concept_obj = self.env['bim.concepts']
        product_obj = self.env['product.product']
        uom_obj = self.env['uom.uom']
        line_count = 1
        last_departure = False
        for count, row in enumerate(range(1, sheet.nrows), 2):
            line_count +=1
            val = {}
            for col in range(sheet.ncols):
                if sheet.cell_value(row, 0) == "":
                    break
                else:
                    val[first_row[col]] = sheet.cell_value(row, col)
            try:
                if len(val) > 0:
                    if str(val['U']) =="" and str(val['CANTIDAD']) =="":
                        parent_id = self.create_chapter3000(val, new_budget, concept_obj, uom_obj)
                    else:
                        last_departure = self.create_departure3000(val, new_budget, concept_obj, uom_obj, parent_id)
            except Exception as exp:
                _logger.info("Error: {}".format(exp))
                raise UserError(exp)
        self.state = 'done'
        for concept in new_budget.concept_ids.filtered_domain([('type','=','departure')]):
            if concept.child_ids:
                concept.amount_type = 'compute'


    def create_chapter3000(self, val, budget, concept_obj, uom_obj):
        code = str(val['COD']).replace('#','')
        name = val['RUBRO']
        uom_id = False
        if val['U'] != "":
            uom_id = uom_obj.search(['|',('name','=',val['U']),('alt_names','ilike',val['U'])], limit=1)
        if name == "":
            name = _("Empty")
        concept_obj = concept_obj.create({
            'code': code,
            'name': name,
            'uom_id': uom_id.id if uom_id else False,
            'budget_id': budget.id,
            'type': 'chapter'
        })

        return concept_obj

    def create_departure3000(self, val, budget, concept_obj, uom_obj, parent_id):
        code = str(val['COD'])
        level = code.count('.')
        code_splitted = code.split('.')
        departure_code_len = len(code_splitted[level])
        parent_code = code[:-departure_code_len-1]

        quantity = 1
        price = 0
        if not '#' in str(val['COD']):
            quantity = 0
            if (not '-' in str(val['CANTIDAD']) and val['CANTIDAD'] != '') or (len(str(val['CANTIDAD']))>1 and val['CANTIDAD'] != '' and float(val['CANTIDAD']) < 0):
                quantity = val['CANTIDAD']
            if (len(str(val['UNITARIO']))>1 and val['UNITARIO'] != ''):
                price = val['UNITARIO']
            if (str(type(val['SUBTOTAL'])) != "<class 'float'>") or (str(type(val['SUBTOTAL'])) == "<class 'float'>" and float(val['SUBTOTAL']) == 0):
                return False
        name = val['RUBRO']
        concept_type = 'departure'
        uom_id = False
        if val['U'] != "":
            uom_id = uom_obj.search(['|', ('name', '=', val['U']), ('alt_names', 'ilike', val['U'])], limit=1)

        if name == "":
            name = _("Empty")
        concept = concept_obj.create({
            'code': code,
            'name': name,
            'budget_id': budget.id,
            'uom_id': uom_id.id if uom_id else False,
            'parent_id': parent_id.id,
            'quantity': float(quantity),
            'amount_fixed': float(price),
            'amount_type': 'fixed',
            'type': concept_type
        })
        return concept


    def import_apu_2000(self):
        bim_concept_template_id = False

        type_calc = self.env['bim.general.config'].search([('key', '=', 'type_calc')], limit=1)

        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))
        line_count = 0

        for count, row in enumerate(range(1, sheet.nrows), 2):
            line_count +=1
            val = {}
            for col in range(sheet.ncols):
                if sheet.cell_value(row, 0) == "":
                    break
                else:
                    val[first_row[col]] = sheet.cell_value(row, col)
            try:
                if len(val) > 0:
                    uom_id = self.env['uom.uom'].search(['|',('name','=',val['UNIDAD']),('alt_names','ilike',val['UNIDAD'])], limit=1)
                    if not uom_id:
                        uom_id = self.env['uom.uom'].search([], limit=1)

                    if not '#' in str(val['PARTIDA']) and '.' in str(val['PARTIDA']) and str(val['NAT']) =="":
                        if bim_concept_template_id:
                            bim_concept_template_id.update_all()

                        bim_concept_template_id = self.env['bim.concept.template'].search([('code','=',val['PARTIDA'])], limit=1)
                        if not bim_concept_template_id:
                            performance = val['RENDIMIENTO']
                            bim_concept_template_vals = {
                                'code': val['PARTIDA'],
                                'name': val['DESCRIPCION DE PARTIDA'],
                                'uom_id': uom_id.id if uom_id else False,
                                'performance': performance if performance else 0,
                                'type_calc' : type_calc.value if type_calc else 'standard',
                            }

                            bim_concept_template_id = self.env['bim.concept.template'].create(bim_concept_template_vals)

                    elif str(val['NAT']) in RESOURSES:
                        _logger.info("create resource 2")
                        _logger.info(val)
                        _type = val['NAT']

                        if _type == "MO":
                            type = "H"
                        elif _type == "MAT":
                            type = "M"
                        elif _type == "EQUIPO":
                            type = "Q"
                        elif _type == "%":
                            type = "A"
                        elif _type == "SUBCONTRATO":
                            type = "S"
                        else:
                            type = "M"


                        if self.create_all_products:
                            product_id = self.env['product.product'].search([
                                            ('default_code','=',val['PARTIDA']),
                                        ], limit=1)
                            if not product_id:
                                v_vals = {
                                    'name': val['DESCRIPCION DE PARTIDA'],
                                    'default_code': val['PARTIDA'],
                                    'type': 'product' if type == 'M' else 'service',
                                    'list_price': val['PRECIO'],
                                    'standard_price': val['PRECIO'],
                                    'uom_id': uom_id.id if uom_id else False,
                                    'uom_id': uom_id.id if uom_id else False,
                                    'resource_type': type,
                                }

                                _logger.info("v_vals: {}".format(v_vals))

                                product_id = self.env['product.product'].create(v_vals)

                        resource_vals = {
                                'code': val['PARTIDA'],
                                'name': val['DESCRIPCION DE PARTIDA'],
                                'uom_id': uom_id.id if uom_id else self.uom_id.id,
                                'template_id' : bim_concept_template_id.id,
                                'type': type,
                                'quantity': val['MEDICION'],
                                'price': val['PRECIO'],
                                'product_id': product_id.id if product_id else False,
                            }

                        _logger.info(resource_vals)


                        line = self.env['bim.concept.template.line'].create(resource_vals)

                        _logger.info("line: {}".format(line))

                if bim_concept_template_id:
                    bim_concept_template_id.update_all()

            except Exception as exp:
                _logger.info("Error: {}".format(exp))
                raise UserError(exp)

        self.state = 'done'



    def import_2000_template(self):
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))
        # validando al cabecera
        if first_row[0] != "PARTIDA":
            raise UserError(_("Please check template header in position: {}").format(0))
        if first_row[1] != "NAT":
            raise UserError(_("Please check template header in position: {}").format(1))
        if first_row[2] != "UNIDAD":
            raise UserError(_("Please check template header in position: {}").format(2))
        if first_row[3] != "DESCRIPCION DE PARTIDA":
            raise UserError(_("Please check template header in position: {}").format(3))
        if first_row[4] != "MEDICION":
            raise UserError(_("Please check template header in position: {}").format(4))
        if first_row[5] != "PRECIO":
            raise UserError(_("Please check template header in position: {}").format(5))
        if first_row[6] != "IMPORTE":
            raise UserError(_("Please check template header in position: {}").format(6))


        if not self.budget_id:
            new_budget = self.env['bim.budget'].create({'name': self.budget_name,
                                                        'project_id': self.project_id.id,
                                                        'currency_id': self.project_id.currency_id.id
                                                        })
            self.budget_id = new_budget.id
        else:
            new_budget = self.budget_id

        concept_obj = self.env['bim.concepts']
        product_obj = self.env['product.product']
        uom_obj = self.env['uom.uom']
        line_count = 1
        last_departure = False
        for count, row in enumerate(range(1, sheet.nrows), 2):
            line_count +=1
            val = {}
            for col in range(sheet.ncols):
                if sheet.cell_value(row, 0) == "":
                    break
                else:
                    val[first_row[col]] = sheet.cell_value(row, col)
            try:
                if len(val) > 0:
                    if not '.' in str(val['PARTIDA']) and str(val['NAT']) =="" and str(val['UNIDAD']) =="":
                        self.create_chapter(val, new_budget, concept_obj, uom_obj)
                    elif '.' in str(val['PARTIDA']) and '#' in str(val['PARTIDA']) and str(val['NAT']) =="":
                        self.create_sub_chapter(val, new_budget, concept_obj, uom_obj)
                    elif not '#' in str(val['PARTIDA']) and '.' in str(val['PARTIDA']) and str(val['NAT']) =="":
                        last_departure = self.create_departure(val, new_budget, concept_obj, uom_obj)
                    elif '#' in str(val['PARTIDA']) or '.' in str(val['PARTIDA']) and (str(val['NAT']) in RESOURSES and self.version == '2000'):
                        if last_departure:
                            self.create_resource(val, new_budget, concept_obj, uom_obj, last_departure, product_obj)
                    elif not '#' in str(val['PARTIDA']) and not '.' in str(val['PARTIDA']) and (str(val['NAT']) in RESOURSES and self.version == '2000'):
                        if last_departure:
                            self.create_resource(val, new_budget, concept_obj, uom_obj, last_departure, product_obj)
            except Exception as exp:
                _logger.info("Error: {}".format(exp))
                raise UserError(exp)
        self.state = 'done'
        for concept in new_budget.concept_ids.filtered_domain([('type','=','departure')]):
            if concept.child_ids:
                concept.amount_type = 'compute'

    def import_1000_template(self):
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        first_row = []
        for col in range(sheet.ncols):
            first_row.append(sheet.cell_value(0, col))
        # validando al cabecera
        if first_row[0] != "PARTIDA":
            raise UserError(_("Please check template header in position: {}").format(0))
        if first_row[1] != "NAT":
            raise UserError(_("Please check template header in position: {}").format(1))
        if first_row[2] != "UNIDAD":
            raise UserError(_("Please check template header in position: {}").format(2))
        if first_row[3] != "DESCRIPCION DE PARTIDA":
            raise UserError(_("Please check template header in position: {}").format(3))
        if first_row[4] != "MEDICION":
            raise UserError(_("Please check template header in position: {}").format(4))
        if first_row[5] != "PRECIO":
            raise UserError(_("Please check template header in position: {}").format(5))
        if first_row[6] != "IMPORTE":
            raise UserError(_("Please check template header in position: {}").format(6))
        new_budget = self.env['bim.budget'].create({'name': self.budget_name,
                                                    'project_id': self.project_id.id,
                                                    'currency_id': self.project_id.currency_id.id
                                                    })
        self.budget_id = new_budget.id

        concept_obj = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']
        line_count = 1
        for count, row in enumerate(range(1, sheet.nrows), 2):
            line_count +=1
            val = {}
            for col in range(sheet.ncols):
                if sheet.cell_value(row, 0) == "":
                    break
                else:
                    val[first_row[col]] = sheet.cell_value(row, col)
            try:
                if len(val) > 0:
                    if not '.' in str(val['PARTIDA']) and str(val['UNIDAD']) =="":
                        self.create_chapter(val, new_budget, concept_obj, uom_obj)
                    elif '.' in str(val['PARTIDA']) and '#' in str(val['PARTIDA']):
                        self.create_sub_chapter(val, new_budget, concept_obj, uom_obj)
                    elif not '#' in str(val['PARTIDA']) and '.' in str(val['PARTIDA']):
                        self.create_departure(val, new_budget, concept_obj, uom_obj)

            except Exception as exp:
                raise UserError(exp)
        self.state = 'done'
        for concept in new_budget.concept_ids.filtered_domain([('type','=','departure')]):
            if concept.child_ids:
                concept.amount_type = 'compute'

    def create_chapter(self, val, budget, concept_obj, uom_obj):
        code = str(val['PARTIDA']).replace('#','')
        name = val['DESCRIPCION DE PARTIDA']
        uom_id = False
        if val['UNIDAD'] != "":
            uom_id = uom_obj.search(['|',('name','=',val['UNIDAD']),('alt_names','ilike',val['UNIDAD'])], limit=1)
        if name == "":
            name = _("Empty")
        concept_obj.create({
            'code': code,
            'name': name,
            'uom_id': uom_id.id if uom_id else False,
            'budget_id': budget.id,
            'type': 'chapter'
        })

    def create_sub_chapter(self, val, budget, concept_obj, uom_obj):
        code = str(val['PARTIDA']).replace('#','')
        name = val['DESCRIPCION DE PARTIDA']
        uom_id = False
        level = code.count('.')
        code_splitted = code.split('.')
        departure_code_len = len(code_splitted[level])
        parent_code = code[:-departure_code_len - 1]
        parent_id = concept_obj.search([('code', '=', parent_code), ('budget_id', '=', budget.id)])
        if val['UNIDAD'] != "":
            uom_id = uom_obj.search(['|',('name','=',val['UNIDAD']),('alt_names','ilike',val['UNIDAD'])], limit=1)
        if name == "":
            name = _("Empty")
        concept_obj.create({
            'code': code,
            'parent_id': parent_id.id if parent_id else False,
            'name': name,
            'uom_id': uom_id.id if uom_id else False,
            'budget_id': budget.id,
            'type': 'chapter'
        })

    def create_departure(self, val, budget, concept_obj, uom_obj):
        code = str(val['PARTIDA']).replace('#','')
        level = code.count('.')
        code_splitted = code.split('.')
        departure_code_len = len(code_splitted[level])
        parent_code = code[:-departure_code_len-1]
        parent_id = concept_obj.search([('code','=',parent_code),('budget_id','=',budget.id)])
        quantity = 1
        price = 0

        if not '#' in str(val['PARTIDA']):
            quantity = 0
            if (not '-' in str(val['MEDICION']) and val['MEDICION'] != '') or (len(str(val['MEDICION']))>1 and val['MEDICION'] != '' and float(val['MEDICION']) < 0):
                quantity = val['MEDICION']
            if (len(str(val['PRECIO']))>1 and val['PRECIO'] != ''):
                price = val['PRECIO']

        name = val['DESCRIPCION DE PARTIDA']
        concept_type = 'departure'
        uom_id = False
        if val['UNIDAD'] != "":
            uom_id = uom_obj.search(['|', ('name', '=', val['UNIDAD']), ('alt_names', 'ilike', val['UNIDAD'])], limit=1)
        if not parent_id:
            count = 1
            while count <= level:
                parent_id = concept_obj.search([('code', '=', code_splitted[level-count]), ('budget_id', '=', budget.id)])
                count += 1
                if parent_id:
                    break
        if not parent_id:
            concept_type = 'chapter'

        if name == "":
            name = _("Empty")

        concept = concept_obj.create({
            'code': code,
            'name': name,
            'budget_id': budget.id,
            'uom_id': uom_id.id if uom_id else False,
            'parent_id': parent_id.id if parent_id else False,
            'quantity': float(quantity),
            'amount_fixed': float(price),
            'amount_type': 'fixed',
            'type': concept_type
        })

        _logger.info("concept created www : {}".format(concept))

        try:
            id_bim = val['ID']
            concept.id_bim = id_bim
        except:
            pass

        try:
            performance = val['RENDIMIENTO']
            if performance:
                concept.performance = float(performance)
        except:
            pass


        _logger.info("end create_departure")
        return concept

    def create_resource(self, val, budget, concept_obj, uom_obj, last_parent_id, product_obj):
        category = self.env.company.bim_product_category_id
        code = str(val['PARTIDA'])
        quantity = 1
        price = 0
        if not '#' in str(val['PARTIDA']):
            quantity = 0
            if (not '-' in str(val['MEDICION']) and val['MEDICION'] != '') or (len(str(val['MEDICION']))>1 and val['MEDICION'] != '' and float(val['MEDICION']) < 0):
                quantity = val['MEDICION']
            if (len(str(val['PRECIO']))>1 and val['PRECIO'] != ''):#(not '-' in str(val['PRECIO']) and val['PRECIO'] != '') or
                price = val['PRECIO']
            if (str(type(val['IMPORTE'])) != "<class 'float'>") or (str(type(val['IMPORTE'])) == "<class 'float'>" and float(val['IMPORTE']) == 0) and str(val['NAT']) != "%":
                return False
        name = val['DESCRIPCION DE PARTIDA']
        concept_type = 'material'
        res_type = 'M'


        _logger.info("val: {}".format(val))

        _logger.info("----> NAT: {}".format(val['NAT']))

        if str(val['NAT']) == "MO":
            concept_type = 'labor'
            res_type = 'H'
        elif str(val['NAT']) == "EQUIPO":
            concept_type = 'equip'
            res_type = 'Q'
        elif str(val['NAT']) == "SC":
            concept_type = 'subcontract'
            res_type = 'S'
        elif str(val['NAT']) == "%":
            concept_type = 'aux'

        _logger.info("concept_type: {}".format(concept_type))

        uom_id = False
        if val['UNIDAD'] != "":
            uom_id = uom_obj.search(['|', ('name', '=', val['UNIDAD']), ('alt_names', 'ilike', val['UNIDAD'])], limit=1)
            if not uom_id:
                uom_id = uom_obj.search(['|', ('name', '=', 'Unidades'), ('alt_names', 'ilike', 'ud')], limit=1)

        else:
            if self.uom_id:
                uom_id = self.uom_id
            else:
                raise ValidationError(_("Unit of measure not found for resource %s") % name)

        if name == "":
            name = _("Empty")
        product = product_obj.search(['|', ('default_code', '=', code), ('barcode', '=', code)],
                                     limit=1) if self.create_all_products else self.product_id

        concept = concept_obj.create({
            'code': code,
            'name': name,
            'budget_id': budget.id,
            'uom_id': uom_id.id if uom_id else False,
            'parent_id': last_parent_id.id if last_parent_id else False,
            'quantity': float(quantity),
            'amount_fixed': float(price),
            'amount_type': 'fixed',
            'type': concept_type
        })

        _logger.info("concept created: {}".format(concept))

        if not product and concept_type != 'aux':
            product = product_obj.create({
                'name': name,
                'resource_type': res_type,
                'type': 'product' if concept_type == 'material' else 'service',
                'list_price': float(price) if self.product_cost_or_price == 'price' else 0,
                'standard_price': float(price) if self.product_cost_or_price == 'cost' else 0,
                'default_code': code,
                'categ_id': category.id,
                'uom_id': uom_id.id if uom_id else False,
                'uom_id': uom_id.id if uom_id else False,
            })
        if concept_type != 'aux':
            concept.product_id = product

        _logger.info("product" " created: {}".format(product))

        _logger.info("end create_resource")

    def unlink(self):
        for record in self:
            if record.state != "to_execute":
                raise UserError(_("Importer Records can be only deleted in 'To Execute' state!"))
        return super().unlink()

