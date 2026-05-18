# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import base64
import xlrd
import io
import logging
_logger = logging.getLogger(__name__)

class BimPriceMassiveWzd(models.TransientModel):
    _name = 'bim.price.massive.wzd'
    _description = 'bim.price.massive.wzd'

    def _get_default_budget(self):
        active_id = self._context.get('active_id')
        budget = self.env['bim.budget'].browse(active_id)
        return budget

    budget_id = fields.Many2one('bim.budget', string='Budget', default=_get_default_budget)
    product_id = fields.Many2one('product.product', string='Resource')
    pricelist_id = fields.Many2one('product.pricelist', string='Price List')
    concept_id = fields.Many2one('bim.concepts', string='Concept')
    new_price = fields.Float('Price New', digits="BIM price")
    type_update = fields.Selection([
                                    ('duplicate', 'Duplicate Budget'),
                                    ('cost', 'Update massive concepts according to current cost'),
                                    ('sale', 'Update massive concepts according to current price'),
                                    ('manual', 'Update bulk concepts manually'),
                                    ('manual_departure', 'Update Departure Manually'),
                                    ('agreed', 'Update massive concepts according to agreed prices'),
                                    ('pricelist', 'Update massive concepts according to pricelist'),
                                    ('usd_exchange', 'Update massive concepts according USD exchange'),
                                    ('delete_parent', 'Delete Parent'),
                                    ('update_from_apu', 'Update from APU'),
                                    ('update_phase_resource', 'Update Phases Resources'),
                                    ('give_me_parent_departure', 'Give Me Parent Departure'),
                                    ('insert_phase_departure_parent', 'Insert Phase in Parent Departure'),
                                    ('update_resources_in_departure', 'Actualizar Recursos en Partidas'),
                                    ('change_product_in_budget', 'Cambiar Producto en Presupuesto'),
                                    ('add_product_to_budget', 'Adicionar Productos al Presupuesto'),
                                    ('delete_product_in_budget', 'Eliminar Productos en Presupuesto'),
                                    ('import_mass_resources', 'Importador Masivo de Recursos'),
                                    ('update_fields', 'Update fields'),
                                    ], string="Type",  default='duplicate')

    name_field = fields.Char(string="Campo", default='performance')
    value_field = fields.Float(string="Valor", digits="BIM price", default=1)

    type_price = fields.Selection([('price','Price'),('percent','Percent')], string="Type Price", default='price')
    duplicate = fields.Boolean(string="Duplicate Budget", default=True)
    departure_code = fields.Char(string="Departure Code")
    new_cost = fields.Float('Cost New', digits="BIM price")

    which_departure = fields.Many2one('bim.concepts', domain="[('budget_id','=',budget_id),('type','=','departure')]", string="Which Departure")
    which_resource = fields.Many2one('bim.concepts', domain="[('budget_id','=',budget_id),('parent_id','=',which_departure),('type','in',['material','labor','equip','subcontract'])]", string="Which Resource")
    which_qty = fields.Float('Quantity', digits="BIM qty")
    which_new_qty = fields.Float('New Quantity', digits="BIM qty")
    which_new_percent = fields.Float('New Percent', digits="BIM qty")

    product_to_change_id = fields.Many2one('product.product', string='Producto a Remplazar', domain="[('id','in', allowed_product_ids)]" )
    product_new_id = fields.Many2one('product.product', string='Nuevo Producto')
    departures_ids = fields.Many2many('bim.concepts', string='Departures', domain="[('budget_id','=',budget_id),('type','=','departure')]")
    products_ids = fields.Many2many('product.product', string='Products', domain="[('id','in', allowed_product_ids)]")
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_products', store=False)
    file_xls = fields.Binary('Fichero XLS 2000')
    product_exists = fields.Boolean(string="validar Productos", default=False)
    qty_to_add = fields.Float('Cant.', digits="BIM qty", default=1.0)


    @api.depends('budget_id', 'type_update')
    def _compute_allowed_products(self):
        for rec in self:
            rec.allowed_product_ids = rec.budget_id.concept_ids.mapped('product_id')


    @api.onchange('which_departure','which_resource')
    def onchange_which_resource(self):
        if self.which_departure and self.which_resource:
            # Buscamos todas las partidas con ese codigo y con ese codigo de recurso
            departure_code = self.which_departure.code
            resource_code = self.which_resource.code

            departure_ids = self.env['bim.concepts'].search(
                [('budget_id', '=', self.budget_id.id),
                ('code', '=', departure_code),
                ('type', '=', 'departure')])

            print('departure_ids', departure_ids)

            which_qty = 0
            for dep in departure_ids:
                resource_ids = self.env['bim.concepts'].search(
                    [('budget_id', '=', self.budget_id.id),
                    ('parent_id', '=', dep.id),
                    ('code', '=', resource_code)
                    ])


                for res in resource_ids:
                    which_qty += res.quantity * dep.quantity

            self.which_qty = which_qty


    @api.onchange('type_update')
    def onchange_type_update(self):
        _logger.info('onchange_type_update')
        if self.type_update == 'duplicate':
            self.duplicate = True
        else:
            self.duplicate = False

    def update_price(self):
        if self.duplicate:
           budget_id = self.budget_id.copy()
        else:
            budget_id = self.budget_id

        if self.type_update == 'delete_parent':
            concepts = self.env['bim.concepts'].search(
                [('budget_id', '=', budget_id.id), ('parent_id', '=', self.concept_id.id)])
            for concept in concepts:
                concept.parent_id = self.concept_id.parent_id.id


        if self.type_update == 'cost':
            resources = budget_id.concept_ids.filtered(lambda self: self.type in ['material', 'labor', 'equip'])
            for resource in resources:
                if resource.not_can_update_cost:
                    continue
                if resource.parent_id.not_can_update_cost:
                    continue
                resource.amount_fixed = resource.product_id.standard_price





        elif self.type_update == 'import_mass_resources':
            if not self.file_xls:
                raise ValidationError(_('Debe seleccionar un fichero xls'))

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

            # Recorro las filas cuando encruntro un recurso busco si esa
            file = io.BytesIO(base64.b64decode(self.file_xls))
            workbook = xlrd.open_workbook(file_contents=file.read())
            sheet = workbook.sheet_by_index(0)
            n_rows = sheet.nrows
            n_cols = sheet.ncols


            last_bim_concept_id = False
            for row in range(1, n_rows):
                line = sheet.row(row)
                # reviso si tiene la columna NAT
                last_departure = line[0].value
                array_not_product_found = []

                if len(line[1].value) > 0:
                    bim_concept_id = self.env['bim.concepts'].search(
                        [('budget_id', '=', budget_id.id),
                        ('code', '=', line[0].value),
                        ('parent_id', '=', last_bim_concept_id.id if last_bim_concept_id else False),
                        ('type', 'in', ['material', 'labor', 'equip', 'subcontract'])])

                    if not bim_concept_id:
                        product_id = self.env['product.product'].search([('default_code', '=', line[0].value)], limit=1)

                        if product_id:
                            if line[4].value:
                                if float(line[4].value) > 0:
                                    vals = {
                                        'budget_id': budget_id.id,
                                        'parent_id': last_bim_concept_id.id if last_bim_concept_id else False,
                                        'code': line[0].value,
                                        'name': line[3].value if len(line[3].value) > 0 else product_id.name,
                                        'type': 'material' if product_id.resource_type == 'M' else 'labor' if product_id.resource_type == 'H' else 'equip' if product_id.resource_type == 'Q' else 'subcontract' if product_id.resource_type == 'S' else 'material',
                                        'product_id': product_id.id,
                                        'quantity': float(line[4].value) if line[4].value else 0,
                                        'amount_fixed': float(line[5].value) if line[5].value else product_id.standard_price,
                                        'uom_id': product_id.uom_id.id,
                                    }
                                    self.env['bim.concepts'].create(vals)

                        else:
                            if self.product_exists:
                                raise ValidationError(_('No existe el producto con codigo %s y nombre %s' % (line[0].value, line[3].value)))

                    else:
                        # actualizo la cantidad y el precio
                        if float(line[4].value) > 0:
                            bim_concept_id.quantity = float(line[4].value)
                        if float(line[5].value) > 0:
                            bim_concept_id.amount_fixed = float(line[5].value)


                else:
                    last_bim_concept_id = self.env['bim.concepts'].search(
                        [('budget_id', '=', budget_id.id),
                        ('code', '=', line[0].value),
                        ('type', '=', 'departure')])



        elif self.type_update == 'insert_phase_departure_parent':
            if not budget_id.parent_id:
                raise ValidationError(_('Does not have a parent budget'))

            departures = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])
            for dep in departures:
                if dep.budget_parent_id:
                    if dep.bim_concept_id:
                        dep.bim_concept_id.concept_phase_id = dep.concept_phase_id.id
                        dep.bim_concept_id.sub_phase_id = dep.sub_phase_id.id
                        dep.bim_concept_id.bim_pcp_id = dep.bim_pcp_id.id
                    else:
                        parent_departure = self.env['bim.concepts'].search(
                            [('budget_id', '=', dep.budget_parent_id.id),
                            ('code', '=', dep.code),
                            ('type', '=', 'departure')])
                        if parent_departure:
                            parent_departure.concept_phase_id = dep.concept_phase_id.id
                            parent_departure.sub_phase_id = dep.sub_phase_id.id
                            parent_departure.bim_pcp_id = dep.bim_pcp_id.id


        elif self.type_update == 'give_me_parent_departure':
            if not budget_id.parent_id:
                raise ValidationError(_('Does not have a parent budget'))
            departures = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])
            for dep in departures:
                if dep.budget_parent_id:
                    # buscamos si existe un concepto con ese codigo en el padre
                    parent_departure = self.env['bim.concepts'].search(
                        [('budget_id', '=', dep.budget_parent_id.id),
                        ('code', '=', dep.code),
                        ('type', '=', 'departure')])
                    if parent_departure:
                        bim_concept_parent_ids = self.env['bim.concept.parent'].search(
                            [('concept_id' , '=', dep.id)]
                        )

                        # Eliminamos los padres
                        for bim_concept_parent_id in bim_concept_parent_ids:
                            bim_concept_parent_id.unlink()

                        # Creamos el padre
                        self.env['bim.concept.parent'].create({
                            'concept_id': dep.id,
                            'name': parent_departure.id
                        })



        elif self.type_update == 'update_phase_resource':
            departures = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])
            for dep in departures:
                resources = self.env['bim.concepts'].search(
                    [('budget_id', '=', budget_id.id),
                    ('parent_id', '=', dep.id),
                    ])

                for resource in resources:
                    resource.concept_specialty_id = dep.concept_specialty_id.id
                    resource.concept_phase_id = dep.concept_phase_id.id
                    resource.sub_phase_id = dep.sub_phase_id.id
                    resource.bim_pcp_id = dep.bim_pcp_id.id


        elif self.type_update == 'sale':
            resources = budget_id.concept_ids.filtered(lambda self: self.type in ['material', 'labor', 'equip'])
            for resource in resources:
                if resource.not_can_update_cost:
                    continue
                if resource.parent_id.not_can_update_cost:
                    continue
                resource.amount_fixed = resource.product_id.lst_price

        elif self.type_update == 'update_resources_in_departure':
            factor = 1
            if self.which_new_qty > 0:
                factor = self.which_new_qty / self.which_qty if self.which_qty > 0 else 1

            if self.which_new_percent > 0:
                factor = self.which_new_percent / 100


            departure_ids = self.env['bim.concepts'].search(
                [('budget_id', '=', budget_id.id),
                ('code', '=', self.which_departure.code),
                ('type', '=', 'departure')])

            for dep in departure_ids:
                resource_ids = self.env['bim.concepts'].search(
                    [('budget_id', '=', budget_id.id),
                    ('parent_id', '=', dep.id),
                    ('code', '=', self.which_resource.code)
                    ])

                for res in resource_ids:
                    res.quantity *= factor



        elif self.type_update == 'manual_departure':
            departure = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])
            for dep in departure:
                if self.departure_code == dep.code:
                    dep.amount_type = 'fixed'
                    dep.amount_fixed = self.new_cost
                    dep.update_amount()

        elif self.type_update == 'update_from_apu':
            departure = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])
            for dep in departure:
                code = dep.code
                # bucamos si existe un apu con ese codigo
                bim_concept_template_id = self.env['bim.concept.template'].search([('code', '=', code)], limit=1)
                if bim_concept_template_id:
                    for line in bim_concept_template_id.template_line_ids:
                        code_rec = line.code

                        # buscamos si existe un concepto con ese codigo
                        rec_id = self.env['bim.concepts'].search(
                                    [
                                        ('code', '=', line.code),
                                        ('parent_id', '=', dep.id)],
                                    limit=1)
                        if rec_id:
                            rec_id.quantity = line.quantity
                            rec_id.amount_fixed = line.price


        elif self.type_update == 'agreed':
            project = budget_id.project_id
            if not project.price_agreed_ids:
                raise ValidationError(_('No existen registros de Productos con precios acordados para la Obra'))
            for line in project.price_agreed_ids:
                resources = budget_id.concept_ids.filtered(lambda x: x.product_id == line.product_id)
                for resource in resources:
                    resource.amount_fixed = line.price_agreed

        elif self.type_update == 'manual':
            concepts = self.env['bim.concepts'].search(
                [('budget_id', '=', budget_id.id), ('product_id', '=', self.product_id.id)])
            if self.new_price > 0.0:
                if self.type_price == 'price':
                    for concept in concepts:
                        _update = False
                        if concept.not_can_update_cost:
                            continue
                        if concept.parent_id.not_can_update_cost:
                            continue
                        concept.write({'amount_fixed': self.new_price})
                elif self.type_price == 'percent':
                    for concept in concepts:
                        if concept.not_can_update_cost:
                            continue
                        if concept.parent_id.not_can_update_cost:
                            continue
                        concept.write({'amount_fixed': concept.amount_fixed * (self.new_price/100)})
            else:
                raise ValidationError(_('Price should be bigger than 0.0'))

        elif self.type_update == 'usd_exchange':
            resources = budget_id.concept_ids.filtered(lambda self: self.type in ['material', 'labor', 'equip'] and self.product_id != False and self.product_id.cost_usd)
            exchange_rate = self.env['res.currency.rate'].search(
                ['|', ('currency_id.name', '=', 'USD'), ('currency_id.symbol', '=', '$'),
                 ('rate', '!=', 0)], order='name desc', limit=1)
            if resources and exchange_rate:
                products = resources.mapped('product_id')
                for product in products:
                    product.product_tmpl_id.onchange_cost_usd()
                for resource in resources:
                    resource.amount_fixed = resource.product_id.standard_price

        elif self.type_update == 'change_product_in_budget':
            products = budget_id.concept_ids.filtered(lambda x: x.product_id == self.product_to_change_id)

            if self.departures_ids:
                products = products.filtered(lambda x: x.parent_id in self.departures_ids)

            for product in products:
                product.product_id = self.product_new_id
                # actualizamos
                product.amount_fixed = self.product_new_id.standard_price
                product.onchange_product()

        elif self.type_update == 'add_product_to_budget':
            if self.departures_ids:
                departures = self.departures_ids
            else:
                departures = budget_id.concept_ids.filtered(lambda self: self.type in ['departure'])

            for dep in departures:
                pro = self.product_new_id
                if pro.resource_type == 'M':
                    type = 'material'
                elif pro.resource_type == 'H':
                    type = 'labor'
                elif pro.resource_type == 'Q':
                    type = 'equip'
                elif pro.resource_type == 'S':
                    type = 'subcontract'
                else:
                    type = 'material'

                new_concept = self.env['bim.concepts'].create({
                    'budget_id': budget_id.id,
                    'parent_id': dep.id,
                    'product_id': pro.id,
                    'code': pro.default_code or '/',
                    'name': pro.name,
                    'type': type,
                    'quantity': self.qty_to_add,
                    'uom_id': pro.uom_id.id,
                    'amount_fixed': pro.standard_price,
                })
                new_concept.update_amount()

        elif self.type_update == 'delete_product_in_budget':
            products = budget_id.concept_ids.filtered(lambda x: x.product_id in self.products_ids)

            if self.departures_ids:
                products = products.filtered(lambda x: x.parent_id in self.departures_ids)

            for product in products:
                product.unlink()



        elif self.type_update == 'update_fields':
            name_field = self.name_field
            value_field = self.value_field

            concepts = self.env['bim.concepts'].search(
                [('budget_id', '=', budget_id.id)])
            for concept in concepts:
                sql = "UPDATE bim_concepts SET %s = %s * %s WHERE id = %s" % (name_field, name_field, value_field, concept.id)
                self.env.cr.execute(sql)



        else:
            resources = budget_id.concept_ids.filtered(lambda self: self.type in ['material', 'labor', 'equip'])
            for resource in resources:
                if self.pricelist_id:
                    resource.amount_fixed = self.pricelist_id._get_product_price(resource.product_id, resource.quantity)
