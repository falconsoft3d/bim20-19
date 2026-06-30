# -*- coding: utf-8 -*-
import base64
import xlwt
import re
import io
import logging
import tempfile
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from xlwt import easyxf, Workbook
from datetime import datetime
from io import StringIO
_logger = logging.getLogger(__name__)
from io import BytesIO

class GeneralDataReportWizard(models.TransientModel):
    _name = "general.data.report.wizard"
    _description = "General Data Report Wizard"

    name = fields.Char(string="Name")
    date = fields.Date(string="Date")
    product_code = fields.Char(string="Product Code")
    description = fields.Char(string="Description")
    qty = fields.Float(string="Quantity")
    total_amount = fields.Float(string="Total Amount")
    type = fields.Char(string="Type")
    other_1 = fields.Char(string="Other 1")
    other_2 = fields.Char(string="Other 2")
    other_3 = fields.Char(string="Other 3")



class CatergoryReportWizard(models.TransientModel):
    _name = "bim.stock.report.category.wizard"
    _description = "Catergory Report Wizard"

    name = fields.Many2one('product.product', string="Product")
    bim_purchase_requisition = fields.Integer(string="Purchase Requisition")
    purchase_order_request = fields.Integer(string="Purchase Request")
    purchase_order = fields.Integer(string="Purchase Order")
    stock_picking = fields.Integer(string="Stock In")
    stock_picking_out = fields.Integer(string="Stock Out")
    account_move = fields.Integer(string="Invoice")
    category_id = fields.Many2one('product.category', string="Category")
    stock_picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    total_amount = fields.Float(string="Total Amount")
    description = fields.Char(string="Description")


class CatergoryReportWizardResum(models.TransientModel):
    _name = "bim.stock.report.cat.resum"
    _description = "Catergory Report Wizard Resum"

    category_id = fields.Many2one('product.category', string="Category")
    bim_purchase_requisition = fields.Integer(string="Purchase Requisition")
    purchase_order_request = fields.Integer(string="Purchase Request")
    purchase_order = fields.Integer(string="Purchase Order")
    stock_picking = fields.Integer(string="Stock In")
    stock_picking_out = fields.Integer(string="Stock Out")
    account_move = fields.Integer(string="Invoice")
    total_amount = fields.Float(string="Total Amount")


class BimstockReportWizard(models.TransientModel):
    _name = "bim.stock.report.wizard"
    _description = "Wizard Report Budget Stock"

    @api.model
    def default_get(self, fields):
        res = super(BimstockReportWizard, self).default_get(fields)
        context = self._context
        
        if context.get('active_model') == 'bim.budget':
            res['budget_ids'] = [(6,0,context.get('active_ids', False))]
        else:
            res['project_id'] = context.get('active_id', False)
        return res

    material = fields.Boolean(string="Materials",default=True)
    equipment = fields.Boolean(string="Equipment",default=True)
    labor = fields.Boolean(string="Labor",default=True)
    attendance = fields.Boolean(string="Attendance",default=True)
    invoice = fields.Boolean(string="Purchase Invoices",default=True)
    tools = fields.Boolean(string="Tools",default=True)
    resource_all = fields.Boolean(default=True,string="All")
    date_beg = fields.Date('Date From', default=fields.Date.today)
    date_end = fields.Date('Date To')
    project_id = fields.Many2one('bim.project', "Budget")
    doc_type = fields.Selection([('csv', 'CSV'), ('xls', 'Excel')], string='Format', default='xls')
    display_type = fields.Selection([
            ('summary', 'Summarized'),
            ('detailed', 'Detailed'),
            ('range', 'Date Range'),
            ('categories_product', 'Categories and Products'),
            ('categories_product_list', 'Categories and Products List'),
            ('categories', 'Categories'),
            ('comparative_project_hours', 'Comparative Project Hours'),
            ('accumulated_delivery_report', 'Accumulated Delivery Report'),
            ('individual_delivery_report', 'Individual Delivery Report')
        ], string="Printing Type", default='summary',
        help="Report grouping form.")
    budget_ids = fields.Many2many('bim.budget', string="Budgets")

    bim_stock_report_wizard_category = fields.Many2many('bim.stock.report.category.wizard')
    bim_stock_report_wizard_category_resum = fields.Many2many('bim.stock.report.cat.resum')
    general_data_report_wizard = fields.Many2many('general.data.report.wizard')

    user_id = fields.Many2one('res.users', string='Creado', default=lambda self: self.env.user)
    create_date = fields.Date(
        'Create Date', default=fields.Datetime.now)

    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    @api.onchange('equipment', 'material', 'labor')
    def onchange_resource(self):
        self.resource_all = True if (self.equipment and self.material and self.labor) else False

    @api.onchange('material')
    def onchange_material(self):
        self.invoice = self.material

    @api.onchange('labor')
    def onchange_labor(self):
        self.attendance = self.labor

    @api.onchange('equipment')
    def onchange_equipment(self):
        self.tools = self.equipment

    @api.onchange('resource_all')
    def onchange_resource_all(self):
        if not self.resource_all and (self.equipment and self.material and self.labor):
            self.equipment = self.material = self.labor = False
        elif self.resource_all:
            self.equipment = self.material = self.labor = True

    def get_space_quantity(self, concept, space):
        qty_space = 0
        if not concept.measuring_ids and concept.parent_id.type == 'departure':
            return self.get_space_quantity(concept.parent_id,space)
        qty_space = sum(m.amount_subtotal for m in concept.measuring_ids if m.space_id and m.space_id.id == space.id)
        return qty_space

    def recursive_quantity_space(self, resource, space, qty_space, qty=None):
        parent = resource.parent_id
        qty = qty is None and resource.quantity or qty

        if parent.type == 'departure':
            if not parent.measuring_ids:
                qty_partial = qty * parent.quantity
            else:
                qty_partial = qty
            return self.recursive_quantity_space(parent,space,qty_space,qty_partial)
        else:
            return qty * qty_space

    def recursive_quantity(self, resource, parent, qty=None):
        qty = qty is None and resource.quantity or qty
        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource,parent.parent_id,qty_partial)
        else:
            return qty * parent.quantity

    def get_quantity(self,resource,concept,space):
        total_qty = 0
        if concept:
            records = concept.child_ids.filtered(lambda c: c.product_id.id == resource.id)
            if space:
                qty_space = self.get_space_quantity(concept,space)
                for rec in records:
                    if rec.quantity > 0:
                        total_qty += self.recursive_quantity_space(rec,space,qty_space,None)
            else:
                for rec in records:
                    if rec.quantity > 0:
                        total_qty += self.recursive_quantity(rec,rec.parent_id,None)
        return total_qty

    def get_budget_quantity_hours(self,concept,resource):
        total_qty = 0
        if concept:
            records = concept.child_ids.filtered(lambda c: c.product_id.id == resource.id)
            for rec in records:
                if rec.quantity > 0:
                    total_qty += self.recursive_quantity(rec,rec.parent_id,None)
        return total_qty

    def print_report(self):
        if self.display_type == 'detailed':
            print ('.....1....')
        elif self.display_type == 'range':
            print ('.....2....')
        elif self.display_type == 'categories':
            print ('.....3....')
        else:
            self.print_xls()
        #action.update({'close_on_report_download': True})

    def get_stock_out(self,product,location,concept=False):
        quantity = 0
        if not concept:
            moves = self.env['stock.move'].search(['|',
                ('location_id', '=', location.id),
                ('location_dest_id', '=', location.id),
                ('product_id','=',product.id),
                ('picking_id.bim_concept_id','=',False)])
        else:
            moves = self.env['stock.move'].search(['|',
                ('location_id', '=', location.id),
                ('location_dest_id', '=', location.id),
                ('product_id','=',product.id),
                ('picking_id.bim_concept_id','=',concept.id)])
        if moves:
            for move in moves:
                if move.picking_id.include_for_bim:
                    if move.picking_id.returned:
                        quantity -= move.product_qty
                    else:
                        quantity += move.product_qty
        return quantity

    def get_part_out(self,product,res_type,concept):
        quantity = 0
        if concept:
            lines = self.env['bim.part.line'].search([
                ('name','=',product.id),
                ('resource_type','=',res_type),
                ('part_id.concept_id','=',concept.id)])
        if lines:
            quantity = sum(line.product_uom_qty for line in lines)
        return quantity

    def get_work_out(self,product,concept,lines):
        quantity = 0
        if lines:
            for line in lines:
                if line.type == 'budget_in':
                    if line.resource_id.product_id.id == product.id:
                        quantity += line.duration_real
                elif line.product_id == product.id:
                    quantity += line.duration_real
        return quantity


    def print_xls_comparative_project_hours(self):
        budget_ids = self.env['bim.budget'].search([
                    ('project_id','=',self.project_id.id)
                ])

        if not budget_ids:
            raise UserError(_('No budget found for this project'))

        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet(_("Product"))
        file_name = self.project_id.name + "_" + _("comparative_project_hours") + "_" + datetime.now().strftime("%d_%m_%Y_%H:%M:%S")
        style_border_table_top = xlwt.easyxf(
            'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

        _e = 0

        worksheet.write(0, _e, _("Nª"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Presupuesto"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Código"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Partida"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Cant HH (P)"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Importe (P)"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Cant HH (R)"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Importe (R)"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Dif.  Horas ( P - R )"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Dif. Importe ( P - R )"), style_border_table_top)
        _e += 1

        budget_ids = self.env['bim.budget'].search([
                    ('project_id','=',self.project_id.id)
                ])



        cont = 0
        row = 1
        for budget in budget_ids:
            cant_hh_r = 0
            for concept in budget.concept_ids:
                if concept.type == 'departure':
                    cont += 1
                    style = style_border_table_details
                    _d = 0
                    worksheet.write(row, _d, cont, style)
                    _d += 1
                    worksheet.write(row, _d, budget.name, style)
                    _d += 1
                    worksheet.write(row, _d, concept.code, style)
                    _d += 1
                    worksheet.write(row, _d, concept.name, style)

                    apu_men_hours = 0
                    _amount = 0

                    if budget.type_calc == 'apu':
                        _logger.info("APU")
                        apu_men_hours = concept.apu_men_hours
                        if concept.quantity > 0:
                            _amount += concept.apu_total_all_labor
                        else:
                            _amount += 0

                    else:
                        _logger.info("ESTANDAR")
                        son_concepts = self.env['bim.concepts'].search([
                            ('parent_id','=',concept.id),
                            ('type','=','labor')
                        ])

                        _logger.info("son_concepts %s",son_concepts)

                        hours = 0
                        if son_concepts:
                            for concept_son in son_concepts:
                                hours = concept_son.quantity
                                _amount += son_concepts.balance
                        apu_men_hours += hours * concept.quantity


                    _d += 1
                    worksheet.write(row, _d, apu_men_hours, style)
                    _d += 1
                    worksheet.write(row, _d, _amount, style)

                    attendances = self.env['hr.attendance'].search([('concept_id','=',concept.id)])
                    if attendances:
                        cant_hh_r = sum(attendance.worked_hours for attendance in attendances)
                        importe_r = sum(attendance.attendance_cost for attendance in attendances)
                    else:
                        cant_hh_r = 0
                        importe_r = 0


                    _d += 1
                    worksheet.write(row, _d, cant_hh_r, style)

                    _d += 1
                    worksheet.write(row, _d, importe_r, style)

                    _d += 1
                    worksheet.write(row, _d, apu_men_hours-cant_hh_r, style)

                    _d += 1
                    worksheet.write(row, _d, _amount-importe_r, style)
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
        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'no_destroy': False,
        }




    def print_xls_categories_list(self):
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet(_("Product"))
        file_name = self.project_id.name + "_" + _("Product") + "_" + datetime.now().strftime("%d_%m_%Y_%H:%M:%S")
        style_border_table_top = xlwt.easyxf(
            'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

        _e = 0

        worksheet.write(0, _e, _("Categoría"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Código"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Descripción"), style_border_table_top)
        _e += 1

        worksheet.write(0, _e, _("Descripción Ampliada"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Unidades"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Coste"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Total precio coste"), style_border_table_top)
        _e += 1


        self.bim_stock_report_wizard_category.unlink()
        self.bim_stock_report_wizard_category_resum.unlink()




        # stock.picking IN



        stock_picking_ids = self.env['stock.picking'].search([
                    ('state','in',['done']),
                    ('bim_project_id','=',self.project_id.id),
                    ('include_for_bim','=',True)
                ])

        if stock_picking_ids:
            for order in stock_picking_ids:
                for line in order.move_ids:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,
                            {
                                'name':line.product_id.id,
                                'stock_picking':line.quantity,
                                'category_id' : line.product_id.categ_id.id
                            }

                        )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.stock_picking += line.quantity



        # stock.picking OUT
        stock_picking_ids = self.env['stock.picking'].search([
                    ('state','in',['done']),
                    ('picking_type_id.code','=','outgoing'),
                    ('bim_project_id','=',self.project_id.id),
                ])

        if stock_picking_ids:
            for order in stock_picking_ids:
                for line in order.move_ids:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,

                            {
                                'name':line.product_id.id,
                                'stock_picking_out':line.quantity_done,
                                'category_id' : line.product_id.categ_id.id,
                            }

                        )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.stock_picking_out += line.quantity






        bim_stock_report_wizard_category_resm = self.bim_stock_report_wizard_category.filtered(lambda r: r.name.categ_id.name)

        cont = 0
        row = 1

        category_name = ""
        tota_qty = 0
        cote_promedio = 0
        importe = 0

        for l in bim_stock_report_wizard_category_resm:
            cont += 1

            product_id = self.env['product.product'].search([('id','=',l.name.id)])


            if category_name != product_id.categ_id.name and category_name != "":
               change_category = True
               tota_qty = 0
               cote_promedio = 0
               importe = 0
            else:
                change_category = False
                tota_qty += l.stock_picking - l.stock_picking_out
                cote_promedio += product_id.standard_price
                importe += product_id.standard_price * tota_qty


            category_name = product_id.categ_id.name

            style = style_border_table_details
            _d = 0


            worksheet.write(row, _d, product_id.categ_id.name, style)
            _d += 1

            #333
            worksheet.write(row, _d, product_id.default_code, style)
            _d += 1

            worksheet.write(row, _d, product_id.name, style)
            _d += 1

            worksheet.write(row, _d, "", style)
            _d += 1

            worksheet.write(row, _d, l.stock_picking - l.stock_picking_out, style)
            _d += 1

            worksheet.write(row, _d, product_id.standard_price, style)
            _d += 1

            worksheet.write(row, _d, (l.stock_picking - l.stock_picking_out) * product_id.standard_price, style)
            _d += 1



            row += 1


            print(l.name.name)
            print(l.name.categ_id.name)
            print(l.stock_picking)
            print(l.stock_picking_out)
            print("---------------------------------------------------")







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
        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'no_destroy': False,
        }




    def print_xls_categories(self):
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet(_("Product"))
        file_name = self.project_id.name + "_" + _("Product") + "_" + datetime.now().strftime("%d_%m_%Y_%H:%M:%S")
        style_border_table_top = xlwt.easyxf(
            'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

        _e = 0

        worksheet.write(0, _e, _("Nª"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Category"), style_border_table_top)
        _e += 1

        if self.display_type == 'categories_product':
            worksheet.write(0, _e, _("Code"), style_border_table_top)
            _e += 1
            worksheet.write(0, _e, _("Description"), style_border_table_top)
            _e += 1

        worksheet.write(0, _e, _("Purchase Requisition"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Purchase Request"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Purchase Order"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Stock In"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Stock Out"), style_border_table_top)
        _e += 1
        worksheet.write(0, _e, _("Purchase Invoices"), style_border_table_top)
        _e += 1

        self.bim_stock_report_wizard_category.unlink()
        self.bim_stock_report_wizard_category_resum.unlink()

        """
        SOLICITUD DE MATERIALES
        """

        purchase_requisition_ids = self.env['bim.purchase.requisition'].search([
                    ('project_id','=',self.project_id.id)
                ])
        if purchase_requisition_ids:
            for order in purchase_requisition_ids:
                for line in order.product_ids:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,
                                {
                                    'name':line.product_id.id,
                                    'bim_purchase_requisition':line.quant
                                })]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.bim_purchase_requisition += line.quant



        """
        SOLICITUD DE SERVICIOS
        """

        purchase_service_ids = self.env['bim.purchase.services'].search([
                    ('project_id','=',self.project_id.id)
                ])

        if purchase_service_ids:
            for order in purchase_service_ids:
                for line in order.product_ids:
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,
                                {
                                    'name':line.product_id.id,
                                    'bim_purchase_requisition':line.quant
                                })]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.bim_purchase_requisition += line.quant


        """
        COTIZACIONES DE COMPRA
        """

        purchase_order_ids = self.env['purchase.order'].search([
                    ('state','in',['draft']),
                    ('project_id','=',self.project_id.id)
                ])
        if purchase_order_ids:
            for order in purchase_order_ids:
                for line in order.order_line:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,
                            {
                            'name':line.product_id.id,
                            'purchase_order_request':line.product_qty
                            }
                            )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.purchase_order_request += line.product_qty


        """
        ORDEN DE COMPRA
        """

        purchase_order_ids = self.env['purchase.order'].search([
                    ('state','in',['done','purchase']),
                    ('project_id','=',self.project_id.id)
                ])
        if purchase_order_ids:
            for order in purchase_order_ids:
                for line in order.order_line:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,

                            {
                                'name':line.product_id.id,
                                'purchase_order':line.product_qty
                            }

                        )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.purchase_order += line.product_qty


        """
        stock.picking IN
        """
        stock_picking_ids = self.env['stock.picking'].search([
                    ('state','in',['done']),
                    ('bim_project_id','=',self.project_id.id),
                    ('include_for_bim','=',True)
                ])

        if stock_picking_ids:
            for order in stock_picking_ids:
                for line in order.move_ids:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,
                            {
                                'name':line.product_id.id,
                                'stock_picking':line.quantity
                            }

                        )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.stock_picking += line.quantity


        """
        stock.picking OUT
        """
        stock_picking_ids = self.env['stock.picking'].search([
                    ('state','in',['done']),
                    ('picking_type_id.code','=','outgoing'),
                    ('bim_project_id','=',self.project_id.id),
                ])

        if stock_picking_ids:
            for order in stock_picking_ids:
                for line in order.move_ids:
                    # buscamos a ver si ya esta el producto en products
                    if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                        self.bim_stock_report_wizard_category = [(0,0,

                            {
                                'name':line.product_id.id,
                                'stock_picking_out':line.quantity_done
                            }

                        )]
                    else:
                        # si esta, buscamos la linea y le sumamos la cantidad
                        for line_category in self.bim_stock_report_wizard_category:
                            if line_category.name.id == line.product_id.id:
                                line_category.stock_picking_out += line.quantity


        """
        ACCOUNT MOVE IN
        """
        account_move_ids = self.env['account.move.line'].search([
                    ('move_id.state','=','posted'),
                    ('move_id.move_type','=', ['in_invoice','in_refund']),
                    ('project_id','=',self.project_id.id)
                ])

        if account_move_ids:
            for line in account_move_ids:
                # buscamos a ver si ya esta el producto en products
                if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                    self.bim_stock_report_wizard_category = [(0,0,
                        {
                            'name':line.product_id.id,
                            'account_move':line.quantity * -1 if line.move_id.move_type == 'in_refund' else line.quantity
                        }

                    )]
                else:
                    # si esta, buscamos la linea y le sumamos la cantidad
                    for line_category in self.bim_stock_report_wizard_category:
                        if line_category.name.id == line.product_id.id:
                            line_category.account_move += line.quantity * -1 if line.move_id.move_type == 'in_refund' else line.quantity





        if self.display_type == 'categories':
            for line in self.bim_stock_report_wizard_category:
                if line.name.categ_id.id not in self.bim_stock_report_wizard_category_resum.mapped('category_id.id'):
                    self.bim_stock_report_wizard_category_resum = [(0,0,
                        {
                            'category_id':line.name.categ_id.id,
                            'bim_purchase_requisition':line.bim_purchase_requisition,
                            'purchase_order_request':line.purchase_order_request,
                            'purchase_order':line.purchase_order,
                            'stock_picking':line.stock_picking,
                            'stock_picking_out':line.stock_picking_out,
                            'account_move':line.account_move
                        }
                    )]
                else:
                     self.bim_stock_report_wizard_category_resum = [(1,line.id,
                        {
                            'bim_purchase_requisition':line.bim_purchase_requisition,
                            'purchase_order_request':line.purchase_order_request,
                            'purchase_order':line.purchase_order,
                            'stock_picking':line.stock_picking,
                            'stock_picking_out':line.stock_picking_out,
                            'account_move':line.account_move
                        }
                    )]
            row = 1
            cont = 0


            bim_stock_report_wizard_category_resum_filtered = self.bim_stock_report_wizard_category_resum.filtered(lambda r: r.category_id.name)
            bim_stock_report_wizard_category_resum = bim_stock_report_wizard_category_resum_filtered.sorted(key=lambda r: r.category_id.name)


            for line in bim_stock_report_wizard_category_resum:
                cont += 1
                style = style_border_table_details
                _d = 0
                worksheet.write(row, _d, cont, style)

                _d += 1
                worksheet.write(row, _d, line.category_id.name, style)
                _d += 1
                worksheet.write(row, _d, line.bim_purchase_requisition, style)
                _d += 1
                worksheet.write(row, _d, line.purchase_order_request, style)
                _d += 1
                worksheet.write(row, _d, line.purchase_order, style)
                _d += 1
                worksheet.write(row, _d, line.stock_picking, style)
                _d += 1
                worksheet.write(row, _d, line.stock_picking_out, style)
                _d += 1
                worksheet.write(row, _d, line.account_move, style)
                _d += 1

                row += 1


        else:
            row = 1
            cont = 0

            bim_stock_report_wizard_category_filtered = self.bim_stock_report_wizard_category.filtered(lambda r: r.name.categ_id.name)

            bim_stock_report_wizard_category = bim_stock_report_wizard_category_filtered.sorted(key=lambda r: r.name.categ_id.name)

            for line in bim_stock_report_wizard_category_filtered:
                cont += 1
                style = style_border_table_details
                _d = 0
                worksheet.write(row, _d, cont, style)
                _d += 1
                worksheet.write(row, _d, line.name.categ_id.name, style)
                _d += 1
                worksheet.write(row, _d, line.name.default_code if line.name.default_code else "-", style)
                _d += 1
                worksheet.write(row, _d, line.name.name, style)
                _d += 1
                worksheet.write(row, _d, line.bim_purchase_requisition, style)
                _d += 1
                worksheet.write(row, _d, line.purchase_order_request, style)
                _d += 1
                worksheet.write(row, _d, line.purchase_order, style)
                _d += 1
                worksheet.write(row, _d, line.stock_picking, style)
                _d += 1
                worksheet.write(row, _d, line.stock_picking_out, style)
                _d += 1
                worksheet.write(row, _d, line.account_move, style)
                _d += 1
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
        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'no_destroy': False,
        }

    def print_xls(self):
        if self.display_type == 'accumulated_delivery_report' or self.display_type == 'individual_delivery_report':
            # Calculamos los valores que tendra el reporte
            # Eliminamos los valores que tengo
            self.bim_stock_report_wizard_category.unlink()


            if not self.date_beg or not self.date_end:
                # Buscamos los albaranes
                stock_picking_ids = self.env['stock.picking'].search([
                        ('state','in',['done']),
                        ('bim_project_id','=',self.project_id.id),
                        ('include_for_bim','=',True)
                    ])
            else:
                stock_picking_ids = self.env['stock.picking'].search([
                        ('state','in',['done']),
                        ('bim_project_id','=',self.project_id.id),
                        ('include_for_bim','=',True),
                        ('scheduled_date','>=',self.date_beg),
                        ('scheduled_date','<=',self.date_end)
                    ])


            _logger.info("1# stock_picking_ids : %s", stock_picking_ids)



            if stock_picking_ids and self.display_type == 'individual_delivery_report':
                for order in stock_picking_ids:
                    for line in order.move_ids:
                        if line.product_id.resource_type == 'M' and not self.material:
                            continue
                        if line.product_id.resource_type == 'Q' and not self.equipment:
                            continue
                        if line.product_id.resource_type == 'H' and not self.labor:
                            continue

                        default_code = line.product_id.default_code
                        if default_code:
                            default_code =  "[" + default_code + "]"
                            description = line.description_picking.replace(default_code,"")
                        else:
                            description = line.description_picking

                        v =    {
                                    'name':line.product_id.id,
                                    'stock_picking':line.quantity if order.picking_type_id.code == 'incoming' else -line.quantity,
                                    'category_id' : line.product_id.categ_id.id,
                                    'stock_picking_id':order.id,
                                    'total_amount' : line.subtotal  if order.picking_type_id.code == 'incoming' else -line.subtotal,
                                    'description': description
                                }

                        self.bim_stock_report_wizard_category = [(0,0,v

                        )]

            _logger.info("2# bim_stock_report_wizard_category : %s", self.bim_stock_report_wizard_category)

            for line in self.bim_stock_report_wizard_category:
                pass



            if stock_picking_ids and self.display_type == 'accumulated_delivery_report':
                for order in stock_picking_ids:
                    for line in order.move_ids:
                        if line.product_id.resource_type == 'M' and not self.material:
                            continue
                        if line.product_id.resource_type == 'Q' and not self.equipment:
                            continue
                        if line.product_id.resource_type == 'H' and not self.labor:
                            continue

                        # buscamos a ver si ya esta el producto en products
                        if line.product_id.id not in self.bim_stock_report_wizard_category.mapped('name.id'):
                            self.bim_stock_report_wizard_category = [(0,0,
                                {
                                    'name':line.product_id.id,
                                    'stock_picking':line.quantity if order.picking_type_id.code == 'incoming' else -line.quantity,
                                    'category_id' : line.product_id.categ_id.id,
                                    'total_amount' : line.subtotal  if order.picking_type_id.code == 'incoming' else -line.subtotal
                                }
                            )]
                        else:
                            # si esta, buscamos la linea y le sumamos la cantidad
                            for line_category in self.bim_stock_report_wizard_category:
                                if line_category.name.id == line.product_id.id:
                                    if order.picking_type_id.code == 'incoming':
                                        line_category.stock_picking += line.quantity
                                        line_category.total_amount += line.subtotal

                                    if order.picking_type_id.code == 'outgoing':
                                        line_category.stock_picking -= line.quantity
                                        line_category.total_amount -= line.subtotal



        # LIMPIAMOS LOS DATOS ########
        _logger.info("# LIMPIAMOS LOS DATOS ######## .....................................")
        _logger.info(self.general_data_report_wizard)
        self.general_data_report_wizard.unlink()

        if self.display_type == 'accumulated_delivery_report':
            _logger.info(" === accumulated_delivery_report === ")

            # VIAJES BEGIN ########
            _logger.info("# VIAJES BEGIN ######## .....................................")
            _logger.info(self.general_data_report_wizard)


            if not self.date_beg or not self.date_end:
                tms_shipment_ids = self.env['tms.shipment'].search([
                        ('state','in',['confirmed']),
                        ('bim_project_origin_id','=',self.project_id.id)
                    ])
            else:
                tms_shipment_ids = self.env['tms.shipment'].search([
                        ('state','in',['confirmed']),
                        ('bim_project_origin_id','=',self.project_id.id),
                        ('date','>=',self.date_beg),
                        ('date','<=',self.date_end)
                    ])



            for shipment in tms_shipment_ids:
                # add data to report

                t_dict = {
                        'name':shipment.name,
                        'date':shipment.date,
                        'product_code': 'KM',
                        'description': 'TRANSPORTE',
                        'qty':shipment.qty,
                        'total_amount':shipment.total,
                        'type' : 'TRANSPORTE'
                    }

                _logger.info(t_dict)
                self.general_data_report_wizard = [(0,0, t_dict)]

            _logger.info("self.general_data_report_wizard : %s", self.general_data_report_wizard)
            # VIAJES END ########



            # OTROS GASTOS BEGIN ########
            _logger.info("OTROS GASTOS BEGIN ######## .....................................")
            _logger.info(self.general_data_report_wizard)

            if not self.date_beg or not self.date_end:
                other_expense_line_ids = self.env['other.expense.line'].search([
                        ('project_id','=',self.project_id.id)
                    ])
            else:
                other_expense_line_ids = self.env['other.expense.line'].search([
                        ('project_id','=',self.project_id.id),
                        ('date','>=',self.date_beg),
                        ('date','<=',self.date_end)
                    ])

            for expense in other_expense_line_ids:
                general_data_report_other_wizard_id = self.general_data_report_wizard.filtered(lambda r: r.product_code == expense.product_id.default_code and r.type == 'OTHER-ACC')
                general_data_report_other_wizard_id = general_data_report_other_wizard_id[0] if general_data_report_other_wizard_id else False

                if not general_data_report_other_wizard_id:
                    other_dict = {
                            'name':expense.other_expense_id.name,
                            'date':expense.other_expense_id.date,
                            'product_code': expense.product_id.default_code,
                            'description': expense.name,
                            'type': 'OTHER-ACC',
                            'qty':expense.qty,
                            'total_amount':expense.total,

                        }
                    _logger.info(other_dict)
                    self.general_data_report_wizard = [(0,0,other_dict)]
                else:
                    general_data_report_other_wizard_id.qty += expense.qty
                    general_data_report_other_wizard_id.total_amount += expense.total

            # OTROS GASTOS END ########

            # MANO DE OBRA BEGIN MO ########
            _logger.info("# MANO DE OBRA BEGIN MO ######## .....................................")
            _logger.info(self.general_data_report_wizard)


            if not self.date_beg or not self.date_end:
                hr_attendance_ids = self.env['hr.attendance'].search([
                        ('project_id','=',self.project_id.id)
                    ])
            else:
                hr_attendance_ids = self.env['hr.attendance'].search([
                        ('project_id','=',self.project_id.id),
                        ('check_in','>=',self.date_beg),
                        ('check_in','<=',self.date_end)
                    ])

            if hr_attendance_ids:
                for attendance in hr_attendance_ids:
                    # add data to report


                    # LABOR-ACC-DIETAS
                    general_data_report_wizard_modietas_id = self.general_data_report_wizard.filtered(lambda r: r.type == 'LABOR-ACC-DIETAS')
                    general_data_report_wizard_modietas_id = general_data_report_wizard_modietas_id[0] if general_data_report_wizard_modietas_id else False

                    try:
                        if not general_data_report_wizard_modietas_id:
                            modietas_dict = {
                                    'type': 'LABOR-ACC-DIETAS',
                                    'qty' : attendance.bim_dietas,
                                    'total_amount' : attendance.bim_dietas * attendance.employee_id.bim_dietas
                                }

                            _logger.info(modietas_dict)
                            self.general_data_report_wizard = [(0,0,modietas_dict)]

                        else:
                            general_data_report_wizard_modietas_id.qty += attendance.bim_dietas
                            general_data_report_wizard_modietas_id.total_amount += attendance.bim_dietas * attendance.employee_id.bim_dietas



                        # LABOR-ACC-MOD
                        general_data_report_wizard_mod_id = self.general_data_report_wizard.filtered(lambda r: r.type == 'LABOR-ACC-MOD')
                        general_data_report_wizard_mod_id = general_data_report_wizard_mod_id[0] if general_data_report_wizard_mod_id else False

                        if not general_data_report_wizard_mod_id:
                            mod_dict = {
                                    'type': 'LABOR-ACC-MOD',
                                    'qty' : attendance.bim_mod,
                                    'total_amount' : attendance.bim_mod * attendance.employee_id.bim_mod
                                }

                            _logger.info(mod_dict)
                            self.general_data_report_wizard = [(0,0,mod_dict)]

                        else:
                            general_data_report_wizard_mod_id.qty += attendance.bim_mod
                            general_data_report_wizard_mod_id.total_amount += attendance.bim_mod * attendance.employee_id.bim_mod




                        # LABOR-ACC-MO
                        general_data_report_wizard_mo_id = self.general_data_report_wizard.filtered(lambda r: r.type == 'LABOR-ACC-MO')
                        general_data_report_wizard_mo_id = general_data_report_wizard_mo_id[0] if general_data_report_wizard_mo_id else False

                        if not general_data_report_wizard_mo_id:
                            mo_dict = {
                                    'type': 'LABOR-ACC-MO',
                                    'qty' : attendance.bim_mo,
                                    'total_amount' : attendance.bim_mo * attendance.employee_id.bim_mo
                                }

                            _logger.info(mo_dict)
                            self.general_data_report_wizard = [(0,0,mo_dict)]

                        else:
                            general_data_report_wizard_mo_id.qty += attendance.bim_mo
                            general_data_report_wizard_mo_id.total_amount += attendance.bim_mo * attendance.employee_id.bim_mo



                        # LABOR-ACC-MOE
                        general_data_report_wizard_moe_id = self.general_data_report_wizard.filtered(lambda r: r.type == 'LABOR-ACC-MOE')
                        general_data_report_wizard_moe_id = general_data_report_wizard_moe_id[0] if general_data_report_wizard_moe_id else False

                        if not general_data_report_wizard_moe_id:
                            moe_dict = {
                                    'type': 'LABOR-ACC-MOE',
                                    'qty' : attendance.bim_moe,
                                    'total_amount' : attendance.bim_moe * attendance.employee_id.bim_moe
                                }

                            _logger.info(moe_dict)
                            self.general_data_report_wizard = [(0,0,moe_dict)]

                        else:
                            general_data_report_wizard_moe_id.qty += attendance.bim_moe
                            general_data_report_wizard_moe_id.total_amount += attendance.bim_moe * attendance.employee_id.bim_moe
                    except Exception as e:
                        _logger.info("Error : %s", e)

            # MANO DE OBRA END ########
            _logger.info("<.....................................................")
            _logger.info(self.general_data_report_wizard)
            _logger.info(".....................................................>")

        else:
            _logger.info(" === begin individual_delivery_report === ")

            # VIAJES BEGIN ########
            _logger.info("# VIAJES BEGIN ######## .....................................")
            _logger.info(self.general_data_report_wizard)


            if not self.date_beg or not self.date_end:
                tms_shipment_ids = self.env['tms.shipment'].search([
                        ('state','in',['confirmed']),
                        ('bim_project_origin_id','=',self.project_id.id)
                    ])
            else:
                tms_shipment_ids = self.env['tms.shipment'].search([
                        ('state','in',['confirmed']),
                        ('bim_project_origin_id','=',self.project_id.id),
                        ('date','>=',self.date_beg),
                        ('date','<=',self.date_end)
                    ])



            for shipment in tms_shipment_ids:
                # add data to report
                t_dict = {
                        'name':shipment.name,
                        'date':shipment.date,
                        'product_code': 'KM',
                        'description': 'TRANSPORTE',
                        'qty':shipment.qty,
                        'total_amount':shipment.total,
                        'type' : 'TRANSPORTE'
                    }

                _logger.info(t_dict)
                self.general_data_report_wizard = [(0,0, t_dict)]

            _logger.info("self.general_data_report_wizard : %s", self.general_data_report_wizard)
            # VIAJES END ########



            # MANO DE OBRA BEGIN MO ########
            _logger.info("# MANO DE OBRA BEGIN MO ######## .....................................")
            _logger.info(self.general_data_report_wizard)


            if not self.date_beg or not self.date_end:
                hr_attendance_ids = self.env['hr.attendance'].search([
                        ('project_id','=',self.project_id.id)
                    ])
            else:
                hr_attendance_ids = self.env['hr.attendance'].search([
                        ('project_id','=',self.project_id.id),
                        ('check_in','>=',self.date_beg),
                        ('check_in','<=',self.date_end)
                    ])

            if hr_attendance_ids:
                for attendance in hr_attendance_ids:
                    try:
                        modietas_dict = {
                                'name':attendance.employee_id.name,
                                'date':attendance.check_in,
                                'type': 'LABOR-ACC-DIETAS',
                                'qty' : attendance.bim_dietas,
                                'total_amount' : attendance.bim_dietas * attendance.employee_id.bim_dietas
                            }
                        _logger.info(modietas_dict)
                        self.general_data_report_wizard = [(0,0,modietas_dict)]




                        # LABOR-ACC-MOD
                        mod_dict = {
                                    'name':attendance.employee_id.name,
                                    'type': 'LABOR-ACC-MOD',
                                    'date':attendance.check_in,
                                    'qty' : attendance.bim_mod,
                                    'total_amount' : attendance.bim_mod * attendance.employee_id.bim_mod
                                }
                        _logger.info(mod_dict)
                        self.general_data_report_wizard = [(0,0,mod_dict)]




                        # LABOR-ACC-MO
                        mo_dict = {
                                    'date':attendance.check_in,
                                    'name':attendance.employee_id.name,
                                    'type': 'LABOR-ACC-MO',
                                    'qty' : attendance.bim_mo,
                                    'total_amount' : attendance.bim_mo * attendance.employee_id.bim_mo
                                }

                        _logger.info(mo_dict)
                        self.general_data_report_wizard = [(0,0,mo_dict)]



                        # LABOR-ACC-MOE
                        moe_dict = {
                                    'date':attendance.check_in,
                                    'name':attendance.employee_id.name,
                                    'type': 'LABOR-ACC-MOE',
                                    'qty' : attendance.bim_moe,
                                    'total_amount' : attendance.bim_moe * attendance.employee_id.bim_moe
                                }

                        _logger.info(moe_dict)
                        self.general_data_report_wizard = [(0,0,moe_dict)]
                    except Exception as e:
                        _logger.info("Error : %s", e)


            # MANO DE OBRA END ########



            # OTROS GASTOS BEGIN ########
            _logger.info("OTROS GASTOS BEGIN ######## .....................................")
            _logger.info(self.general_data_report_wizard)

            if not self.date_beg or not self.date_end:
                other_expense_line_ids = self.env['other.expense.line'].search([
                        ('project_id','=',self.project_id.id)
                    ])
            else:
                other_expense_line_ids = self.env['other.expense.line'].search([
                        ('project_id','=',self.project_id.id),
                        ('date','>=',self.date_beg),
                        ('date','<=',self.date_end)
                    ])

            for expense in other_expense_line_ids:
                other_dict = {
                            'name':expense.other_expense_id.name,
                            'date':expense.other_expense_id.date,
                            'product_code': expense.product_id.default_code,
                            'description': expense.name,
                            'type': 'OTHER-ACC',
                            'qty':expense.qty,
                            'total_amount':expense.total,

                        }
                _logger.info(other_dict)
                self.general_data_report_wizard = [(0,0,other_dict)]

            # OTROS GASTOS END ########
            _logger.info(" === end individual_delivery_report === ")














        if self.display_type == 'accumulated_delivery_report':
            self.bim_stock_report_wizard_category = self.bim_stock_report_wizard_category.sorted(key=lambda r: r.category_id.name)
            """
            if not self.bim_stock_report_wizard_category:
                raise UserError(_('No data found for this report'))"""
            return self.env.ref('base_bim_2.acc_accumulated_delivery_report').report_action(self)

        elif self.display_type == 'individual_delivery_report':
            # self.bim_stock_report_wizard_category lo organizo por category_id
            self.bim_stock_report_wizard_category = self.bim_stock_report_wizard_category.sorted(key=lambda r: r.category_id.name)
            """
            if not self.bim_stock_report_wizard_category:
                raise UserError(_('No data found for this report'))"""
            return self.env.ref('base_bim_2.acc_individual_delivery_report').report_action(self)

        elif self.display_type == 'categories_product_list':
            return self.print_xls_categories_list()
        elif self.display_type == 'categories' or self.display_type == 'categories_product':
            return self.print_xls_categories()
        elif self.display_type == 'comparative_project_hours':
            return self.print_xls_comparative_project_hours()
        if self.budget_ids:
            return self.print_xls_from_budget(self.budget_ids)

        project = self.project_id
        location = project.stock_location_id
        base_domain = [('bim_project_id','=',project.id),('include_for_bim','=',True),('state','=','done')]
        part_domain = [('project_id','=',project.id),('state','=','validated')]
        attendance_domain = [('project_id','=',project.id),('check_out','!=',False)]
        tools_domain = [('project_id','=',project.id)]
        workorder_active = False
        invoice_domain = [('display_type','=','product'),('move_id.move_type','in',['in_invoice','in_refund']),('move_id.state','=','posted'),('move_id.include_for_bim','=',True)]
        if project.analytic_id:
            invoice_domain.append(('analytic_account_id', '=', project.analytic_id.id))
        if self.display_type == 'summary':
            header = ["Código","Nombre","Inventario General","Inventario Ubicación","Presupuesto","Partida","Uom","Salidas","Coste","Importe"]
        elif self.display_type == 'range':
            base_domain.append(('date','>=',self.date_beg))
            base_domain.append(('date','<=',self.date_end))
            invoice_domain.append(('move_id.invoice_date','<=',self.date_end))
            invoice_domain.append(('move_id.invoice_date','>=',self.date_beg))
            part_domain.append(('date','>=',self.date_beg))
            part_domain.append(('date','<=',self.date_end))
            attendance_domain.append(('check_in','>=',self.date_beg))
            attendance_domain.append(('check_out','<=',self.date_end))
            tools_domain.append(('date_start','>=',self.date_beg))
            tools_domain.append(('date_end','<=',self.date_end))
            header = ["Código","Nombre","Inventario General","Inventario Ubicación","Presupuesto","Partida","Uom","Salidas","Coste","Importe"]
        else:
            header = ["Código","Nombre","Movimiento/Parte","Presupuesto","Partida","Objeto de Obra","Espacio","Proveedor","Descripción","Fecha","Inventario General","Inventario Ubicación","Uom","Cantidad","Coste","Importe","Cantidad","Coste","Importe","Cantidad","Importe"]

        # Verificamos si esta activo Orden de Trabajo
        if 'bim_workorder' in self.env.registry._init_modules:
            workorder_active = True
            workorders = self.env['bim.workorder'].search([('project_id','=',project.id)])

        # Buscamos los picking de la Obra
        picking_obj = self.env['stock.picking']

        outgoing_domain = base_domain + [('include_for_bim','=', True),('returned','=',False)]
        pickings = picking_obj.search(outgoing_domain)

        incoming_domain = base_domain + [('include_for_bim','=', True),('returned','=',True)]
        pickings += picking_obj.search(incoming_domain)

        #Buscamos las partidas
        departs = pickings.mapped('bim_concept_id')

        #Buscamos las Partes de la Obra
        parts = self.env['bim.part'].search(part_domain)
        dep_parts = parts.mapped('concept_id')

        # Buscamos asistencia de la Obra
        attendances = self.env['hr.attendance'].search(attendance_domain)
        employees = attendances.mapped('employee_id')

        # Buscamos las herramientas
        tools_lines = self.env['bim.tool.use'].search(tools_domain)
        tools_product = tools_lines.mapped('product_id')

        # Buscamos las Facturas de Compra desde las lineas
        invoice_lines = self.env['account.move.line'].search(invoice_domain)
        invoice_products = invoice_lines.mapped('product_id')
        invoice_concepts = invoice_lines.mapped('concept_id')
        invoice_records = invoice_lines.mapped('move_id')

        # Datos Para excel
        wb = Workbook(encoding='utf-8')
        ws = wb.add_sheet(_('Book'))
        Quants = self.env['stock.quant']
        style_title = easyxf('font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center')
        style_negative = easyxf('font: color red;')

        row = 0
        index = 0
        if self.display_type == 'detailed':
            ws.write_merge(row,row,13,15, _("BUDGET"),style_title)
            ws.write_merge(row,row,16,18, _("REAL EXECUTED"),style_title)
            ws.write_merge(row,row,19,20, _("DIFFERENCE"),style_title)
            row = row + 1

        for head in header:
            ws.write(row, index, head, style_title)
            index = index + 1

        row = row + 1

        # CALCULO DE LINEAS RESUMIDAS y RANGO
        if self.display_type in ['range','summary']:
            # (Partes)
            for concept in dep_parts:
                # Mano de Obra
                if self.labor:
                    product_ids = []
                    for part in parts.filtered(lambda pt: pt.concept_id.id == concept.id):
                        products = part.lines_ids.mapped('name')
                        for product in products.filtered(lambda p: p.resource_type == 'H'):
                            if not product.id in product_ids:
                                qty_location = Quants._get_available_quantity(product,location)
                                part_outs = self.get_part_out(product,'H',concept)
                                ws.write(row, 0, product.default_code if product.default_code else '-')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, part_outs)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, part_outs*product.standard_price)
                                product_ids.append(product.id)
                                row += 1

                    # Mano de Obra desde Orden de TRabajo (Si esta instalado bim_workorder)
                    if workorder_active and workorders:
                        product_ids = []
                        bwor_obj = self.env['bim.workorder.resources']
                        for word in workorders:
                            for bwoc in word.concept_ids:
                                lines_with = bwor_obj.search([('workorder_concept_id','=',bwoc.id),('workorder_id','=',bwoc.workorder_id.id)])
                                lines_out = bwor_obj.search([('workorder_id','=',bwoc.workorder_id.id),('departure_id','=',bwoc.concept_id.id)])
                                lines = lines_with + lines_out
                                lines_mo = lines.filtered(lambda x:x.qty_execute > 0)

                                for line in lines_mo:
                                    product = line.resource_id.product_id if line.type == 'budget_in' else line.product_id
                                    if not product.id in product_ids:
                                        concept = line.concept_id if line.type == 'budget_in' else line.departure_id
                                        work_outs = self.get_work_out(product,concept,lines_mo)
                                        qty_location = Quants._get_available_quantity(product,location)
                                        ws.write(row, 0, product.default_code if product.default_code else '-')
                                        ws.write(row, 1, product.display_name)
                                        ws.write(row, 2, product.qty_available or 0)
                                        ws.write(row, 3, qty_location or 0)
                                        ws.write(row, 4, concept and concept.budget_id.display_name or '')
                                        ws.write(row, 5, concept and concept.name or '')
                                        ws.write(row, 6, product.uom_id.name)
                                        ws.write(row, 7, work_outs)
                                        ws.write(row, 8, product.standard_price)
                                        ws.write(row, 9, work_outs*product.standard_price)
                                        product_ids.append(product.id)
                                        row += 1
                # Equipos
                if self.equipment:
                    product_ids = []
                    for part in parts.filtered(lambda pt: pt.concept_id.id == concept.id):
                        products = part.lines_ids.mapped('name')
                        for product in products.filtered(lambda p: p.resource_type == 'Q'):
                            if not product.id in product_ids:
                                qty_location = Quants._get_available_quantity(product,location)
                                part_outs = self.get_part_out(product,'Q',concept)
                                ws.write(row, 0, product.default_code if product.default_code else '-')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, part_outs)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, part_outs*product.standard_price)
                                product_ids.append(product.id)
                                row += 1

            if self.resource_all:
                for balance in self.project_id.opening_balance_ids:
                    ws.write(row, 0, balance.name)
                    ws.write(row, 1, _("Opening Balance"))
                    ws.write(row, 2, '')
                    ws.write(row, 3, '')
                    ws.write(row, 4, balance.budget_id.display_name)
                    ws.write(row, 5, balance.concept_id.name if balance.concept_id else '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, balance.amount)
                    row += 1

            # Materiales (Picking)
            if self.material:
                for concept in departs:
                    product_ids = []
                    for pick in pickings.filtered(lambda sp: sp.bim_concept_id.id == concept.id):
                        products = pick.move_ids.mapped('product_id')
                        for product in products:
                            if not product.id in product_ids:
                                quantity_done = self.get_stock_out(product, location, concept)
                                qty_location = Quants._get_available_quantity(product,location)
                                ws.write(row, 0, product.default_code or '')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, quantity_done)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, quantity_done * product.standard_price)
                                product_ids.append(product.id)
                                row += 1
                product_ids = []
                for pick in pickings.filtered(lambda sp: not sp.bim_concept_id):
                    for product in pick.move_ids.mapped('product_id'):
                        if not product.id in product_ids:
                            qty_location = Quants._get_available_quantity(product,location)
                            quantity_done = self.get_stock_out(product, location)
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, product.qty_available or 0)
                            ws.write(row, 3, qty_location or 0)
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, product.uom_id.name)
                            ws.write(row, 7, quantity_done)
                            ws.write(row, 8, product.standard_price)
                            ws.write(row, 9, quantity_done * product.standard_price)
                            product_ids.append(product.id)
                            row += 1
            # aqui va asistencia resumida
            if self.attendance:
                for employee in employees:
                    employee_attendances = attendances.filtered_domain([('employee_id','=',employee.id)])
                    concepts = employee_attendances.mapped('concept_id')
                    for concept in concepts:
                        total_hours = 0
                        total_cost = 0
                        for attendance in employee_attendances.filtered_domain([('concept_id','=',concept.id)]):
                            total_hours += attendance.worked_hours
                            total_cost += attendance.attendance_cost
                        ws.write(row, 0, employee.bim_resource_id.default_code if employee.bim_resource_id else '')
                        ws.write(row, 1, employee.bim_resource_id.display_name if employee.bim_resource_id else employee.name )
                        ws.write(row, 2, '')
                        ws.write(row, 3, '')
                        ws.write(row, 4, '')
                        ws.write(row, 5, concept.name)
                        ws.write(row, 6, employee.bim_resource_id.uom_id.name if employee.bim_resource_id else '')
                        ws.write(row, 7, round(total_hours,2))
                        ws.write(row, 8, round(total_cost/total_hours,2) if total_hours > 0 else 0)
                        ws.write(row, 9, round(total_cost,2))
                        row += 1
                    total_hours = 0
                    total_cost = 0
                    for attendance in employee_attendances.filtered_domain([('concept_id', '=', False)]):
                        total_hours += attendance.worked_hours
                        total_cost += attendance.attendance_cost
                    ws.write(row, 0, employee.bim_resource_id.default_code if employee.bim_resource_id else '')
                    ws.write(row, 1,
                             employee.bim_resource_id.display_name if employee.bim_resource_id else employee.name)
                    ws.write(row, 2, '')
                    ws.write(row, 3, '')
                    ws.write(row, 4, '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, employee.bim_resource_id.uom_id.name if employee.bim_resource_id else '')
                    ws.write(row, 7, round(total_hours, 2))
                    ws.write(row, 8, round(total_cost / total_hours, 2) if total_hours > 0 else 0)
                    ws.write(row, 9, round(total_cost, 2))
                    row += 1

            #Facturas
            if self.invoice:
                for product in invoice_products:
                    qty_location = Quants._get_available_quantity(product, location)
                    for concept in invoice_concepts:
                        budget = concept.budget_id if concept.budget_id else False
                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', concept.id)]):
                            factor = 1
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_subtotal * factor
                            product_invoiced_qty += line.quantity * factor

                        ws.write(row, 0, product.default_code or '')
                        ws.write(row, 1, product.display_name or '')
                        ws.write(row, 2, product.qty_available or 0)
                        ws.write(row, 3, qty_location)
                        ws.write(row, 4, budget.display_name if budget else '')
                        ws.write(row, 5, concept.name)
                        ws.write(row, 6, product.uom_id.name or '')
                        ws.write(row, 7, round(product_invoiced_qty, 2))
                        ws.write(row, 8, round(product_invoiced_price_total / product_invoiced_qty, 2) if product_invoiced_qty > 0 else 0)
                        ws.write(row, 9, round(product_invoiced_price_total, 2))
                        row += 1

                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        without_concept = False
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', False)]):
                            factor = 1
                            without_concept = True
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_total * factor
                            product_invoiced_qty += line.quantity * factor

                        if without_concept:
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name or '')
                            ws.write(row, 2, product.qty_available or 0)
                            ws.write(row, 3, qty_location)
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, product.uom_id.name or '')
                            ws.write(row, 7, round(product_invoiced_qty, 2))
                            ws.write(row, 8, round(product_invoiced_price_total / product_invoiced_qty,
                                                   2) if product_invoiced_qty > 0 else 0)
                            ws.write(row, 9, round(product_invoiced_price_total, 2))
                            row += 1
            #Herramientas 
            if self.tools:
                for tool in tools_lines:
                    qty_location = Quants._get_available_quantity(tool.product_id,location)
                    ws.write(row, 0, tool.product_id.default_code  or '')
                    ws.write(row, 1, tool.product_id.display_name)
                    ws.write(row, 2, tool.product_id.qty_available)
                    ws.write(row, 3, qty_location)
                    ws.write(row, 4, tool.budget_id.display_name)
                    ws.write(row, 5, tool.concept_id.name or '')
                    ws.write(row, 6, tool.product_id.uom_id.name or '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, round(tool.cost, 2))
                    ws.write(row, 9, round(tool.total, 2))
                    row += 1
        #----------------------------------#
        #-- CALCULO DE LINEAS DETALLADAS --#
        #----------------------------------#
        else:
            #Materiales (Picking)
            if self.material:
                for pick in pickings:
                    if pick.returned:
                        direction = -1
                    else:
                        direction = 1
                    for move in pick.move_ids:
                        qty_location = Quants._get_available_quantity(move.product_id,location)
                        budget = pick.bim_concept_id and pick.bim_concept_id.budget_id or False
                        departure = pick.bim_concept_id and pick.bim_concept_id or False
                        coste_real = move.product_cost
                        if workorder_active:
                            if not budget:
                                budget = move.workorder_departure_id and move.workorder_departure_id.budget_id or False
                            if not departure:
                                departure = move.workorder_departure_id and move.workorder_departure_id or False
                            if move.workorder_departure_id:
                                coste_real = move.price_unit

                        qty_budget = self.get_quantity(move.product_id,departure,pick.bim_space_id)
                        quantity_dif = qty_budget-move.product_uom_qty
                        amount_dif = (qty_budget*move.product_id.standard_price)-(move.product_uom_qty*move.product_id.standard_price)
                        supplier = ''
                        if move.supplier_id:
                            supplier = move.supplier_id.display_name
                        else:
                            if move.product_id.product_tmpl_id.bim_purchase_ids:
                                history = move.product_id.product_tmpl_id.bim_purchase_ids.filtered_domain([('project_id','=',project.id),('product_id','=',move.product_id.id)])
                                if history:
                                    supplier = history[0].supplier_id.display_name
                            elif move.product_id.seller_ids:
                                supplier = move.product_id.seller_ids[0].name.display_name
                        ws.write(row, 0, move.product_id.default_code or '')
                        ws.write(row, 1, move.product_id.display_name)
                        ws.write(row, 2, move.reference)
                        ws.write(row, 3, budget and budget.display_name or '')
                        ws.write(row, 4, departure and departure.name or '')
                        ws.write(row, 5, pick.bim_object_id and pick.bim_object_id.desc or '')
                        ws.write(row, 6, pick.bim_space_id and pick.bim_space_id.name or '')
                        ws.write(row, 7, supplier)
                        ws.write(row, 8, pick.note and pick.note or '')
                        ws.write(row, 9, datetime.strftime(move.date,'%Y-%m-%d'))
                        ws.write(row, 10, move.product_id.qty_available or 0)
                        ws.write(row, 11, qty_location or 0)
                        ws.write(row, 12, move.product_id.uom_id.name)
                        ws.write(row, 13, qty_budget)                                #Presupuesto
                        ws.write(row, 14, move.product_id.standard_price)            #Presupuesto
                        ws.write(row, 15, qty_budget*move.product_id.standard_price) #Presupuesto
                        ws.write(row, 16, move.product_uom_qty * direction)             #Ejecutado
                        ws.write(row, 17, coste_real)                       #Ejecutado
                        ws.write(row, 18, move.product_uom_qty*coste_real * direction)  #Ejecutado
                        if quantity_dif < 0:
                            ws.write(row, 19, quantity_dif,style_negative)
                        else:
                            ws.write(row, 19, quantity_dif)

                        if amount_dif < 0:
                            ws.write(row, 20, amount_dif,style_negative)
                        else:
                            ws.write(row, 20, amount_dif)
                        row += 1

            #  Mano de Obra
            if self.labor:
                for part in parts:
                    for line in part.lines_ids:
                        if line.resource_type == 'H':
                            product = line.name
                            qty_location = Quants._get_available_quantity(product,location)
                            qty_budget = self.get_quantity(product,part.concept_id,part.space_id)
                            quantity_dif = qty_budget-line.product_uom_qty
                            amount_dif = (qty_budget*product.standard_price)-line.price_subtotal
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, line.part_id.name)
                            ws.write(row, 3, part.concept_id and part.concept_id.budget_id.display_name or '')
                            ws.write(row, 4, part.concept_id and part.concept_id.name or '')
                            ws.write(row, 5, part.space_id.object_id and part.space_id.object_id.desc or '')
                            ws.write(row, 6, part.space_id and part.space_id.name or '')
                            ws.write(row, 7, part.partner_id and part.partner_id.name or line.partner_id.name)
                            ws.write(row, 8, line.description and line.description or '')
                            ws.write(row, 9, datetime.strftime(part.date,'%Y-%m-%d'))
                            ws.write(row, 10, product.qty_available or 0)
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, line.product_uom.name)
                            ws.write(row, 13, qty_budget)                        #Presupuesto
                            ws.write(row, 14, product.standard_price)            #Presupuesto
                            ws.write(row, 15, qty_budget*product.standard_price) #Presupuesto
                            ws.write(row, 16, line.product_uom_qty)    #Ejecutado
                            ws.write(row, 17, line.price_unit)         #Ejecutado
                            ws.write(row, 18, line.price_subtotal)     #Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif,style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)
                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif,style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1

                # Mano de Obra desde Orden de TRabajo (Si esta instalado bim_workorder)
                if workorder_active and workorders:
                    bwor_obj = self.env['bim.workorder.resources']
                    for word in workorders:
                        for bwoc in word.concept_ids:
                            lines_with = bwor_obj.search([('workorder_concept_id','=',bwoc.id),('workorder_id','=',bwoc.workorder_id.id)])
                            lines_out = bwor_obj.search([('workorder_id','=',bwoc.workorder_id.id),('departure_id','=',bwoc.concept_id.id)])
                            lines = lines_with + lines_out
                            lines_mo = lines.filtered(lambda x:x.qty_execute > 0)

                            for line in lines_mo:
                                product = line.resource_id.product_id if line.type == 'budget_in' else line.product_id
                                concept = line.concept_id if line.type == 'budget_in' else line.departure_id
                                qty_location = Quants._get_available_quantity(product,location)
                                qty_budget = self.get_quantity(product,concept,word.space_id)
                                quantity_dif = qty_budget-line.qty_execute
                                amount_dif = (qty_budget*product.standard_price)-line.duration_real*product.standard_price
                                ws.write(row, 0, product.default_code or '')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, word.name)
                                ws.write(row, 3, concept and concept.budget_id.display_name or '')
                                ws.write(row, 4, concept and concept.name or '')
                                ws.write(row, 5, word.object_id and word.object_id.desc or '')
                                ws.write(row, 6, word.space_id and word.space_id.name or '')
                                ws.write(row, 7, '')
                                ws.write(row, 8, line.reason or '')
                                ws.write(row, 9, datetime.strftime(line.date_start,'%Y-%m-%d'))
                                ws.write(row, 10, product.qty_available or 0)
                                ws.write(row, 11, qty_location or 0)
                                ws.write(row, 12, product.uom_id.name)
                                ws.write(row, 13, qty_budget)                        #Presupuesto
                                ws.write(row, 14, product.standard_price)            #Presupuesto
                                ws.write(row, 15, qty_budget*product.standard_price) #Presupuesto
                                ws.write(row, 16, line.duration_real)                            #Ejecutado
                                ws.write(row, 17, product.standard_price)                      #Ejecutado
                                ws.write(row, 18, line.duration_real*product.standard_price)     #Ejecutado
                                if quantity_dif < 0:
                                    ws.write(row, 19, quantity_dif,style_negative)
                                else:
                                    ws.write(row, 19, quantity_dif)
                                if amount_dif < 0:
                                    ws.write(row, 20, amount_dif,style_negative)
                                else:
                                    ws.write(row, 20, amount_dif)
                                row += 1

            # Equipos (Partes)
            if self.equipment:
                for part in parts:
                    for line in part.lines_ids:
                        if line.resource_type == 'Q':
                            product = line.name
                            qty_location = Quants._get_available_quantity(product,location)
                            qty_budget = self.get_quantity(product,part.concept_id,part.space_id)
                            quantity_dif = qty_budget-line.product_uom_qty
                            amount_dif = (qty_budget*product.standard_price)-line.price_subtotal
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, line.part_id.name)
                            ws.write(row, 3, part.concept_id and part.concept_id.budget_id.display_name or '')
                            ws.write(row, 4, part.concept_id and part.concept_id.name or '')
                            ws.write(row, 5, part.space_id.object_id and part.space_id.object_id.desc or '')
                            ws.write(row, 6, part.space_id and part.space_id.name or '')
                            ws.write(row, 7, part.partner_id and part.partner_id.name or line.partner_id.name)
                            ws.write(row, 8, line.description and line.description or '')
                            ws.write(row, 9, datetime.strftime(part.date,'%Y-%m-%d'))
                            ws.write(row, 10, product.qty_available or 0)
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, line.product_uom.name)
                            ws.write(row, 13, qty_budget)                         #Presupuesto
                            ws.write(row, 14, product.standard_price)             #Presupuesto
                            ws.write(row, 15, qty_budget*product.standard_price)  #Presupuesto
                            ws.write(row, 16, line.product_uom_qty)    #Ejecutado
                            ws.write(row, 17, line.price_unit)         #Ejecutado
                            ws.write(row, 18, line.price_subtotal)     #Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif,style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)
                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif,style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1


            # aqui va asistencia detallada
            if self.attendance:
                for attendance in attendances:
                    att_qty_budget = 0
                    hour_price = 0
                    if attendance.sudo().concept_id and attendance.sudo().employee_id.bim_resource_id:
                        att_qty_budget = self.get_budget_quantity_hours(attendance.concept_id, attendance.sudo().employee_id.bim_resource_id)
                        hour_price = attendance.sudo().employee_id.bim_resource_id.standard_price
                    quantity_dif = round(att_qty_budget - attendance.worked_hours,2)
                    amount_dif = (att_qty_budget * hour_price) - attendance.attendance_cost
                    dates = str(datetime.strftime(attendance.check_in, '%Y-%m-%d'))
                    if attendance.check_out:
                        dates += ' - ' + str(datetime.strftime(attendance.check_out, '%Y-%m-%d'))
                    ws.write(row, 0, str(attendance.id))
                    ws.write(row, 1, attendance.sudo().employee_id.bim_resource_id.display_name if attendance.sudo().employee_id.bim_resource_id else attendance.sudo().employee_id.name)
                    ws.write(row, 2, _("Attendance"))
                    ws.write(row, 3, attendance.budget_id.display_name if attendance.budget_id else '')
                    ws.write(row, 4, attendance.concept_id.name if attendance.concept_id else '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, attendance.employee_id.name)
                    ws.write(row, 8, attendance.description or '')
                    ws.write(row, 9, dates)
                    ws.write(row, 10, '')
                    ws.write(row, 11, '')
                    ws.write(row, 12, attendance.sudo().employee_id.bim_resource_id.uom_id.name if attendance.sudo().employee_id.bim_resource_id else '')
                    ws.write(row, 13, att_qty_budget)  # Presupuesto
                    ws.write(row, 14, round(hour_price,2))  # Presupuesto
                    ws.write(row, 15, round(att_qty_budget * hour_price,2))  # Presupuesto ver esto
                    ws.write(row, 16, round(attendance.worked_hours,2))  # Ejecutado
                    ws.write(row, 17, round(attendance.hour_cost,2))  # Ejecutado
                    ws.write(row, 18, round(attendance.attendance_cost,2))  # Ejecutado
                    if quantity_dif < 0:
                        ws.write(row, 19, quantity_dif, style_negative)
                    else:
                        ws.write(row, 19, quantity_dif)
                    if amount_dif < 0:
                        ws.write(row, 20, amount_dif, style_negative)
                    else:
                        ws.write(row, 20, amount_dif)
                    row += 1

            #aqui van facturas de compras y rectificativas
            if self.invoice:
                for product in invoice_products:
                    qty_location = Quants._get_available_quantity(product, location)
                    for invoice in invoice_records:
                        for concept in invoice_concepts:
                            budget = concept.budget_id if concept.budget_id else False
                            product_invoiced_price = 0
                            product_invoiced_qty = 0
                            product_invoiced_price_total = 0
                            any_product = False
                            for line in invoice_lines.filtered_domain([('product_id','=',product.id),('concept_id','=',concept.id),('move_id','=',invoice.id)]):
                                factor = 1
                                any_product = True
                                if line.move_id.move_type == 'in_refund':
                                    factor = -1
                                if self.env.company.include_vat_in_indicators:
                                    product_invoiced_price_total += line.price_total * factor
                                else:
                                    product_invoiced_price_total += line.price_subtotal * factor
                                product_invoiced_price += line.price_unit * factor
                                product_invoiced_qty += line.quantity * factor
                            if any_product:
                                qty_budget = self.get_quantity(product, concept, False)
                                quantity_dif = qty_budget - product_invoiced_qty
                                amount_dif = (qty_budget * product.standard_price) - (product_invoiced_qty * product.standard_price)

                                ws.write(row, 0, product.default_code or '')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, invoice.name)
                                ws.write(row, 3, budget and budget.display_name or '')
                                ws.write(row, 4, concept and concept.name or '')
                                ws.write(row, 5, '')
                                ws.write(row, 6, '')
                                ws.write(row, 7, invoice.partner_id.display_name)
                                ws.write(row, 8, invoice.narration or '')
                                ws.write(row, 9, str(invoice.invoice_date))
                                ws.write(row, 10, '')
                                ws.write(row, 11, qty_location or 0)
                                ws.write(row, 12, product.uom_id.name)
                                ws.write(row, 13, qty_budget)  # Presupuesto
                                ws.write(row, 14, product.standard_price)  # Presupuesto
                                ws.write(row, 15, qty_budget * product.standard_price)  # Presupuesto
                                ws.write(row, 16, product_invoiced_qty)  # Ejecutado
                                ws.write(row, 17, round(product_invoiced_price_total/product_invoiced_qty,2) if product_invoiced_qty > 0 else 0 )  # Ejecutado
                                ws.write(row, 18, product_invoiced_price_total)  # Ejecutado
                                if quantity_dif < 0:
                                    ws.write(row, 19, quantity_dif, style_negative)
                                else:
                                    ws.write(row, 19, quantity_dif)

                                if amount_dif < 0:
                                    ws.write(row, 20, amount_dif, style_negative)
                                else:
                                    ws.write(row, 20, amount_dif)
                                row += 1

                        product_invoiced_price = 0
                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        without_concept = False
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', False),('move_id','=',invoice.id)]):
                            factor = 1
                            without_concept = True
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_subtotal * factor
                            product_invoiced_price += line.price_unit * factor
                            product_invoiced_qty += line.quantity * factor
                        if without_concept:
                            qty_budget = 0#self.get_quantity(product, concept, False)
                            quantity_dif = qty_budget - product_invoiced_qty
                            amount_dif = (qty_budget * product.standard_price) - (product_invoiced_qty * product.standard_price)

                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, invoice.name)
                            ws.write(row, 3, line.budget_id.display_name if line.budget_id else '')
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, '')
                            ws.write(row, 7, invoice.partner_id.display_name)
                            ws.write(row, 8, '')
                            ws.write(row, 9, str(invoice.invoice_date))
                            ws.write(row, 10, '')
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, product.uom_id.name)
                            ws.write(row, 13, qty_budget)  # Presupuesto
                            ws.write(row, 14, product.standard_price)  # Presupuesto
                            ws.write(row, 15, qty_budget * product.standard_price)  # Presupuesto
                            ws.write(row, 16, product_invoiced_qty)  # Ejecutado
                            ws.write(row, 17, round(product_invoiced_price_total / product_invoiced_qty,
                                                    2) if product_invoiced_qty > 0 else 0)  # Ejecutado
                            ws.write(row, 18, product_invoiced_price_total)  # Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif, style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)

                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif, style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1
            #Herramientas 
            if self.tools:
                for tool in tools_lines:
                    location = self.project_id.stock_location_id
                    qty_tool = tool.hours
                    qty_budget = self.get_quantity(tool.product_id, tool.concept_id, False)
                    quantity_dif = qty_budget - qty_tool
                    amount_dif = (qty_budget * tool.product_id.standard_price) - (qty_tool * tool.product_id.standard_price)
                    qty_location = Quants._get_available_quantity(tool.product_id,location)
                    ws.write(row, 0, tool.product_id.default_code  or '')
                    ws.write(row, 1, tool.product_id.display_name)
                    ws.write(row, 2, tool.product_id.display_name)
                    ws.write(row, 3, tool.budget_id.display_name if tool.budget_id else '')
                    ws.write(row, 4, tool.concept_id.name or '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, '')
                    ws.write(row, 10, '')
                    ws.write(row, 11, qty_location or 0)
                    ws.write(row, 12, tool.product_id.uom_id.name)
                    ws.write(row, 13, '')
                    ws.write(row, 14, '')
                    ws.write(row, 15, '')
                    ws.write(row, 16, qty_tool)# Ejecutado
                    ws.write(row, 17, round(tool.cost, 2))# Ejecutado
                    ws.write(row, 18, round(tool.total, 2))# Ejecutado
                    if quantity_dif < 0:
                        ws.write(row, 19, quantity_dif, style_negative)
                    else:
                        ws.write(row, 19, quantity_dif)

                    if amount_dif < 0:
                        ws.write(row, 20, amount_dif, style_negative)
                    else:
                        ws.write(row, 20, amount_dif)
                    row += 1
                    
            if self.resource_all:
                for balance in self.project_id.opening_balance_ids:
                    ws.write(row, 0, balance.name)
                    ws.write(row, 1, _("Opening Balance"))
                    ws.write(row, 2, '')
                    ws.write(row, 3, balance.budget_id.display_name if balance.budget_id else '')
                    ws.write(row, 4, balance.concept_id.name if balance.concept_id else '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, '')
                    ws.write(row, 10, '')
                    ws.write(row, 11, '')
                    ws.write(row, 12, '')
                    ws.write(row, 13, '')  # Presupuesto
                    ws.write(row, 14, '')  # Presupuesto
                    ws.write(row, 15, '')  # Presupuesto
                    ws.write(row, 16, '')  # Ejecutado
                    ws.write(row, 17, '')
                    ws.write(row, 18, balance.amount)
                    ws.write(row, 19, '')
                    ws.write(row, 20, '')
                    row += 1
                    #.Exportacion
        fp = io.BytesIO()
        wb.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        data_b64 = base64.encodebytes(data)
        attach = self.env['ir.attachment'].create({
            'name': '%s.%s'%(project.name,self.doc_type),
            'type': 'binary',
            'datas': data_b64  })
        url = '/web/content/?model=ir.attachment'
        url += '&id={}&field=datas&download=true&filename={}'.format(attach.id,attach.name)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'self'}

    ##############################################################################################################
    
    def print_xls_from_budget(self,budgets):
        _logger.info("::::::BUDGETS:::::: %s" %budgets)
        base_domain = [('bim_budget_id','in',budgets.ids),('include_for_bim','=',True),('state','=','done')]
        part_domain = [('budget_id','in',budgets.ids),('state','=','validated')]
        attendance_domain = [('budget_id','in',budgets.ids),('check_out','!=',False)]
        tools_domain = [('budget_id','in',budgets.ids)]
        invoice_domain = [('display_type','=','product'),
            ('move_id.move_type','in',['in_invoice','in_refund']),
            ('budget_id','in',budgets.ids),('move_id.state','=','posted'),('move_id.include_for_bim','=',True)]

        if self.display_type == 'summary':
            header = ["Código","Nombre","Inventario General","Inventario Ubicación","Presupuesto","Partida","Uom","Salidas","Coste","Importe"]
        elif self.display_type == 'range':
            base_domain.append(('date','>=',self.date_beg))
            base_domain.append(('date','<=',self.date_end))
            invoice_domain.append(('move_id.invoice_date','<=',self.date_end))
            invoice_domain.append(('move_id.invoice_date','>=',self.date_beg))
            part_domain.append(('date','>=',self.date_beg))
            part_domain.append(('date','<=',self.date_end))
            attendance_domain.append(('check_in','>=',self.date_beg))
            attendance_domain.append(('check_out','<=',self.date_end))
            tools_domain.append(('date_start','>=',self.date_beg))
            tools_domain.append(('date_end','<=',self.date_end))
            header = ["Código","Nombre","Inventario General","Inventario Ubicación","Presupuesto","Partida","Uom","Salidas","Coste","Importe"]
        else:
            header = ["Código","Nombre","Movimiento/Parte","Presupuesto","Partida","Objeto de Obra","Espacio","Proveedor","Descripción","Fecha","Inventario General","Inventario Ubicación","Uom","Cantidad","Coste","Importe","Cantidad","Coste","Importe","Cantidad","Importe"]

        # Verificamos si esta activo Orden de Trabajo (COMENTADO TEMPORALMENTE)
        #workorders = self.env['bim.workorder'].search([('project_id','in',project.ids)])

        # Buscamos los picking de la Obra
        picking_obj = self.env['stock.picking']
        outgoing_domain = base_domain + [('picking_type_code','!=','incoming'),('returned','=',False)]
        pickings = picking_obj.search(outgoing_domain)
        incoming_domain = base_domain + [('picking_type_code','=','incoming'),('returned','=',True)]
        pickings += picking_obj.search(incoming_domain)
        _logger.info("::::::PICKS:::::: %s" %pickings)


        #Buscamos las partidas
        departs = pickings.mapped('bim_concept_id')
        _logger.info("::::::PARTIDAS:::::: %s" %departs)

        #Buscamos las Partes de la Obra
        parts = self.env['bim.part'].search(part_domain)
        _logger.info("::::::PARTES:::::: %s" %parts)
        dep_parts = parts.mapped('concept_id')

        # Buscamos asistencia de la Obra
        attendances = self.env['hr.attendance'].search(attendance_domain)
        employees = attendances.mapped('employee_id')
        _logger.info("::::::ASIST:::::: %s" %employees)

        # Buscamos las herramientas
        tools_lines = self.env['bim.tool.use'].search(tools_domain)
        tools_product = tools_lines.mapped('product_id')
        _logger.info("::::::TOOLS:::::: %s" %tools_lines)

        # Buscamos las Facturas de Compra
        invoice_lines = self.env['account.move.line'].search(invoice_domain)
        _logger.info("::::::INVOICE LINES:::::: %s" %invoice_lines)
        invoice_products = invoice_lines.mapped('product_id')
        invoice_concepts = invoice_lines.mapped('concept_id')
        invoice_records = invoice_lines.mapped('move_id')

        # Datos Para excel
        wb = Workbook(encoding='utf-8')
        ws = wb.add_sheet(_('Book'))
        Quants = self.env['stock.quant']
        style_title = easyxf('font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center')
        style_negative = easyxf('font: color red;')

        row = 0
        index = 0
        if self.display_type == 'detailed':
            ws.write_merge(row,row,13,15, _("BUDGET"),style_title)
            ws.write_merge(row,row,16,18, _("REAL EXECUTED"),style_title)
            ws.write_merge(row,row,19,20, _("DIFFERENCE"),style_title)
            row = row + 1

        for head in header:
            ws.write(row, index, head, style_title)
            index = index + 1

        row = row + 1

        # CALCULO DE LINEAS RESUMIDAS y RANGO
        if self.display_type in ['range','summary']:
            # (Partes)
            for concept in dep_parts:
                location = concept.budget_id.project_id.stock_location_id
                # Mano de Obra
                if self.labor:
                    product_ids = []
                    for part in parts.filtered(lambda pt: pt.concept_id.id == concept.id):
                        _logger.info("::::::part:::::: %s" %part.name)
                        products = part.lines_ids.mapped('name')
                        for product in products.filtered(lambda p: p.resource_type == 'H'):
                            _logger.info("::::::product:::::: %s" %product.name)
                            if not product.id in product_ids:
                                qty_location = Quants._get_available_quantity(product,location)
                                part_outs = self.get_part_out(product,'H',concept)
                                ws.write(row, 0, product.default_code if product.default_code else '-')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, part_outs)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, part_outs*product.standard_price)
                                product_ids.append(product.id)
                                row += 1
                # Equipos
                if self.equipment:
                    product_ids = []
                    for part in parts.filtered(lambda pt: pt.concept_id.id == concept.id):
                        products = part.lines_ids.mapped('name')
                        for product in products.filtered(lambda p: p.resource_type == 'Q'):
                            if not product.id in product_ids:
                                qty_location = Quants._get_available_quantity(product,location)
                                part_outs = self.get_part_out(product,'Q',concept)
                                ws.write(row, 0, product.default_code or '-')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, part_outs)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, part_outs*product.standard_price)
                                product_ids.append(product.id)
                                row += 1

            if self.resource_all:
                balances = self.env['bim.opening.balance'].search([('budget_id','in',budgets.ids)])
                for balance in balances:
                    ws.write(row, 0, balance.name)
                    ws.write(row, 1, _("Opening Balance"))
                    ws.write(row, 2, '')
                    ws.write(row, 3, '')
                    ws.write(row, 4, balance.budget_id.display_name)
                    ws.write(row, 5, balance.concept_id.name if balance.concept_id else '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, balance.amount)
                    row += 1

            # Materiales (Picking)
            if self.material:
                for concept in departs:
                    product_ids = []
                    for pick in pickings.filtered(lambda sp: sp.bim_concept_id.id == concept.id):
                        products = pick.move_ids.mapped('product_id')
                        for product in products:
                            if not product.id in product_ids:
                                quantity_done = self.get_stock_out(product, location, concept)
                                qty_location = Quants._get_available_quantity(product,location)
                                ws.write(row, 0, product.default_code or '')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, product.qty_available or 0)
                                ws.write(row, 3, qty_location or 0)
                                ws.write(row, 4, concept.budget_id.display_name)
                                ws.write(row, 5, concept.name)
                                ws.write(row, 6, product.uom_id.name)
                                ws.write(row, 7, quantity_done)
                                ws.write(row, 8, product.standard_price)
                                ws.write(row, 9, quantity_done * product.standard_price)
                                product_ids.append(product.id)
                                row += 1
                product_ids = []
                for pick in pickings.filtered(lambda sp: not sp.bim_concept_id):
                    for product in pick.move_ids.mapped('product_id'):
                        if not product.id in product_ids:
                            qty_location = Quants._get_available_quantity(product,location)
                            quantity_done = self.get_stock_out(product, location, concept)
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, product.qty_available or 0)
                            ws.write(row, 3, qty_location or 0)
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, product.uom_id.name)
                            ws.write(row, 7, quantity_done)
                            ws.write(row, 8, product.standard_price)
                            ws.write(row, 9, quantity_done * product.standard_price)
                            product_ids.append(product.id)
                            row += 1
            # asistencia 
            if self.attendance:
                for employee in employees:
                    employee_attendances = attendances.filtered_domain([('employee_id','=',employee.id)])
                    concepts = employee_attendances.mapped('concept_id')
                    for concept in concepts:
                        total_hours = 0
                        total_cost = 0
                        for attendance in employee_attendances.filtered_domain([('concept_id','=',concept.id)]):
                            total_hours += attendance.worked_hours
                            total_cost += attendance.attendance_cost
                        ws.write(row, 0, employee.bim_resource_id.default_code if employee.bim_resource_id else '')
                        ws.write(row, 1, employee.bim_resource_id.display_name if employee.bim_resource_id else employee.name )
                        ws.write(row, 2, '')
                        ws.write(row, 3, '')
                        ws.write(row, 4, '')
                        ws.write(row, 5, concept.name)
                        ws.write(row, 6, employee.bim_resource_id.uom_id.name if employee.bim_resource_id else '')
                        ws.write(row, 7, round(total_hours,2))
                        ws.write(row, 8, round(total_cost/total_hours,2) if total_hours > 0 else 0)
                        ws.write(row, 9, round(total_cost,2))
                        row += 1
                    total_hours = 0
                    total_cost = 0
                    for attendance in employee_attendances.filtered_domain([('concept_id', '=', False)]):
                        total_hours += attendance.worked_hours
                        total_cost += attendance.attendance_cost
                    ws.write(row, 0, employee.bim_resource_id.default_code if employee.bim_resource_id else '')
                    ws.write(row, 1,
                             employee.bim_resource_id.display_name if employee.bim_resource_id else employee.name)
                    ws.write(row, 2, '')
                    ws.write(row, 3, '')
                    ws.write(row, 4, '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, employee.bim_resource_id.uom_id.name if employee.bim_resource_id else '')
                    ws.write(row, 7, round(total_hours, 2))
                    ws.write(row, 8, round(total_cost / total_hours, 2) if total_hours > 0 else 0)
                    ws.write(row, 9, round(total_cost, 2))
                    row += 1

            #Facturas
            if self.invoice:
                for product in invoice_products:
                    for concept in invoice_concepts:
                        budget = concept.budget_id if concept.budget_id else False
                        location = budget.project_id.stock_location_id
                        qty_location = Quants._get_available_quantity(product, location)
                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', concept.id)]):
                            factor = 1
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_subtotal * factor
                            product_invoiced_qty += line.quantity * factor

                        ws.write(row, 0, product.default_code or '')
                        ws.write(row, 1, product.display_name or '')
                        ws.write(row, 2, product.qty_available or 0)
                        ws.write(row, 3, qty_location)
                        ws.write(row, 4, budget.display_name if budget else '')
                        ws.write(row, 5, concept.name)
                        ws.write(row, 6, product.uom_id.name or '')
                        ws.write(row, 7, round(product_invoiced_qty, 2))
                        ws.write(row, 8, round(product_invoiced_price_total / product_invoiced_qty, 2) if product_invoiced_qty > 0 else 0)
                        ws.write(row, 9, round(product_invoiced_price_total, 2))
                        row += 1

                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        without_concept = False
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', False)]):
                            factor = 1
                            without_concept = True
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_total * factor
                            product_invoiced_qty += line.quantity * factor

                        if without_concept:
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name or '')
                            ws.write(row, 2, product.qty_available or 0)
                            ws.write(row, 3, qty_location)
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, product.uom_id.name or '')
                            ws.write(row, 7, round(product_invoiced_qty, 2))
                            ws.write(row, 8, round(product_invoiced_price_total / product_invoiced_qty,2) if product_invoiced_qty > 0 else 0)
                            ws.write(row, 9, round(product_invoiced_price_total, 2))
                            row += 1

            #Herramientas 
            if self.tools:
                for tool in tools_lines:
                    qty_location = Quants._get_available_quantity(tool.product_id,location)
                    ws.write(row, 0, tool.product_id.default_code  or '')
                    ws.write(row, 1, tool.product_id.display_name)
                    ws.write(row, 2, tool.product_id.qty_available)
                    ws.write(row, 3, qty_location)
                    ws.write(row, 4, tool.budget_id.display_name)
                    ws.write(row, 5, tool.concept_id.name or '')
                    ws.write(row, 6, tool.product_id.uom_id.name or '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, round(tool.cost, 2))
                    ws.write(row, 9, round(tool.total, 2))
                    row += 1

                    
        # CALCULO DE LINEAS DETALLADAS
        else:
            #Materiales (Picking)
            if self.material:
                for pick in pickings:
                    if pick.returned:
                        direction = -1
                    else:
                        direction = 1

                    location = pick.bim_budget_id.project_id.stock_location_id
                    for move in pick.move_ids:
                        qty_location = Quants._get_available_quantity(move.product_id,location)
                        departure = pick.bim_concept_id and pick.bim_concept_id or False
                        coste_real = move.product_cost
                        #if workorders:
                        #    if not budget:
                        #        budget = move.workorder_departure_id and move.workorder_departure_id.budget_id or False
                        #    if not departure:
                        #        departure = move.workorder_departure_id and move.workorder_departure_id or False
                        #    if move.workorder_departure_id:
                        #        coste_real = move.price_unit

                        qty_budget = self.get_quantity(move.product_id,departure,pick.bim_space_id)
                        quantity_dif = qty_budget-move.product_uom_qty
                        amount_dif = (qty_budget*move.product_id.standard_price)-(move.product_uom_qty*move.product_id.standard_price)
                        supplier = ''
                        if move.supplier_id:
                            supplier = move.supplier_id.display_name
                        else:
                            if move.product_id.seller_ids:
                                supplier = move.product_id.seller_ids[0].name.display_name
                        ws.write(row, 0, move.product_id.default_code or '')
                        ws.write(row, 1, move.product_id.display_name)
                        ws.write(row, 2, move.reference)
                        ws.write(row, 3, pick.bim_budget_id and pick.bim_budget_id.display_name or '')
                        ws.write(row, 4, departure and departure.name or '')
                        ws.write(row, 5, pick.bim_object_id and pick.bim_object_id.desc or '')
                        ws.write(row, 6, pick.bim_space_id and pick.bim_space_id.name or '')
                        ws.write(row, 7, supplier)
                        ws.write(row, 8, pick.note and pick.note or '')
                        ws.write(row, 9, datetime.strftime(move.date,'%Y-%m-%d'))
                        ws.write(row, 10, move.product_id.qty_available or 0)
                        ws.write(row, 11, qty_location or 0)
                        ws.write(row, 12, move.product_id.uom_id.name)
                        ws.write(row, 13, qty_budget)                                #Presupuesto
                        ws.write(row, 14, move.product_id.standard_price)            #Presupuesto
                        ws.write(row, 15, qty_budget*move.product_id.standard_price) #Presupuesto
                        ws.write(row, 16, move.product_uom_qty * direction)             #Ejecutado
                        ws.write(row, 17, coste_real)                       #Ejecutado
                        ws.write(row, 18, move.product_uom_qty*coste_real * direction)  #Ejecutado
                        if quantity_dif < 0:
                            ws.write(row, 19, quantity_dif,style_negative)
                        else:
                            ws.write(row, 19, quantity_dif)

                        if amount_dif < 0:
                            ws.write(row, 20, amount_dif,style_negative)
                        else:
                            ws.write(row, 20, amount_dif)
                        row += 1

            #  Mano de Obra
            if self.labor:
                for part in parts:
                    location = part.budget_id.project_id.stock_location_id
                    for line in part.lines_ids:
                        if line.resource_type == 'H':
                            product = line.name
                            qty_location = Quants._get_available_quantity(product,location)
                            qty_budget = self.get_quantity(product,part.concept_id,part.space_id)
                            quantity_dif = qty_budget-line.product_uom_qty
                            amount_dif = (qty_budget*product.standard_price)-line.price_subtotal
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, line.part_id.name)
                            ws.write(row, 3, part.concept_id and part.concept_id.budget_id.display_name or '')
                            ws.write(row, 4, part.concept_id and part.concept_id.name or '')
                            ws.write(row, 5, part.space_id.object_id and part.space_id.object_id.desc or '')
                            ws.write(row, 6, part.space_id and part.space_id.name or '')
                            ws.write(row, 7, part.partner_id and part.partner_id.name or line.partner_id.name)
                            ws.write(row, 8, line.description and line.description or '')
                            ws.write(row, 9, datetime.strftime(part.date,'%Y-%m-%d'))
                            ws.write(row, 10, product.qty_available or 0)
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, line.product_uom.name)
                            ws.write(row, 13, qty_budget)                        #Presupuesto
                            ws.write(row, 14, product.standard_price)            #Presupuesto
                            ws.write(row, 15, qty_budget*product.standard_price) #Presupuesto
                            ws.write(row, 16, line.product_uom_qty)    #Ejecutado
                            ws.write(row, 17, line.price_unit)         #Ejecutado
                            ws.write(row, 18, line.price_subtotal)     #Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif,style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)
                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif,style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1

                # Mano de Obra desde Orden de TRabajo (Si esta instalado bim_workorder)
                #if workorders:
                #    bwor_obj = self.env['bim.workorder.resources']
                #    for word in workorders:
                #        for bwoc in word.concept_ids:
                #            lines_with = bwor_obj.search([('workorder_concept_id','=',bwoc.id),('workorder_id','=',bwoc.workorder_id.id)])
                #            lines_out = bwor_obj.search([('workorder_id','=',bwoc.workorder_id.id),('departure_id','=',bwoc.concept_id.id)])
                #            lines = lines_with + lines_out
                #            lines_mo = lines.filtered(lambda x:x.qty_execute > 0)
                #            location = bwoc.concept_id.budget_id.project_id.stock_location_id
                #
                #            for line in lines_mo:
                #                product = line.resource_id.product_id if line.type == 'budget_in' else line.product_id
                #                concept = line.concept_id if line.type == 'budget_in' else line.departure_id
                #                qty_location = Quants._get_available_quantity(product,location)
                #                qty_budget = self.get_quantity(product,concept,word.space_id)
                #                quantity_dif = qty_budget-line.qty_execute
                #                amount_dif = (qty_budget*product.standard_price)-line.duration_real*product.standard_price
                #                ws.write(row, 0, product.default_code or '')
                #                ws.write(row, 1, product.display_name)
                #                ws.write(row, 2, word.name)
                #                ws.write(row, 3, concept and concept.budget_id.display_name or '')
                #                ws.write(row, 4, concept and concept.name or '')
                #                ws.write(row, 5, word.object_id and word.object_id.desc or '')
                #                ws.write(row, 6, word.space_id and word.space_id.name or '')
                #                ws.write(row, 7, '')
                #                ws.write(row, 8, line.reason or '')
                #                ws.write(row, 9, datetime.strftime(line.date_start,'%Y-%m-%d'))
                #                ws.write(row, 10, product.qty_available or 0)
                #                ws.write(row, 11, qty_location or 0)
                #                ws.write(row, 12, product.uom_id.name)
                #                ws.write(row, 13, qty_budget)                        #Presupuesto
                #                ws.write(row, 14, product.standard_price)            #Presupuesto
                #                ws.write(row, 15, qty_budget*product.standard_price) #Presupuesto
                #                ws.write(row, 16, line.duration_real)                            #Ejecutado
                #                ws.write(row, 17, product.standard_price)                      #Ejecutado
                #                ws.write(row, 18, line.duration_real*product.standard_price)     #Ejecutado
                #                if quantity_dif < 0:
                #                    ws.write(row, 19, quantity_dif,style_negative)
                #                else:
                #                    ws.write(row, 19, quantity_dif)
                #                if amount_dif < 0:
                #                    ws.write(row, 20, amount_dif,style_negative)
                #                else:
                #                    ws.write(row, 20, amount_dif)
                #                row += 1

            # Equipos (Partes)
            if self.equipment:
                for part in parts:
                    location = part.budget_id.project_id.stock_location_id
                    for line in part.lines_ids:
                        if line.resource_type == 'Q':
                            product = line.name
                            qty_location = Quants._get_available_quantity(product,location)
                            qty_budget = self.get_quantity(product,part.concept_id,part.space_id)
                            quantity_dif = qty_budget-line.product_uom_qty
                            amount_dif = (qty_budget*product.standard_price)-line.price_subtotal
                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, line.part_id.name)
                            ws.write(row, 3, part.concept_id and part.concept_id.budget_id.display_name or '')
                            ws.write(row, 4, part.concept_id and part.concept_id.name or '')
                            ws.write(row, 5, part.space_id.object_id and part.space_id.object_id.desc or '')
                            ws.write(row, 6, part.space_id and part.space_id.name or '')
                            ws.write(row, 7, part.partner_id and part.partner_id.name or line.partner_id.name)
                            ws.write(row, 8, line.description and line.description or '')
                            ws.write(row, 9, datetime.strftime(part.date,'%Y-%m-%d'))
                            ws.write(row, 10, product.qty_available or 0)
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, line.product_uom.name)
                            ws.write(row, 13, qty_budget)                         #Presupuesto
                            ws.write(row, 14, product.standard_price)             #Presupuesto
                            ws.write(row, 15, qty_budget*product.standard_price)  #Presupuesto
                            ws.write(row, 16, line.product_uom_qty)    #Ejecutado
                            ws.write(row, 17, line.price_unit)         #Ejecutado
                            ws.write(row, 18, line.price_subtotal)     #Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif,style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)
                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif,style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1


            # aqui va asistencia detallada
            if self.attendance:
                for attendance in attendances:
                    att_qty_budget = 0
                    hour_price = 0
                    if attendance.sudo().concept_id and attendance.sudo().employee_id.bim_resource_id:
                        att_qty_budget = self.get_budget_quantity_hours(attendance.concept_id, attendance.sudo().employee_id.bim_resource_id)
                        hour_price = attendance.sudo().employee_id.bim_resource_id.standard_price
                    quantity_dif = round(att_qty_budget - attendance.worked_hours,2)
                    amount_dif = (att_qty_budget * hour_price) - attendance.attendance_cost
                    dates = str(datetime.strftime(attendance.check_in, '%Y-%m-%d'))
                    if attendance.check_out:
                        dates += ' - ' + str(datetime.strftime(attendance.check_out, '%Y-%m-%d'))
                    ws.write(row, 0, str(attendance.id))
                    ws.write(row, 1, attendance.sudo().employee_id.bim_resource_id.display_name if attendance.sudo().employee_id.bim_resource_id else attendance.sudo().employee_id.name)
                    ws.write(row, 2, _("Attendance"))
                    ws.write(row, 3, attendance.budget_id.display_name if attendance.budget_id else '')
                    ws.write(row, 4, attendance.concept_id.name if attendance.concept_id else '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, attendance.employee_id.name)
                    ws.write(row, 8, attendance.description or '')
                    ws.write(row, 9, dates)
                    ws.write(row, 10, '')
                    ws.write(row, 11, '')
                    ws.write(row, 12, attendance.sudo().employee_id.bim_resource_id.uom_id.name if attendance.sudo().employee_id.bim_resource_id else '')
                    ws.write(row, 13, att_qty_budget)  # Presupuesto
                    ws.write(row, 14, round(hour_price,2))  # Presupuesto
                    ws.write(row, 15, round(att_qty_budget * hour_price,2))  # Presupuesto ver esto
                    ws.write(row, 16, round(attendance.worked_hours,2))  # Ejecutado
                    ws.write(row, 17, round(attendance.hour_cost,2))  # Ejecutado
                    ws.write(row, 18, round(attendance.attendance_cost,2))  # Ejecutado
                    if quantity_dif < 0:
                        ws.write(row, 19, quantity_dif, style_negative)
                    else:
                        ws.write(row, 19, quantity_dif)
                    if amount_dif < 0:
                        ws.write(row, 20, amount_dif, style_negative)
                    else:
                        ws.write(row, 20, amount_dif)
                    row += 1

            #aqui van facturas de compras y rectificativas
            if self.invoice:
                for product in invoice_products:
                    for invoice in invoice_records:
                        for concept in invoice_concepts:
                            location = concept.budget_id.project_id.stock_location_id
                            qty_location = Quants._get_available_quantity(product, location)
                            budget = concept.budget_id if concept.budget_id else False
                            product_invoiced_price = 0
                            product_invoiced_qty = 0
                            product_invoiced_price_total = 0
                            any_product = False
                            for line in invoice_lines.filtered_domain([('product_id','=',product.id),('concept_id','=',concept.id),('move_id','=',invoice.id)]):
                                factor = 1
                                any_product = True
                                if line.move_id.move_type == 'in_refund':
                                    factor = -1
                                if self.env.company.include_vat_in_indicators:
                                    product_invoiced_price_total += line.price_total * factor
                                else:
                                    product_invoiced_price_total += line.price_subtotal * factor
                                product_invoiced_price += line.price_unit * factor
                                product_invoiced_qty += line.quantity * factor
                            if any_product:
                                qty_budget = self.get_quantity(product, concept, False)
                                quantity_dif = qty_budget - product_invoiced_qty
                                amount_dif = (qty_budget * product.standard_price) - (product_invoiced_qty * product.standard_price)

                                ws.write(row, 0, product.default_code or '')
                                ws.write(row, 1, product.display_name)
                                ws.write(row, 2, invoice.name)
                                ws.write(row, 3, budget and budget.display_name or '')
                                ws.write(row, 4, concept and concept.name or '')
                                ws.write(row, 5, '')
                                ws.write(row, 6, '')
                                ws.write(row, 7, invoice.partner_id.display_name)
                                ws.write(row, 8, invoice.narration or '')
                                ws.write(row, 9, str(invoice.invoice_date))
                                ws.write(row, 10, '')
                                ws.write(row, 11, qty_location or 0)
                                ws.write(row, 12, product.uom_id.name)
                                ws.write(row, 13, qty_budget)  # Presupuesto
                                ws.write(row, 14, product.standard_price)  # Presupuesto
                                ws.write(row, 15, qty_budget * product.standard_price)  # Presupuesto
                                ws.write(row, 16, product_invoiced_qty)  # Ejecutado
                                ws.write(row, 17, round(product_invoiced_price_total/product_invoiced_qty,2) if product_invoiced_qty > 0 else 0 )  # Ejecutado
                                ws.write(row, 18, product_invoiced_price_total)  # Ejecutado
                                if quantity_dif < 0:
                                    ws.write(row, 19, quantity_dif, style_negative)
                                else:
                                    ws.write(row, 19, quantity_dif)

                                if amount_dif < 0:
                                    ws.write(row, 20, amount_dif, style_negative)
                                else:
                                    ws.write(row, 20, amount_dif)
                                row += 1

                        product_invoiced_price = 0
                        product_invoiced_qty = 0
                        product_invoiced_price_total = 0
                        without_concept = False
                        for line in invoice_lines.filtered_domain(
                                [('product_id', '=', product.id), ('concept_id', '=', False),('move_id','=',invoice.id)]):
                            factor = 1
                            without_concept = True
                            if line.move_id.move_type == 'in_refund':
                                factor = -1
                            if self.env.company.include_vat_in_indicators:
                                product_invoiced_price_total += line.price_total * factor
                            else:
                                product_invoiced_price_total += line.price_subtotal * factor
                            product_invoiced_price += line.price_unit * factor
                            product_invoiced_qty += line.quantity * factor
                        if without_concept:
                            qty_budget = 0#self.get_quantity(product, concept, False)
                            quantity_dif = qty_budget - product_invoiced_qty
                            amount_dif = (qty_budget * product.standard_price) - (product_invoiced_qty * product.standard_price)
                            location = line.budget_id.project_id.stock_location_id
                            qty_location = Quants._get_available_quantity(product, location)

                            ws.write(row, 0, product.default_code or '')
                            ws.write(row, 1, product.display_name)
                            ws.write(row, 2, invoice.name)
                            ws.write(row, 3, line.budget_id.display_name if line.budget_id else '')
                            ws.write(row, 4, '')
                            ws.write(row, 5, '')
                            ws.write(row, 6, '')
                            ws.write(row, 7, invoice.partner_id.display_name)
                            ws.write(row, 8, '')
                            ws.write(row, 9, str(invoice.invoice_date))
                            ws.write(row, 10, '')
                            ws.write(row, 11, qty_location or 0)
                            ws.write(row, 12, product.uom_id.name)
                            ws.write(row, 13, qty_budget)  # Presupuesto
                            ws.write(row, 14, product.standard_price)  # Presupuesto
                            ws.write(row, 15, qty_budget * product.standard_price)  # Presupuesto
                            ws.write(row, 16, product_invoiced_qty)  # Ejecutado
                            ws.write(row, 17, round(product_invoiced_price_total / product_invoiced_qty,2) if product_invoiced_qty > 0 else 0)  # Ejecutado
                            ws.write(row, 18, product_invoiced_price_total)  # Ejecutado
                            if quantity_dif < 0:
                                ws.write(row, 19, quantity_dif, style_negative)
                            else:
                                ws.write(row, 19, quantity_dif)

                            if amount_dif < 0:
                                ws.write(row, 20, amount_dif, style_negative)
                            else:
                                ws.write(row, 20, amount_dif)
                            row += 1
            #Herramientas 
            if self.tools:
                for tool in tools_lines:
                    location = self.project_id.stock_location_id
                    qty_tool = tool.hours
                    qty_budget = self.get_quantity(tool.product_id, tool.concept_id, False)
                    quantity_dif = qty_budget - qty_tool
                    amount_dif = (qty_budget * tool.product_id.standard_price) - (qty_tool * tool.product_id.standard_price)
                    qty_location = Quants._get_available_quantity(tool.product_id,location)
                    ws.write(row, 0, tool.product_id.default_code  or '')
                    ws.write(row, 1, tool.product_id.display_name)
                    ws.write(row, 2, tool.product_id.display_name)
                    ws.write(row, 3, tool.budget_id.display_name if tool.budget_id else '')
                    ws.write(row, 4, tool.concept_id.name or '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, '')
                    ws.write(row, 10, '')
                    ws.write(row, 11, qty_location or 0)
                    ws.write(row, 12, tool.product_id.uom_id.name)
                    ws.write(row, 13, '')
                    ws.write(row, 14, '')
                    ws.write(row, 15, '')
                    ws.write(row, 16, qty_tool)# Ejecutado
                    ws.write(row, 17, round(tool.cost, 2))# Ejecutado
                    ws.write(row, 18, round(tool.total, 2))# Ejecutado
                    if quantity_dif < 0:
                        ws.write(row, 19, quantity_dif, style_negative)
                    else:
                        ws.write(row, 19, quantity_dif)

                    if amount_dif < 0:
                        ws.write(row, 20, amount_dif, style_negative)
                    else:
                        ws.write(row, 20, amount_dif)
                    row += 1

            if self.resource_all:
                balances = self.env['bim.opening.balance'].search([('budget_id','in',budgets.ids)])
                for balance in balances:
                    ws.write(row, 0, balance.name)
                    ws.write(row, 1, _("Opening Balance"))
                    ws.write(row, 2, '')
                    ws.write(row, 3, balance.budget_id.display_name if balance.budget_id else '')
                    ws.write(row, 4, balance.concept_id.name if balance.concept_id else '')
                    ws.write(row, 5, '')
                    ws.write(row, 6, '')
                    ws.write(row, 7, '')
                    ws.write(row, 8, '')
                    ws.write(row, 9, '')
                    ws.write(row, 10, '')
                    ws.write(row, 11, '')
                    ws.write(row, 12, '')
                    ws.write(row, 13, '')  # Presupuesto
                    ws.write(row, 14, '')  # Presupuesto
                    ws.write(row, 15, '')  # Presupuesto
                    ws.write(row, 16, '')  # Ejecutado
                    ws.write(row, 17, '')
                    ws.write(row, 18, balance.amount)
                    ws.write(row, 19, '')
                    ws.write(row, 20, '')
                    row += 1
                    #.Exportacion
        fp = io.BytesIO()
        wb.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        data_b64 = base64.encodebytes(data)
        attach = self.env['ir.attachment'].create({
            'name': 'Salida_presupuestos.%s'%self.doc_type,
            'type': 'binary',
            'datas': data_b64  })
        url = '/web/content/?model=ir.attachment'
        url += '&id={}&field=datas&download=true&filename={}'.format(attach.id,attach.name)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'self'}
