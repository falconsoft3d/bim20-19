import base64
import datetime
import io
import traceback
from odoo.exceptions import UserError
import bs4
import xlrd
import os
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)
import re

class BimImportTemp(models.Model):
    _name = 'bim.import.temp'
    _description = 'Importation Project'
    _inherit = ['mail.thread']
    _rec_name = 'filename'
    _order = 'id desc'

    name = fields.Char('Code', default='New', tracking=True)

    version = fields.Selection([
                                    ('8.8', 'Excel Template 8.8'),
                                    ('bc3', 'BC3'),
                                    ('ms_xml', 'Project XML'),
                                    ('ip3', 'IP-3'),
                                    ('ip3-v2', 'IP-3 V2'),
                                    ('ip3-db1', 'IP-3 DB1'),
                                    ('lulo', 'Lulo V1'),
                                ], 'Version', default='bc3', required=True, tracking=True)


    project_id = fields.Many2one('bim.project', 'Project', tracking=True, ondelete='cascade')
    create_all_products = fields.Boolean('Create non-existent products', tracking=True)
    product_id = fields.Many2one('product.product', 'Default product', default=lambda self: self.env.ref('base_bim_2.default_product', raise_if_not_found=False), tracking=True)
    excel_file = fields.Binary('Excel File', required=True)
    filename = fields.Char('File name')
    state = fields.Selection([('to_execute', 'To execute'), ('ongoing', 'In process'), ('done', 'Done'), ('error', 'Error')], 'Status', default='to_execute', tracking=True)
    error = fields.Text(readonly=True, default="")
    budget_id = fields.Many2one('bim.budget', 'Created budget', ondelete='cascade', copy=False)
    user_id = fields.Many2one('res.users', 'Responsable', readonly=True, required=True, default=lambda self: self.env.user)
    last_row = fields.Integer('Last Row', readonly=True, tracking=True)
    product_cost_or_price = fields.Selection([('price', 'Precio Venta'), ('cost', 'Costo Producto')],
                                             string='Asignar a', default='cost')
    import_stages = fields.Boolean()
    category_id = fields.Many2one('product.category')
    limit = fields.Integer('Limit', default=0)
    update = fields.Boolean('Update', default=False)
    default_uom_id = fields.Many2one('uom.uom', string='Unidad de medida',
        help='Si se especifica, se asignará a todos los conceptos importados que no tengan unidad de medida.')

    enconding = fields.Selection([
        ('latin-1', 'Latin-1')
        , ('utf-8', 'UTF-8')
    ], 'Encoding', default='latin-1', required=True)

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.import.temp') or 'New'
        return super().create(vals_list)


    @api.model
    def file_validator(self, fileformat):
        name, extension = os.path.splitext(fileformat)
        if self.version == '8.8' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'ip3' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'lulo' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'ip3-v2' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'ip3-db1' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == '2024_xls' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'fases' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == '2024_xls_2' and extension in ('.xls', '.xlsx'):
            return True
        elif self.version == 'bc3' and extension in ('.bc3'):
            return True
        elif self.version == 'ms_xml' and extension in ('.xml'):
            return True
        return False

    def action_import(self):
        if not self.file_validator(self.filename):
            raise UserError(_("File Extension does not match with Importation Version"))
        self.with_context(import_this=self.id).cron_start_import()

    @api.model
    def cron_start_import(self):
        record = self.browse(self.env.context.get('import_this'))
        if not record or record.state not in ['ongoing', 'to_execute']:
            record = self.search([('state', 'in', ['ongoing', 'to_execute'])], limit=1, order='state')
        if record.version == '8.8':
            with io.StringIO() as error_traceback:
                try:
                    record.import_8_8()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})

        elif record.version == 'fases':
            with io.StringIO() as error_traceback:
                try:
                    record.import_fases_xls()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == '2024_xls':
            with io.StringIO() as error_traceback:
                try:
                    record.import_2024_xls()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == '2024_xls_2':
            with io.StringIO() as error_traceback:
                try:
                    record.import_2024_xls_2()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == 'lulo':
            with io.StringIO() as error_traceback:
                try:
                    record.import_lulo()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == 'ip3-v2':
            with io.StringIO() as error_traceback:
                try:
                    record.import_ip3_v2()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})

        elif record.version == 'ip3-db1':
            with io.StringIO() as error_traceback:
                try:
                    record.import_ip3_db1()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == 'ip3':
            with io.StringIO() as error_traceback:
                try:
                    record.import_ip3()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})


        elif record.version == 'bc3':
            with io.StringIO() as error_traceback:
                try:
                    record.import_bc3()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})
        elif record.version == 'ms_xml':
            with io.StringIO() as error_traceback:
                try:
                    record.import_ms_xml()
                except:
                    traceback.print_exc(file=error_traceback)
                    error_traceback.seek(0)
                    record.write({'state': 'error', 'error': error_traceback.read()})
        else:
            record.write({'state': 'error', 'error': 'No implemented'})

        for concept in record.budget_id.concept_ids:
            if concept.type == 'departure':
                for m in concept.measuring_ids:
                    if m.name == '':
                        m.unlink()

                amount_subtotal = sum(measure.amount_subtotal for measure in concept.measuring_ids)
                if amount_subtotal > 0:
                    concept.quantity = amount_subtotal

        """
        # Revisamos las mediciones
        for concept in record.budget_id.concept_ids:
            if concept.type == 'departure':
                amount_subtotal = sum(measure.amount_subtotal for measure in concept.measuring_ids)
                if amount_subtotal > 0:
                    concept.quantity = amount_subtotal"""


        return True

    def back_draft(self):
        self.write({'state': 'to_execute'})


    def format_number(self, number):
        # le quito el .
        number = number.replace(".", "")
        # le cambio la , por .
        number = number.replace(",", ".")
        return number




    def import_2024_xls_2(self):
        _logger.info('BEGIN: import_2024_xls_2')


        # DATA
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        budget = self.env['bim.budget']
        concept_obj = departure = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']


        last_row = 0
        read_rows = 0

        mode = ""
        count_ = 0
        code = ""

        is_departure = False
        departure = False
        parent = False
        mode = ""


        aux_uom_id = uom_obj.search([('name', '=', "%")], limit=1)
        hh_uom_id = uom_obj.search([('name', '=', "HH")], limit=1)

        if not aux_uom_id:
            raise UserError(_("No existe la unidad de medida %"))

        if not hh_uom_id:
            raise UserError(_("No existe la unidad de medida HH"))

        for i, row in enumerate(list(sheet.get_rows())[last_row:], last_row):
            count_ += 1
            read_rows += 1

            code = row[1].value
            description = row[2].value
            unit = row[3].value
            quantity = row[5].value
            price = row[6].value

            # _logger.info('code: %s' % (code))

            if unit == 'Rendto:':
                is_departure = True
            else:
                is_departure = False

            if is_departure:
                _logger.info('is_departure: %s' % (is_departure))
                # Buscamos si existe esa partida
                departure = self.env['bim.concepts'].search([
                        ('code', '=', code),
                        ('budget_id', '=', self.budget_id.id),
                        ], limit=1)
                if departure:
                    _logger.info('departure: %s' % (departure))

            if description == 'Mano de Obra':
                mode = 'labor'

            elif description == 'Materiales':
                mode = 'material'

            elif description == 'Equipos':
                mode = 'equip'

            elif description == 'Otros':
                mode = 'aux'

            elif description == 'Subcontratos':
                mode = 'subcontratos'


            if code and description and unit and quantity and price:
                if mode == 'subcontratos':
                    # MANO DE OBRA
                    _logger.info('SUB CONTRATO')
                    product_id = self.env['product.product'].search([('default_code', '=', code)], limit=1)


                    uom_id = False
                    if not product_id:
                        uom_id = hh_uom_id
                        # creamos la unidad de medida si no existe

                        product_id = self.env['product.product'].create({
                            'name': description,
                            'default_code': code,
                            'type': 'service',
                            'standard_price': price,
                            'resource_type': 'S',
                        })

                        if uom_id:
                            product_id.uom_id = uom_id.id
                            product_id.uom_po_id = uom_id.id

                    vals = {
                        'type': 'subcontract',
                        'budget_id': departure.budget_id.id,
                        'quantity': quantity,
                        'name': description,
                        'code': code,
                        'parent_id': departure.id,
                        'amount_fixed': price,
                        'product_id': product_id.id,
                        'uom_id': product_id.uom_id.id,
                    }

                    _logger.info('vals: %s' % (vals))

                    labor_id = self.env['bim.concepts'].create(vals)


                if mode == 'aux':
                    # %
                    uom_id = aux_uom_id

                    _logger.info('AUX')
                    vals = {
                        'type': 'aux',
                        'budget_id': departure.budget_id.id,
                        'name': description,
                        'code': code,
                        'parent_id': departure.id,
                        'amount_fixed': quantity,
                        'uom_id': product_id.uom_id.id,
                    }

                    _logger.info('vals: %s' % (vals))
                    labor_id = self.env['bim.concepts'].create(vals)
                    if uom_id:
                        labor_id.uom_id = uom_id.id

                if mode == 'material':
                    # MATERIALES
                    _logger.info('MATERIALES')
                    product_id = self.env['product.product'].search([('default_code', '=', code)], limit=1)


                    uom_id = False
                    if not product_id:
                        _logger.info('unit: %s' % (unit))
                        uom_id = uom_obj.search([('name', '=', unit)], limit=1)

                        product_id = self.env['product.product'].create({
                            'name': description,
                            'default_code': code,
                            'type': 'consu',
                            'standard_price': price,
                            'resource_type': 'M',
                        })

                        if uom_id:
                            product_id.uom_id = uom_id.id
                            product_id.uom_po_id = uom_id.id



                    vals = {
                        'type': 'material',
                        'budget_id': departure.budget_id.id,
                        'quantity': quantity,
                        'name': description,
                        'code': code,
                        'parent_id': departure.id,
                        'amount_fixed': price,
                        'product_id': product_id.id,
                        'uom_id': product_id.uom_id.id,
                    }

                    _logger.info('vals: %s' % (vals))

                    labor_id = self.env['bim.concepts'].create(vals)


                if mode == 'labor':
                    # MANO DE OBRA
                    _logger.info('MANO DE OBRA')
                    product_id = self.env['product.product'].search([('default_code', '=', code)], limit=1)


                    uom_id = False
                    if not product_id:
                        _logger.info('unit: %s' % (unit))
                        uom_id = uom_obj.search([('name', '=', unit)], limit=1)
                        # creamos la unidad de medida si no existe

                        product_id = self.env['product.product'].create({
                            'name': description,
                            'default_code': code,
                            'type': 'service',
                            'standard_price': price,
                            'resource_type': 'H',
                        })

                        if uom_id:
                            product_id.uom_id = uom_id.id
                            product_id.uom_po_id = uom_id.id



                    vals = {
                        'type': 'labor',
                        'budget_id': departure.budget_id.id,
                        'quantity': quantity,
                        'name': description,
                        'code': code,
                        'parent_id': departure.id,
                        'amount_fixed': price,
                        'product_id': product_id.id,
                        'uom_id': product_id.uom_id.id,
                    }

                    _logger.info('vals: %s' % (vals))

                    labor_id = self.env['bim.concepts'].create(vals)
        _logger.info('END: import_2024_xls_2')






    def import_fases_xls(self):
        _logger.info('BEGIN: import_fases_xls')


        # DATA
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        budget = self.env['bim.budget']
        concept_obj = departure = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']


        # Creamos el presupuesto

        last_row = 0
        read_rows = 0

        mode = ""
        count_ = 0
        code = ""

        parent = False
        for i, row in enumerate(list(sheet.get_rows())[last_row:], last_row):
            count_ += 1
            read_rows += 1

            code = str(row[0].value).replace(" ", "").replace(".0", ".")
            # si el primer caracter es 0 lo elimino
            try:
                code = code[1:] if code[0] == "0" else code
            except:
                pass
            especialidad = row[1].value
            fase = row[2].value
            subfase = row[3].value

            if fase == 'FASE':
                continue

            if especialidad == 'ESPECIALIDAD':
                continue

            # revisamos si existe la especialidad
            if len(especialidad) > 0:
                concept_specialty_id = self.env['concept.specialty'].search([
                    ('name', '=', especialidad),
                    ('description', '=', especialidad),
                ], limit=1)

                if not concept_specialty_id:
                    concept_specialty_id = self.env['concept.specialty'].create({
                        'name': especialidad,
                        'description' : especialidad,
                    })


            # revisamos si existe la fase
            if len(str(fase)) > 0:
                fase = str(fase).replace(" ", "").replace(".0", "")
                subfase = str(subfase).replace(" ", "").replace(".0", "")


                concept_phase_id = self.env['concept.phase'].search([
                    ('name', '=', fase),
                ], limit=1)

                if not concept_phase_id:
                    concept_phase_id = self.env['concept.phase'].create({
                        'name': fase,
                        'description' : fase,
                    })



            if len(str(subfase)) > 0:
                concept_sub_phase_id = self.env['concept.phase'].search([
                    ('name', '=', subfase),
                    ('parent_id', '=', concept_phase_id.id),
                ], limit=1)

                if not concept_sub_phase_id:
                    concept_sub_phase_id = self.env['concept.phase'].create({
                        'name': subfase,
                        'description' : subfase,
                        'parent_id': concept_phase_id.id,
                    })

            if code:
                departure_id = self.env['bim.concepts'].search([
                    ('note', '=', code),
                    ('budget_id', '=', self.budget_id.id),
                ], limit=1)


                if departure_id:
                    _logger.info('code encontrado: %s' % (code))
                    try:
                        departure_id.concept_specialty_id = concept_specialty_id.id
                        departure_id.concept_phase_id = concept_phase_id.id
                        departure_id.sub_phase_id = concept_sub_phase_id.id
                    except:
                        pass
                else:
                    _logger.info('code no encontrado: %s' % (code))


        _logger.info('END: import_fases_xls')



    def import_2024_xls(self):
        _logger.info('BEGIN: Importing 2024_xls')

        # DATA
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        budget = self.env['bim.budget']
        concept_obj = departure = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']

        # Creamos el presupuesto
        budget = budget.create({
                    'name': self.project_id.nombre,
                    'project_id': self.project_id.id,
                    'currency_id': self.project_id.currency_id.id,
                })

        general_id = self.env['bim.concepts'].create({
            'type': 'chapter',
            'budget_id': budget.id,
            'quantity': 1,
            'name': 'GENERAL',
            'code': '01',
        })



        self.budget_id = budget
        if budget.space_ids:
            default_space = budget.space_ids[0]
        else:
            default_space = self.env.ref('base_bim_2.default_bim_budget_space')

        if budget.space_ids:
            default_space = budget.space_ids[0]

        last_row = 0
        read_rows = 0

        mode = ""
        count_ = 0
        code = ""

        parent = False
        for i, row in enumerate(list(sheet.get_rows())[last_row:], last_row):
            count_ += 1
            read_rows += 1

            edt = row[0].value
            dificultad = row[1].value
            produccion = row[2].value
            codigo = row[3].value
            resumen = row[4].value
            cant = row[5].value
            unidad = row[6].value
            pres = row[7].value
            imp_pres = row[8].value



            if edt and cant == 1 and not unidad:
                chapter_id = self.env['bim.concepts'].create({
                    'type': 'chapter',
                    'budget_id': budget.id,
                    'quantity': 1,
                    'name': resumen,
                    'code': edt,
                    'parent_id': general_id.id,
                    'note' : codigo,
                })


            if edt and codigo and unidad:
                if edt != "EDT":
                    daparture_id = self.env['bim.concepts'].create({
                        'type': 'departure',
                        'budget_id': budget.id,
                        'quantity': cant,
                        'name': resumen,
                        'code': edt,
                        'parent_id': general_id.id,
                        'note' : codigo,
                    })

        # Organizamos Los Capitulos.
        apus_ids = self.env['bim.concepts'].search([('budget_id', '=', budget.id)], order='code')

        for apu in apus_ids:
            if apu.code.count('.') >= 1:
                version = apu.code
                last_dot_index = version.rfind('.')
                parent_code = version[:last_dot_index] if last_dot_index != -1 else version
                parent_id = self.env['bim.concepts'].search([
                                    ('code', '=', parent_code),
                                    ('budget_id', '=', budget.id),
                                    ('type', '=', 'chapter')
                                    ], limit=1)
                if parent_id:
                    apu.parent_id = parent_id.id

        # cambiamos el codigo por la nota limpiandola
        for apu in apus_ids:
            if apu.note:
                _code = apu.code
                apu.code = apu.note
                apu.note = _code

        self.state = 'done'
        _logger.info('END: Importing IP3')


    def import_ip3_db1(self):
        _logger.info('BEGIN: import_ip3_db1')
        bim_concept_template_id = None
        numer_apu = 0

        # Decodificar y leer el archivo Excel
        try:
            data = base64.b64decode(self.excel_file)
            work_book = xlrd.open_workbook(file_contents=data)
        except Exception as e:
            _logger.error('Error leyendo el archivo Excel: %s', e)
            raise ValueError("El archivo Excel no es válido o no puede ser procesado.")

        # Crear el presupuesto asociado al proyecto
        budget = self.env['bim.budget'].create({
            'name': self.project_id.name,
            'project_id': self.project_id.id,
            'currency_id': self.project_id.currency_id.id,
            'type_calc': 'apu',
        })

        if budget :
            self.budget_id = budget


        # Procesar cada hoja del archivo Excel
        _counter = 0
        _counter_row = 0
        inicio = 0
        sheet = work_book.sheet_by_index(0)
        _logger.info('Procesando hoja: %s', sheet.name)
        mode = ""  # Para identificar la sección actual
        mat = False
        eq = False
        mo = False
        sub = False

        for row_index in range(sheet.nrows):
            _counter_row += 1
            row = sheet.row(row_index)
            next = False
            r1 = row[1].value

            _logger.info("row >> : %s", row)
            if r1 and isinstance(r1, str) and "\n" in r1:
                _logger.info("-------------------------------->")
                if '\n' in r1:
                    codigo, descripcion = r1.split('\n', 1)

                    _logger.info("Codigo: --%s--", codigo)
                    _logger.info("Descripcion: --%s--", descripcion)

                    bim_concept_template_id = self.env['bim.concept.template'].search([
                                            ('code', '=', codigo),
                                            ('name', '=', descripcion),
                                        ], limit=1)


                    if not bim_concept_template_id:
                        _logger.info("bim_concept_template_id No existe")
                        bim_concept_template_id = self.env['bim.concept.template'].create({
                                            'code': codigo,
                                            'name' : descripcion,
                                            'bim_id' : codigo,
                                        })

                    else:
                        _logger.info("bim_concept_template_id existe: --%s--", bim_concept_template_id)
                        try:
                            if bim_concept_template_id.template_line_ids:
                                bim_concept_template_id.template_line_ids.unlink()
                        except:
                            _logger.info("Error tratando de borrar las lineas")


            r2 = row[1].value
            if bim_concept_template_id:
                if r2 and isinstance(r2, str) and "Unidad:" in r2:
                    r22 = r2.replace("Unidad: ", "")
                    _logger.info("Unidad: --%s--", r22)
                    _logger.info("bim_concept_template_id: --%s--", bim_concept_template_id)
                    bim_concept_template_id.uom_id = self._get_uom(r22)

                    # rendimiento
                    r23 = row[4].value
                    rend = r23.replace("Rendimiento: ", "").replace(",", ".")
                    bim_concept_template_id.performance = rend


            r3 = row[3].value
            if r3:
                # _logger.info("row %s", row)

                if r3 == 'MATERIALES':
                    mat = True
                    eq = False
                    mo = False

                if r3 == 'EQUIPOS':
                    eq = True
                    mo = False
                    mat = False

                if r3 == 'MANO DE OBRA':
                    mo = True
                    mat = False
                    eq = False


                # MATERALES
                if mat and r3 != 'MATERIALES':
                    _logger.info("mat")

                    # paso r3 de cel a string
                    template_id = bim_concept_template_id.id
                    code = row[2].value.strip()
                    name = row[3].value.strip()
                    text_uom = row[7].value.strip()
                    qty = row[8].value or 0.0
                    precio = row[10].value or 0.0
                    dep = row[12].value or 0.0

                    vals = {
                        'name': name,
                        'type': 'consu',
                        'standard_price': float(precio),
                        'resource_type': 'M',
                        'default_code': code
                    }
                    product_id = self.env['product.product'].search([
                                            ('default_code', '=', code),
                                        ], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create(vals)


                    m_va = {
                        'template_id': template_id,
                        'name': name,
                        'code': code,
                        'quantity': qty,
                        'uom_id': self._get_uom(text_uom) if self._get_uom(text_uom) else product_id.uom_id.id,
                        'price': float(precio),
                        'product_id': product_id.id,
                        'type' : 'M',
                        'dep': dep,
                    }
                    bim_concept_template_line_id = self.env['bim.concept.template.line'].create(m_va)

                # EQUIPOS
                if eq and r3 != 'EQUIPOS':
                    _logger.info("eq")
                    # paso r3 de cel a string
                    template_id = bim_concept_template_id.id
                    code = row[2].value.strip()
                    name = row[3].value.strip()
                    # text_uom = row[7].value.strip()
                    qty = row[6].value or 0.0
                    precio = row[9].value or 0.0
                    dep = row[11].value or 0.0

                    vals = {
                        'name': name,
                        'type': 'service',
                        'standard_price': float(precio),
                        'resource_type': 'Q',
                        'default_code': code,

                    }

                    product_id = self.env['product.product'].search([
                                            ('default_code', '=', code),
                                        ], limit=1)


                    if not product_id:
                        product_id = self.env['product.product'].create(vals)


                    eq_va = {
                        'template_id': template_id,
                        'name': name,
                        'code': code,
                        'quantity': qty,
                        'uom_id': product_id.uom_id.id,
                        'price': float(precio),
                        'product_id': product_id.id,
                        'type' : 'Q',
                        'dep': dep,
                    }
                    bim_concept_template_line_id = self.env['bim.concept.template.line'].create(eq_va)

                # MANO DE OBRA
                if mo and r3 != 'MANO DE OBRA':
                    _logger.info("mo")
                    # paso r3 de cel a string
                    template_id = bim_concept_template_id.id
                    code = row[2].value.strip()
                    name = row[3].value.strip()
                    qty = row[6].value or 0.0
                    precio = row[9].value or 0.0
                    dep = row[11].value or 0.0

                    vals = {
                        'name': name,
                        'type': 'service',
                        'standard_price': float(precio),
                        'resource_type': 'H',
                        'default_code': code,
                    }

                    product_id = self.env['product.product'].search([
                                            ('default_code', '=', code),
                                        ], limit=1)


                    if not product_id:
                        product_id = self.env['product.product'].create(vals)


                    eq_va = {
                        'template_id': template_id,
                        'name': name,
                        'code': code,
                        'quantity': qty,
                        'uom_id': product_id.uom_id.id,
                        'price': float(precio),
                        'product_id': product_id.id,
                        'type' : 'H',
                        'dep': dep,
                    }
                    bim_concept_template_line_id = self.env['bim.concept.template.line'].create(eq_va)

        self.state = 'done'
        _logger.info('END: import_ip3_db1')


    def action_to_execute(self):
        self.state = 'to_execute'

    def import_ip3_v2(self):
        _logger.info('BEGIN: Importando archivo IP3 200')

        # Decodificar y leer el archivo Excel
        try:
            data = base64.b64decode(self.excel_file)
            work_book = xlrd.open_workbook(file_contents=data)
        except Exception as e:
            _logger.error('Error leyendo el archivo Excel: %s', e)
            raise ValueError("El archivo Excel no es válido o no puede ser procesado.")

        if self.budget_id :
            budget = self.budget_id

            # Limpiar el presupuesto
            try:
                concept_ids = self.env['bim.concepts'].search([('budget_id', '=', budget.id)])
                concept_ids.unlink()
            except Exception as e:
                _logger.error('Error limpiando el presupuesto: %s', e)

            try:
                concept_ids = self.env['bim.concepts'].search([('budget_id', '=', budget.id)])
                concept_ids.unlink()
            except Exception as e:
                _logger.error('Error limpiando el presupuesto: %s', e)

        else:
            # Crear el presupuesto asociado al proyecto
            # revisamos cuantos presupuestos tiene el proyecto
            num_budgets = self.env['bim.budget'].search_count([('project_id', '=', self.project_id.id)])


            budget = self.env['bim.budget'].create({
                'name': self.project_id.name + ' V' + str(num_budgets + 1),
                'project_id': self.project_id.id,
                'currency_id': self.project_id.currency_id.id,
                'type_calc': 'apu',
            })

            self.budget_id = budget

        # Crear capítulo principal
        chapter = self.env['bim.concepts'].create({
            'type': 'chapter',
            'budget_id': budget.id,
            'quantity': 1,
            'name': 'GENERAL',
            'code': '01',
        })

        # Procesar cada hoja del archivo Excel
        _counter = 0

        for sheet_index in range(work_book.nsheets):
            _counter += 1
            _counter_row = 0
            inicio = 0
            sheet = work_book.sheet_by_index(sheet_index)
            _logger.info('Procesando hoja: %s', sheet.name)

            mode = ""  # Para identificar la sección actual

            mat = False
            eq = False
            mo = False
            sub = False



            for row_index in range(sheet.nrows):
                _counter_row += 1
                row = sheet.row(row_index)
                # _logger.info("row >> : %s", row)
                next = False


                if row[1].value == "ANALISIS DE PRECIO UNITARIO":
                    # _logger.info('row: %s', row)
                    # _logger.info('_counter_row: %s', _counter_row)
                    inicio = _counter_row

                if inicio > 0 and _counter_row == inicio + 2:
                    # _logger.info('row dd: %s', row)
                    name_departure = row[1].value

                    # Creamos las partidas
                    _val = {
                        'type': 'departure',
                        'budget_id': budget.id,
                        'quantity': 1,
                        'name': name_departure,
                        'parent_id': chapter.id,
                        'code' : _counter,
                        }

                    departure = self.env['bim.concepts'].create(_val)

                    cant_mat = 0
                    cant_eq = 0
                    cant_mo = 0

                if inicio > 0:
                     # si la fila contiene "Código: SC"
                     if "Código:" in str(row[1].value):
                         departure.quantity = row[5].value.replace("Cantidad: ", "").replace(".", "").replace(",", ".")
                         departure.performance = row[11].value

                         # Dame el codigo
                         code = row[1].value.replace("Código: ", "")
                         departure.code = code

                if inicio > 0:
                    if row[1].value == "1.-MATERIALES":
                        mat = True
                        _logger.info('Inicio de Materiales')

                    if row[1].value == "2.-EQUIPOS":
                        mat = False
                        eq = True
                        _logger.info('Inicio los Equipos')

                    if row[1].value == "3.-MANO DE OBRA":
                        eq = False
                        mo = True
                        _logger.info('Inicio la Mano de Obra')






                    # Beneficios Sociales
                    try:
                        if "Prestaciones Sociales" in str(row[5].value):
                            s = row[5].value
                            m = re.search(r'(\d+)', s)
                            valor = float(m.group(1)) if m else None
                            hyd = budget.social_benefits
                            # comparamos las utilidades
                            if hyd != valor and valor > 0:
                                departure.use_social_benefits = True
                                departure.social_benefits = valor
                    except Exception as e:
                        _logger.error('Error leyendo Prestaciones Sociales: %s', e)



                    # Administración y Gastos Generales
                    try:
                        if "Administración y Gastos Generales" in str(row[7].value):
                            s = row[7].value
                            m = re.search(r'(\d+)', s)
                            valor = float(m.group(1)) if m else None

                            budget_asset_ids = self.env['bim.budget.assets'].search([
                                ('budget_id', '=', budget.id),
                            ])

                            if len(budget_asset_ids) > 0:
                                utilidad_hyd = 0.0
                                for ba in budget_asset_ids:
                                    if 'Administración y Gastos Generales' in ba.asset_id.desc:
                                        hyd = ba.value
                                        break

                                # comparamos las utilidades
                                if hyd != valor:
                                    departure.use_administration = True
                                    departure.administration = valor
                    except Exception as e:
                        _logger.error('Error leyendo Administración y Gastos Generales: %s', e)



                    # Utilidad o Imprevistos
                    try:
                        if "Utilidad o Imprevistos" in str(row[7].value):
                            s = row[7].value
                            m = re.search(r'(\d+)', s)
                            valor = float(m.group(1)) if m else None

                            budget_asset_ids = self.env['bim.budget.assets'].search([
                                ('budget_id', '=', budget.id),
                            ])

                            if len(budget_asset_ids) > 0:
                                utilidad_hyd = 0.0
                                for ba in budget_asset_ids:
                                    if 'Utilidad' in ba.asset_id.desc:
                                        utilidad_hyd = ba.value
                                        break

                                # comparamos las utilidades
                                if utilidad_hyd != valor:
                                    departure.use_utility = True
                                    departure.utility = valor
                    except Exception as e:
                        _logger.error('Error leyendo Utilidad o Imprevistos: %s', e)


                if mat:
                    cant_mat += 1
                    _c = row[2].value.strip()
                    _name = row[3].value.strip()
                    _uom = row[6].value.strip()
                    _qty = row[7].value
                    _desp = row[9].value
                    _cost = row[10].value

                    product_id = self.env['product.product'].search([
                                            ('name', '=', _name),
                                            ('resource_type', '=', 'M'),
                                        ], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': _name,
                            'type': 'consu',
                            'standard_price': _cost,
                            'resource_type': 'M',
                        })

                    if _name and _qty and _cost:
                        _va = {
                            'name': _name,
                            'type': 'material',
                            'budget_id': budget.id,
                            'quantity': _qty,
                            'uom_id': self._get_uom(_uom),
                            'code': departure.code + "." + str(cant_mat),
                            'parent_id': departure.id,
                            'amount_fixed': _cost,
                            'product_id': product_id.id,
                            'waste' : _desp,
                        }
                        bim_concepts_id =  self.env['bim.concepts'].create(_va)

                if eq and not row[1].value == "2.-EQUIPOS" and not row[1].value == "No":
                    cant_eq += 1
                    _c = row[2].value.strip()
                    _name = row[3].value.strip()
                    _uom = "UN"
                    _qty = row[6].value
                    _cost = row[10].value
                    _dep = row[8].value

                    product_id = self.env['product.product'].search([
                                            ('name', '=', _name),
                                            ('resource_type', '=', 'Q'),
                                        ], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': _name,
                            'type': 'service',
                            'standard_price': _cost,
                            'resource_type': 'Q',
                        })

                    if _name and _qty:
                        _va = {
                            'name': _name,
                            'type': 'equip',
                            'budget_id': budget.id,
                            'quantity': _qty,
                            'uom_id': self._get_uom(_uom),
                            'code': departure.code + "." + str(cant_eq),
                            'parent_id': departure.id,
                            'amount_fixed': _cost,
                            'product_id': product_id.id,
                            'depreciation' : _dep
                        }
                        bim_concepts_id =  self.env['bim.concepts'].create(_va)


                if mo and not row[1].value == "3.-MANO DE OBRA" and not row[1].value == "No":
                    cant_mo += 1
                    _name = row[2].value.strip()
                    _qty = row[5].value
                    _cost = row[7].value
                    _desp = row[9].value

                    product_id = self.env['product.product'].search([
                                            ('name', '=', _name),
                                            ('resource_type', '=', 'H'),
                                        ], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': _name,
                            'type': 'service',
                            'standard_price': _cost,
                            'resource_type': 'H',
                        })

                    if _name :
                        _va = {
                            'name': _name,
                            'type': 'labor',
                            'budget_id': budget.id,
                            'quantity': _qty,
                            'uom_id': self._get_uom(_uom),
                            'code': departure.code + "." + str(cant_mo),
                            'parent_id': departure.id,
                            'amount_fixed': _cost,
                            'product_id': product_id.id,
                            'foot_bonus' : _desp
                        }
                        bim_concepts_id =  self.env['bim.concepts'].create(_va)

                        if _desp != budget.foot_bonus:
                            bim_concepts_id.parent_id.use_foot_bonus = True
                            bim_concepts_id.parent_id.foot_bonus = _desp

        if self.update:
            self.budget_id.update_amount()

        self.state = 'done'
        _logger.info('END: Importando archivo IP3 200')




    def import_lulo(self):
        _logger.info('BEGIN: Importando archivo LULO')

        # Decodificar y leer el archivo Excel
        try:
            data = base64.b64decode(self.excel_file)
            work_book = xlrd.open_workbook(file_contents=data)
        except Exception as e:
            _logger.error('Error leyendo el archivo Excel: %s', e)
            raise ValueError("El archivo Excel no es válido o no puede ser procesado.")

        # Crear el presupuesto asociado al proyecto
        budget = self.env['bim.budget'].create({
            'name': self.project_id.name,
            'project_id': self.project_id.id,
            'currency_id': self.project_id.currency_id.id,
            'type_calc': 'apu',
        })

        if budget :
            self.budget_id = budget

        # Crear capítulo principal
        chapter = self.env['bim.concepts'].create({
            'type': 'chapter',
            'budget_id': budget.id,
            'quantity': 1,
            'name': 'GENERAL',
            'code': '01',
        })

        # Procesar cada hoja del archivo Excel
        _counter = 0

        for sheet_index in range(work_book.nsheets):
            _counter += 1
            _counter_row = 0
            sheet = work_book.sheet_by_index(sheet_index)
            _logger.info('Procesando hoja: %s', sheet.name)

            mode = ""  # Para identificar la sección actual
            for row_index in range(sheet.nrows):
                _counter_row += 1
                row = sheet.row(row_index)
                next = False

                if row[0].value == "Partida:":
                    # Creamos las partidas
                    _val = {
                        'type': 'departure',
                        'budget_id': budget.id,
                        'quantity': 1,
                        'name': row[1].value,
                        'parent_id': chapter.id,
                        'code' : _counter,
                        }

                    departure = self.env['bim.concepts'].create(_val)
                    if departure:
                        _logger.info('departure /-/ : %s', departure)



                if next:
                    _logger.info('row: %s', row)
                    uom = row[2].value
                    quantity = row[4].value
                    performance = row[5].value
                    uom_id = self._get_uom(uom)

                    _logger.info('quantity: %s', quantity)

                    departure.uom_id = uom_id
                    departure.quantity = quantity
                    departure.performance = performance
                    next = False

                if row[4].value == 'Cantidad:':
                    next = True

                elif row[0].value == "1.- MATERIALES":
                    mode = "MAT"
                    _logger.info("Sección: Materiales")
                    continue
                elif row[0].value == "2.- EQUIPOS":
                    mode = "EQ"
                    _logger.info("Sección: Equipos")
                    continue
                elif row[0].value == "3.- MANO DE OBRA ":
                    mode = "MO"
                    _logger.info("Sección: Mano de Obra")
                    continue


                # Leer datos según la sección
                if mode == "MAT":  # Procesar materiales
                    self._process_materials(row, budget, departure)
                elif mode == "EQ":  # Procesar equipos
                    self._process_equipments(row, budget, departure)
                elif mode == "MO":  # Procesar mano de obra
                    pass
                    self._process_labor(row, budget, departure)

        if self.update:
            self.budget_id.update_amount()

        self.state = 'done'
        _logger.info('END: Importando archivo LULO')


    def _process_materials(self, row, budget, departure):
        """Procesa una fila de materiales y la guarda en Odoo"""
        try:
            code = row[0].value
            if row[0].value == "Código" or not row[0].value:
                return
            description = row[1].value
            unit = row[2].value
            quantity = row[3].value
            cost = row[4].value
            waste = row[5].value

            product_id = self.env['product.product'].search([
                    ('default_code', '=', code),
                    ('resource_type', '=', 'M'),
                    ], limit=1)
            if not product_id:
                product_id = self.env['product.product'].create({
                    'name': description,
                    'default_code': code,
                    'type': 'consu',
                    'standard_price': cost,
                    'resource_type': 'M',
                })

            _va = {
                'name': description,
                'type': 'material',
                'budget_id': budget.id,
                'quantity': quantity,
                'uom_id': self._get_uom(unit),
                'code': code,
                'parent_id': departure.id,
                'amount_fixed': cost,
                'product_id': product_id.id,
                'waste' : waste,
            }
            bim_concepts_id =  self.env['bim.concepts'].create(_va)
        except Exception as e:
            _logger.error('Error procesando material: %s', e)

    def _process_equipments(self, row, budget, departure):
        """Procesa una fila de equipos y la guarda en Odoo"""
        try:
            code = row[0].value
            if row[0].value == "Código" or not row[0].value:
                return
            description = row[1].value
            unit = row[2].value
            quantity = row[3].value
            cost = row[4].value

            product_id = self.env['product.product'].search([
                    ('default_code', '=', code),
                    ('resource_type', '=', 'Q'),
                    ], limit=1)
            if not product_id:
                product_id = self.env['product.product'].create({
                    'name': description,
                    'default_code': code,
                    'type': 'service',
                    'standard_price': cost,
                    'resource_type': 'Q',
                })

            self.env['bim.concepts'].create({
                'name': description,
                'type': 'equip',
                'budget_id': budget.id,
                'quantity': quantity,
                'code': code,
                'parent_id': departure.id,
                'amount_fixed': cost,
            })
        except Exception as e:
            _logger.error('Error procesando equipo: %s', e)

    def _process_labor(self, row, budget, departure):
        """Procesa una fila de mano de obra y la guarda en Odoo"""
        try:
            code = row[0].value
            if row[0].value == "Código" or not row[0].value or not row[3].value:
                return

            description = row[1].value
            unit = row[2].value
            quantity = row[3].value
            cost = row[4].value

            product_id = self.env['product.product'].search([
                ('default_code', '=', code),
                ('resource_type', '=', 'H'),
                ], limit=1)
            if not product_id:
                product_id = self.env['product.product'].create({
                    'name': description,
                    'default_code': code,
                    'type': 'service',
                    'standard_price': cost,
                    'resource_type': 'H',
                })

            self.env['bim.concepts'].create({
                'name': description,
                'type': 'labor',
                'budget_id': budget.id,
                'quantity': quantity,
                'code': code,
                'parent_id': departure.id,
                'amount_fixed': cost,
            })
        except Exception as e:
            _logger.error('Error procesando mano de obra: %s', e)

    def _get_uom(self, unit_name):
        """Devuelve el UoM basado en el nombre"""
        uom = self.env['uom.uom'].search([('name', '=', unit_name)], limit=1)
        if not uom:
            return False
        return uom.id

    def import_ip3(self):
        _logger.info('BEGIN: Importing IP3')

        # DATA
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        budget = self.env['bim.budget']
        concept_obj = departure = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']

        # Creamos el presupuesto
        budget = budget.create({
                    'name': self.project_id.nombre,
                    'project_id': self.project_id.id,
                    'currency_id': self.project_id.currency_id.id,
                    'type_calc' : 'apu',
                })

        _bim_concepts_id = self.env['bim.concepts'].create({
            'type': 'chapter',
            'budget_id': budget.id,
            'quantity': 1,
            'name': 'GENERAL',
            'code': '01',
        })

        self.budget_id = budget
        if budget.space_ids:
            default_space = budget.space_ids[0]
        else:
            default_space = self.env.ref('base_bim_2.default_bim_budget_space')

        if budget.space_ids:
            default_space = budget.space_ids[0]

        last_row = 0
        read_rows = 0

        mode = ""
        count_ = 0
        code = ""
        for i, row in enumerate(list(sheet.get_rows())[last_row:], last_row):
            count_ += 1
            read_rows += 1
            _logger.info('- %d' % (count_))

            d = row[3].value
            new_apu = False

            if "UNIDAD:" in d:
                new_apu = True
                # busco el nombre dos filas arriba
                unidad = d.split("UNIDAD:")[1].strip()

                z_qty = row[4].value.split("CANTIDAD:")[1].strip()
                qty = z_qty.replace(".", "").replace(",", ".")

                performance = row[10].value.split("RENDIMIENTO:")[1].strip().replace(",", ".")
                code = row[24].value.split("CODIGO:")[1].strip()


                uom_id = uom_obj.search([('name', '=', unidad)], limit=1)
                if not uom_id:
                    uom_id = uom_obj.search([('id', '=', 1)], limit=1)

                _logger.info('name: %s' % (name))

                bim_concepts_id = self.env['bim.concepts'].create({
                        'name': name,
                        'type': 'departure',
                        'budget_id': budget.id,
                        'quantity': qty,
                        'code': code,
                        'uom_id': uom_id.id,
                        'parent_id': _bim_concepts_id.id,
                        'performance': performance,
                    })
            else:
                if row[3].value:
                    name = row[3].value

            if row[1].value == "1.-MATERIALES":
                mode = "MATERIALES"

            if row[1].value == "2.-EQUIPOS":
                mode = "EQUIPOS"


            if row[1].value == "3.-MANO DE OBRA":
                mode = "MANO DE OBRA"

            if row[1].value and row[3].value:
                if mode == "EQUIPOS":
                    __name = row[3].value
                    product_id = self.env['product.product'].search([('name', '=', __name)], limit=1)
                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': __name,
                            'type': 'service',
                            'standard_price': str(row[17].value).replace(",", "."),
                            'resource_type': 'Q',
                        })

                    eq_bim_concepts_id = self.env['bim.concepts'].create({
                        'name': __name,
                        'type': 'equip',
                        'budget_id': budget.id,
                        'quantity': str(row[10].value).replace(",", "."),
                        'code': str(count_),
                        'parent_id': bim_concepts_id.id,
                        'amount_fixed': str(row[17].value).replace(",", "."),
                        'product_id': product_id.id,
                    })


                if mode == "MATERIALES":
                    __name = row[3].value
                    product_id = self.env['product.product'].search([('name', '=', __name)], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': __name,
                            'type': 'consu',
                            'standard_price': str(row[17].value).replace(",", "."),
                            'resource_type': 'M',
                        })

                    mat_bim_concepts_id = self.env['bim.concepts'].create({
                        'name': __name,
                        'type': 'material',
                        'budget_id': budget.id,
                        'quantity': str(row[12].value).replace(",", "."),
                        'code': str(count_),
                        'parent_id': bim_concepts_id.id,
                        'amount_fixed': str(row[17].value).replace(",", "."),
                        'product_id': product_id.id,
                    })

                    waste = row[16].value

                    print(row)

                    if waste:
                        mat_bim_concepts_id.waste = waste


                if mode == "MANO DE OBRA":
                    __name = row[3].value
                    product_id = self.env['product.product'].search([('name', '=', __name)], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].create({
                            'name': __name,
                            'type': 'service',
                            'standard_price': str(row[11].value).replace(",", "."),
                            'resource_type': 'H',
                        })

                    lab_bim_concepts_id = self.env['bim.concepts'].create({
                        'name': __name,
                        'type': 'labor',
                        'budget_id': budget.id,
                        'quantity': str(row[9].value).replace(",", "."),
                        'code': str(count_),
                        'parent_id': bim_concepts_id.id,
                        'amount_fixed': str(row[11].value).replace(",", "."),
                        'product_id': product_id.id,
                    })

                    bono = row[16].value

                    _logger.info(row)
                    _logger.info('bono: %s' % (bono))

                    if bono:
                        lab_bim_concepts_id.foot_bonus = bono

        self.state = 'done'
        _logger.info('END: Importing IP3')



    def import_8_8(self):
        types = {
            'Capítulo': 'chapter',
            'Partida': 'departure',
            'Mano de obra': 'labor',
            'Maquinaria': 'equip',
            'Material': 'material',
            'Otros': 'aux',
        }
        res_types = {
            'Mano de obra': 'H',
            'Maquinaria': 'Q',
            'Material': 'M',
            'Otros': 'A'
        }
        data = base64.b64decode(self.excel_file)
        work_book = xlrd.open_workbook(file_contents=data)
        sheet = work_book.sheet_by_index(0)
        budget = self.env['bim.budget']
        concept_obj = departure = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']
        uoms = {}
        for uom in uom_obj.search([]):
            uoms[uom.name] = uom
            for alt_name in (uom.alt_names or '').split(','):
                if not alt_name.strip():
                    continue
                uoms[alt_name.strip()] = uom

        units_id = self.env.ref('uom.product_uom_unit').id
        next_row_is_departure_note = False
        product_obj = self.env['product.product']
        formula_obj = self.env['bim.formula']
        last_row = self.last_row
        read_rows = 0
        limit = int(self.env['ir.config_parameter'].get_param('bim.import.temp.limit')) or 5000

        if self.limit > 0:
            limit = self.limit

        budget = self.budget_id
        if budget.space_ids:
            default_space = budget.space_ids[0]
        else:
            default_space = self.env.ref('base_bim_2.default_bim_budget_space')

        category = self.category_id if self.category_id else self.env.company.bim_product_category_id
        # Creamos un set de todos los conceptos "sin hijos", de modo que podamos
        # asignarle padre cuando encontremos la columna "parcial", usando el index
        # de ese concepto para tomar todos los hijos despúes de él y asignarles así un padre,
        # para luego sacarlos de la lista.
        concepts_without_parent = budget.concept_ids.filtered_domain([('parent_id', '=', False)])
        for i, row in enumerate(list(sheet.get_rows())[last_row:], last_row):
            read_rows += 1

            if i == 0:  # Si es la primera línea, solo tomo el nombre para crear el presupuesto.
                budget = budget.create({
                    'name': row[0].value,
                    'project_id': self.project_id.id,
                    'currency_id': self.project_id.currency_id.id,
                })
                continue
            elif i in [1, 2]:  # Las 2 siguientes líneas las puedo ignorar.
                continue
            # Tomamos la naturaleza
            nat = 'aux' if '%' in str(row[0].value).strip() else types.get(row[1].value)
            # Si encontramos un capítulo luego de haber pasado el límite, y no
            # quedan padres en la pila, detenemos el proceso para continuarlo
            # en una siguiente interación.
            if nat == 'chapter' and read_rows >= limit:
                read_rows -= 1
                break
            # Si la fila tiene mas de 7 columnas, es porque el archivo es de mediciones
            has_measures = len(row) > 7
            # Si la siguiente línea viene luego de una partida, y no tiene naturaleza,
            # ni valores en la columna CanPres (E cuando no tiene mediciones, K cuando tiene)
            # es una nota de partida, la tomamos y continuamos.
            if next_row_is_departure_note and not nat and row[3].value and row[10 if has_measures else 4].ctype == 0:
                departure.note = row[3].value
                next_row_is_departure_note = False
                continue

            # Verificamos la columna "parcial" (J si tiene las mediciones, D si no tiene)
            parcial_row = row[9 if has_measures else 3]
            parent_close_code = parcial_row.value.strip() if (parcial_row.ctype == 1 and not row[0].value and not row[1].value and not row[2].value) else False
            # Es posible que en presto 19 la columna "parcial" inicie con la palabra "Total", así que se la quitaremos
            if isinstance(parent_close_code, str):
                parent_close_code = parent_close_code.replace('Total', '').replace('total', '').replace('TOTAL', '').strip()

            # Si tenemos código en la "parcial", buscamos el index en el set de
            # padres, para tomar a todos los conceptos después de este y así
            # asignarles el padre, para luego sacarlos.
            if parent_close_code:
                concetps_without_parent_codes = concepts_without_parent.mapped('code')
                index = rindex(concetps_without_parent_codes, parent_close_code) if parent_close_code in concetps_without_parent_codes else -1
                # Si casualmente no está ese código en el listado de padres... ¿no se?
                if index >= 0:
                    parent = concepts_without_parent[index]
                    children = concepts_without_parent[index + 1:]
                    children.write({'parent_id': parent.id})
                    # Asignamos la secuencia a cada uno de sus hijos
                    for seq, child in enumerate(children, 1):
                        child.sequence = seq
                    concepts_without_parent -= children
                    if parent.child_ids:
                        parent.amount_type = 'compute'  # Si ya es padre, entonces lo hacemos calculado.

            uom_id = uoms.get(row[2].value, uom_obj.browse())
            # Creamos el concepto base, luego nos preocupamos de su naturaleza.
            concept = concept_obj.create({
                'code': str(row[0].value).strip(),
                'type': nat,
                'uom_id': uom_id.id,
                'name': row[3].value,
                'budget_id': budget.id,
                'quantity': float(row[10 if has_measures else 4].value),
                'amount_fixed': float(row[11 if has_measures else 5].value),
                'amount_type': 'fixed'  # Será manual hasta que le encontremos un hijo
            }) if nat else concept_obj.browse()
            # Este concepto recién creado lo añadimos al set de conceptos sin padre
            concepts_without_parent += concept

            # Si es una partida, guardo este concepto como la "última partida"
            # y le indicamos que la siguiente línea es para la nota de la partida.
            if nat == 'departure':
                departure = concept
                next_row_is_departure_note = True
            # Si contiene al menos una naturaleza, y sabemos que no es ni un
            # capítulo ni una partida, entonces es una obra, material o función.
            elif nat and nat != 'chapter':
                # Tratamos de buscar un producto con el mismo nombre
                code = str(row[0].value).strip()
                product = product_obj.search(['|', ('default_code', '=', code), ('barcode', '=', code)], limit=1) if self.create_all_products else self.product_id
                if not product:
                    # Y si no lo encontramos, se crea
                    res_type = res_types.get(row[1].value)
                    product = product_obj.create({
                        'name': row[3].value,
                        'resource_type': res_type,
                        'type': 'consu' if res_type == 'M' else 'service',
                        'standard_price': float(row[11 if has_measures else 5].value) if self.product_cost_or_price == 'cost' else 0,
                        'list_price': float(row[11 if has_measures else 5].value) if self.product_cost_or_price == 'price' else 0,
                        'default_code': str(row[0].value).strip(),
                        'categ_id': category.id or False,
                        'uom_id': uom_id.id or units_id,
                        'uom_po_id': uom_id.id or units_id,
                    })
                concept.product_id = product
            # Si esta línea no tiene naturaleza, y tampoco es la siguiente luego
            # de una partida, pero si tiene un comentario, entonces es una medición,
            # se la asignamos a la partida.
            elif row[5].value and has_measures:
                formula = formula_obj.search(['|', ('formula', 'ilike', row[10].value), ('name', 'ilike', row[10].value)], limit=1) if row[10].value else formula_obj.browse()
                if not formula and row[10].value:
                    # La fórmula podría fallar, así que si da problemas, no la cargamos.
                    try:
                        X = x = b = B = float(row[6].value)
                        Y = y = c = C = float(row[7].value)
                        Z = z = d = D = float(row[8].value)
                        eval(str(row[10].value))
                        valid = True
                    except (SyntaxError, NameError):
                        valid = False
                    formula = formula_obj.create({
                        'name': row[10].value,
                        'formula':  "X*Y*Z*" + row[10].value,
                    }) if valid else formula_obj.browse()


                # si es "" es 0
                _qty = float(row[5].value) if row[5].value else 0.0
                _length = float(row[6].value) if row[6].value else 0.0
                _width = float(row[7].value) if row[7].value else 0.0
                _height = float(row[8].value) if row[8].value else 0.0

                measuring_vals = {
                    'space_id': default_space.id,
                    'name': row[4].value if row[4].value else 'Medición',
                    'qty': _qty,
                    'length': _length,
                    'width': _width,
                    'height': _height,
                    'amount_subtotal': float(row[9].value),
                    'formula': formula.id,
                }

                _logger.info('Measuring vals: %s', measuring_vals)

                departure.write({
                    'measuring_ids': [(0, 0, measuring_vals)]
                })


        return self.write({
            'state': 'ongoing' if read_rows >= limit else 'done',
            'last_row': last_row + read_rows,
            'budget_id': budget.id,
        })

    def import_bc3(self):
        _logger.info('BEGIN: Importing BC3')
        data = base64.b64decode(self.excel_file).decode('latin-1')
        read_rows = 0
        limit = int(self.env['ir.config_parameter'].get_param('bim.import.temp.limit')) or 5000

        if self.limit > 0:
            limit = self.limit

        budget = self.budget_id or self.budget_id.create({'name': 'N/A',
                                                          'project_id': self.project_id.id,
                                                          'date_end': fields.Date.today(),
                                                          'currency_id': self.project_id.currency_id.id})
        if budget.space_ids:
            default_space = budget.space_ids[0]
        else:
            default_space = self.env.ref('base_bim_2.default_bim_budget_space')
        last_row = self.last_row
        formula_obj = self.env['bim.formula']
        concept_obj = self.env['bim.concepts']
        uom_obj = self.env['uom.uom']
        uoms = {}
        uoms_lower = {}
        for uom in uom_obj.search([]):
            uoms[uom.name] = uom
            uoms_lower[uom.name.lower()] = uom
            for alt_name in (uom.alt_names or '').split(','):
                if not alt_name.strip():
                    continue
                uoms[alt_name.strip()] = uom
                uoms_lower[alt_name.strip().lower()] = uom
        units_id = self.env.ref('uom.product_uom_unit').id
        product_obj = self.env['product.product']
        category = self.category_id if self.category_id else self.env.company.bim_product_category_id
        children_codes = {}
        concepts = budget.concept_ids
        nats = ['not_used', 'labor', 'equip', 'material','subcontract']
        res_types = ['A', 'H', 'Q', 'M', 'S']
        pending = ''
        rows = data.split('\n')

        for row in rows[last_row:]:
            row = row.strip()
            read_rows += 1
            _logger.info('Row %d: %s' % (read_rows, row))

            if read_rows > limit:
                break
            if row and pending:
                row = pending + row
                pending = ''

            next_row = rows[last_row + read_rows] if len(rows) > last_row + read_rows else False
            if row and next_row and next_row[0] != '~':
                pending = row
                continue
            else:
                pending = ''

            if not row or row[0] != '~':
                continue
            elif row[1] == 'K':
                try:
                    currency_name = row[3:].split('|')[0].split('\\')[8]
                    currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
                    if currency:
                        budget.currency_id = currency
                except:
                    pass
            elif row[1] == 'C':
                datas = row[3:].split('|')
                code, uom, name, price, ___, ctype = datas[:6]
                price = price.replace('\\','')
                code = code.replace('\\','')
                try:
                    ctype = int(float(ctype.replace('\\', '').strip()))
                except:
                    ctype = 0
                    pass
                if '##' in code:
                    budget.name = name or code.replace('##', '')
                    continue
                is_chapter = '#' in code
                code = code.replace('#', '')
                is_subcontract = (ctype == 4) or (code.upper().startswith('SUBC') and not is_chapter)
                uom_id = uoms.get(uom) or uoms_lower.get(uom.lower(), uom_obj.browse())
                concept = concept_obj.create({
                    'code': code,
                    'type': 'aux' if '%' in code else 'subcontract' if is_subcontract else nats[ctype] if 0 < ctype < 4 else 'chapter' if is_chapter else 'departure',
                    'uom_id': uom_id.id,
                    'name': name,
                    'budget_id': budget.id,
                    'quantity': 1,
                    'amount_fixed': price,
                    'amount_type': 'fixed',
                })

                if concept.type not in ['chapter', 'departure']:
                    product = product_obj.search(['|', ('default_code', '=', code), ('barcode', '=', code)], limit=1) if self.create_all_products else self.product_id
                    if not product:
                        res_type = 'S' if is_subcontract else (res_types[ctype] if 0 < ctype < 4 else 'A')
                        product = product_obj.create({
                            'name': name,
                            'resource_type': res_type,
                            'default_code': code,
                            'type': 'consu' if res_type == 'M' else 'service',
                            'list_price': price if self.product_cost_or_price == 'price' else 0,
                            'standard_price': price if self.product_cost_or_price == 'cost' else 0,
                            'categ_id': category.id or False,
                            'uom_id': uom_id.id or units_id,
                            'uom_po_id': uom_id.id or units_id,
                        })
                    concept.product_id = product

                concept_copies = concept_obj.browse()
                for i, (parent_code, child_data) in enumerate(children_codes.get(code, {}).items()):
                    for parent in concepts.filtered_domain([('code', '=', parent_code)]):
                        parent.amount_type = 'compute'
                        if i == 0:
                            concept.parent_id = parent
                            concept.quantity = child_data.get('qty', 0)
                            concept.sequence = child_data.get('seq', 1)
                        elif parent:
                            copy_concept = self.env.user.recursive_create(concept, parent.id, budget.id)
                            copy_concept.quantity = child_data.get('qty', 0)
                            copy_concept.sequence = child_data.get('seq', 1)
                            concept_copies += copy_concept

                concepts += concept
                # if concept_copies:
                #     concepts += concept_copies
            elif row[1] == 'D':
                datas = row[3:-1].split('|')
                parent_code = datas[0].replace('#', '')
                children = datas[1:]
                for seq, (code, __, qty) in enumerate(zip(*[iter(children[0].split('\\'))] * 3), 1):
                    try:
                        qty = float(qty)
                    except:
                        qty = 0
                        pass
                    if code in children_codes:
                        children_codes[code][parent_code] = {'qty': qty, 'seq': seq}
                    else:
                        children_codes[code] = {parent_code: {'qty': qty, 'seq': seq}}
                    for child in concepts.filtered_domain([('code', '=', code)]) if code else concept_obj.browse():
                        for parent in concepts.filtered_domain([('code', '=', parent_code)]) if parent_code else concept_obj.browse():
                            if child.parent_id:
                                child = self.env.user.recursive_create(child, parent.id, budget.id)
                                # No se si deba meter los hijos nuevos en el total de conceptos...
                            parent.child_ids += child
                            parent.amount_type = 'compute'
                        child.sequence = seq
                        child.quantity = qty
            elif row[1] == 'M':
                datas = row[3:-1].split('|')
                __, departure_code = datas[0].split('\\')
                departure = concepts.filtered_domain([('code', '=', departure_code)])
                measuring_vals = []
                for is_formula, name, qty, length, width, height in zip(*[iter(datas[3].split('\\'))] * 6):
                    # Saltar grupos sin cantidad ni dimensiones (títulos/separadores de BC3)
                    if not qty and not length and not width and not height:
                        continue
                    name = (name or '').strip() or 'Medición'
                    formula = formula_obj.browse()
                    if is_formula == '3':
                        formula = formula_obj.search(['|', ('formula', 'ilike', name), ('name', 'ilike', name)], limit=1)
                        if not formula:
                            # La fórmula podría fallar, así que si da problemas, no la cargamos.
                            try:
                                X = x = b = B = float(length or 0.0)
                                Y = y = c = C = float(width or 0.0)
                                Z = z = d = D = float(height or 0.0)
                                eval(name)
                                valid = True
                            except (SyntaxError, NameError):
                                valid = False
                            formula = formula_obj.create({
                                'name': name,
                                'formula': name,
                            }) if valid else formula_obj.browse()
                    if not qty:
                        self.message_post(body='Amount at 0 or null for the measurement line %d:\n%s' % (read_rows + self.last_row, row))
                    measuring_vals.append((0, 0, {
                        'space_id': default_space.id,
                        'name': name,
                        'qty': float(qty or 1.0),
                        'length': float(length or 0.0),
                        'width': float(width or 0.0),
                        'height': float(height or 0.0),
                        'amount_subtotal': float(datas[2] or 0.0),
                        'formula': formula.id,
                    }))

                departure.write({'measuring_ids': measuring_vals})
            elif row[1] == 'T':
                datas = row[3:-1].split('|')
                concept = concepts.filtered_domain([('code', '=', datas[0])])
                concept.write({'note': datas[1]})

        # Eliminar conceptos huérfanos: recursos definidos en ~C pero no referenciados
        # en ningún ~D (elementos de biblioteca no utilizados en este presupuesto).
        orphan_concepts = concepts.filtered(
            lambda c: not c.parent_id and not c.child_ids and c.type not in ('chapter', 'departure')
        )
        if orphan_concepts:
            _logger.info('Eliminando %d conceptos huérfanos: %s', len(orphan_concepts), orphan_concepts.mapped('code'))
            orphan_concepts.unlink()

        if self.default_uom_id:
            concepts_without_uom = concept_obj.search([('budget_id', '=', budget.id), ('uom_id', '=', False)])
            if concepts_without_uom:
                concepts_without_uom.write({'uom_id': self.default_uom_id.id})
                _logger.info('Asignada UdM %s a %d conceptos sin unidad de medida', self.default_uom_id.name, len(concepts_without_uom))

        if self.update:
            def rec_update(concept):
                """ Actualiza desde el último hijo hasta subir al primer padre """
                for child in concept.child_ids:
                    rec_update(child)
                concept.onchange_function()
                concept.update_amount()

            for concept in budget.concept_ids:
                rec_update(concept)

        return self.write({
            'state': 'ongoing' if read_rows >= limit else 'done',
            'last_row': last_row + read_rows,
            'budget_id': budget.id,
        })

        _logger.info('END: Importing BC3')



    def import_ms_xml(self):
        dt_format = '%Y-%m-%dT%H:%M:%S'
        file_content = base64.b64decode(self.excel_file)
        content = bs4.BeautifulSoup(file_content, 'lxml')
        tasks = [task for task in content.find_all('task') if task.find('wbs')]
        concept_obj = self.env['bim.concepts']
        budget = self.budget_id or self.budget_id.create({'name': 'N/A',
                                                          'project_id': self.project_id.id,
                                                          'date_end': fields.Date.today(),
                                                          'currency_id': self.project_id.currency_id.id})
        budget.do_compute = False
        concepts = budget.concept_ids
        stages_percents = {}
        for task in sorted(tasks, key=lambda t: len(t.find('wbs').text.split('.'))):
            wbs = task.find('wbs')
            if wbs and wbs.text == '0':
                continue
            if wbs and wbs.text == '1':
                budget.name = task.find('name').text
                continue
            if not wbs:
                continue
            code = (wbs.text or '').split('.')

            concept = concept_obj.create({
                'code': '.'.join(code),
                'type': 'chapter' if len(code) <= 2 else 'departure',
                'name': task.find('name').text,
                'budget_id': budget.id,
                'quantity': 1,
                'acs_date_start': datetime.datetime.strptime(task.find('start').text, dt_format),
                'acs_date_end': datetime.datetime.strptime(task.find('finish').text, dt_format),
            })

            if len(code) > 2:
                parent_code = '.'.join(code[:-1])
                parent_concept = concepts.filtered_domain([('code', '=', parent_code)])
                if len(parent_concept) == 1:
                    concept.parent_id = parent_concept

            concepts |= concept

            if self.import_stages and task.find('percentcomplete'):
                certif_percent = float(task.find('percentcomplete').text)
                if certif_percent:
                    stages_percents[concept] = certif_percent


        if self.import_stages and stages_percents:
            budget.set_estimated_dates()
            if budget.date_start and budget.date_end and budget.date_start < budget.date_end:
                budget.create_stage(1)

        if budget.stage_ids:
            budget_stage = budget.stage_ids[0]
            for concept, percent in stages_percents.items():
                concept.type_cert = 'stage'
                concept.generate_stage_list()
                stage = concept.certification_stage_ids.filtered_domain([('stage_id', '=', budget_stage.id)])
                stage.certif_percent = percent
                stage.onchange_percent()
                concept.update_amount()

        return self.write({
            'state': 'done',
            'budget_id': budget.id,
        })



class BimImportWizard(models.TransientModel):
    _name = 'bim.import.wizard'
    _description = 'Project Importer'

    version = fields.Selection([('8.8', 'Excel Template'), ('bc3', 'BC3'), ('ms_xml', 'Project XML')], 'Version', default='8.8', required=True)
    project_id = fields.Many2one('bim.project', 'Project', required=True)
    enconding = fields.Selection([
        ('latin-1', 'Latin-1')
        , ('utf-8', 'UTF-8')
    ], 'Encoding', default='latin-1', required=True)
    create_all_products = fields.Boolean('Create non-existent products')
    product_id = fields.Many2one('product.product', 'Default product', default=lambda self: self.env.ref('base_bim_2.default_product', raise_if_not_found=False))
    excel_file = fields.Binary('Excel file', required=True)
    filename = fields.Char('File name')
    product_cost_or_price = fields.Selection([('price', 'Price'), ('cost', 'Product Cost')],
                                             string='Assign to', default='cost')
    import_stages = fields.Boolean()
    category_id = fields.Many2one('product.category', 'Product Category')

    @api.model
    def file_validator(self, fileformat):
        name, extension = os.path.splitext(fileformat)
        if self.version == '8.8' and extension in ('.xls','.xlsx'):
            return True
        elif self.version == 'bc3' and extension in ('.bc3'):
            return True
        elif self.version == 'ms_xml' and extension in ('.xml'):
            return True
        return False

    def import_data(self):
        if not self.file_validator(self.filename):
            raise UserError(_("File Extension does not match with Importation Version"))
        self.env['bim.import.temp'].create({
            'version': self.version,
            'project_id': self.project_id.id,
            'create_all_products': self.create_all_products,
            'product_id': self.product_id.id,
            'category_id': self.category_id.id if self.category_id else False,
            'excel_file': self.excel_file,
            'filename': self.filename,
            'enconding': self.enconding,
            'import_stages': self.import_stages,
            'product_cost_or_price': self.product_cost_or_price,
        })
        return {'type': 'ir.actions.act_window_close'}


def rindex(alist, val):
    return len(alist) - alist[-1::-1].index(val) - 1
