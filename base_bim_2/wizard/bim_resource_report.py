# coding: utf-8
import base64
import logging
import xlwt
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from io import BytesIO
from datetime import datetime, date, timedelta
_logger = logging.getLogger(__name__)

class BimResourceReportWizard(models.TransientModel):
    _name = 'bim.resource.report.wizard'
    _description = 'Buget Resource Report'

    def _default_budget(self):
        return self.env['bim.budget'].browse(self._context.get('active_id'))


    material = fields.Boolean(string="Materials",default=True)
    equipment = fields.Boolean(string="Equipment",default=True)
    labor = fields.Boolean(string="Labor",default=True)
    aux = fields.Boolean(string="Other",default=True)
    fsubcontract = fields.Boolean(string="Subcontract",default=True)

    budget_id = fields.Many2one('bim.budget', "Budget", required=True, default=_default_budget)
    resource_all = fields.Boolean(default=True,string="All")
    filter_categ = fields.Boolean(string="Category Filter")

    type_unit = fields.Selection([
                                  ('day','Días'),
                                  ('hour','Horas'),
                                  ],string="Tipo Unidad", required=True, default='day')

    show_footer = fields.Boolean(string="Mostrar Totales", default=True)
    concept_ids = fields.Many2many('bim.concepts', string="Partidas")

    group_stage = fields.Selection([('not','No'),('select','Select'),('all','All')],string="Group Stage", required=True, default='not')
    subcontract = fields.Selection([('not',''),('separe','Split Subcontracts'),('subcon','Only subcontracts')],string="Subcontratos", default='not')
    category_id = fields.Many2one('product.category', "Category")
    count_stages = fields.Integer('Stages Count', compute='_compute_stages')
    stage_ids = fields.Many2many(
        string= "Etapas",
        comodel_name='bim.budget.stage',
        relation='budget_stage_rel',
        column1='budget_id',
        column2='stage_id',
    )


    @api.depends('budget_id')
    def _compute_stages(self):
        for record in self:
            record.count_stages = len(record.budget_id.stage_ids)

    def recursive_amount(self, resource, parent, amount=None):
        amount = amount is None and resource.balance or amount
        if parent.type == 'departure':
            amount_partial = amount * parent.quantity
            return self.recursive_amount(resource,parent.parent_id,amount_partial)
        else:
            return amount * parent.quantity

    def recursive_quantity(self, resource, parent, qty=None):
        qty = qty is None and resource.quantity or qty
        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource,parent.parent_id,qty_partial)
        else:
            return qty * parent.quantity

   # Retorna partida padre del concepto
    def get_departure_parent(self, resource):
        departure = False
        if resource.parent_id:
            if resource.parent_id.type in ['departure']:
                departure = resource.parent_id
            else:
                self.get_departure_parent(resource.parent_id)
        return departure
        
    @api.model
    def get_total_aux(self,resource):
        total = 0
        if resource.balance > 0:
            total += self.recursive_amount(resource,resource.parent_id,None)
        return total

    @api.model
    def get_total(self,resource_id,subcontract=False):
        budget = self.budget_id
        if subcontract and subcontract != 'not':
            records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id and c.subcon)
        else:
            records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id)
        total = 0

        for rec in records:
            if self.concept_ids and rec.parent_id not in self.concept_ids:
                continue
            if rec.type in ['equip']:
                if rec.parent_id.performance > 0:
                    total += rec.balance * rec.parent_id.quantity / rec.parent_id.performance
                else:
                    total += rec.balance * rec.parent_id.quantity
            elif rec.type in ['labor']:
                if rec.parent_id.performance > 0:
                    total += rec.rec_total_labor * rec.parent_id.quantity / rec.parent_id.performance
                else:
                    total += rec.rec_total_labor * rec.parent_id.quantity
            else:
                total += rec.balance * rec.parent_id.quantity

        return total

    @api.model
    def get_quantity_aux(self,resource):
        total_qty = 0
        if resource.quantity > 0:
            total_qty += self.recursive_quantity(resource,resource.parent_id,None)
        return total_qty

    @api.model
    def get_quantity(self,resource_id,subcontract):
        total_qty = 0
        budget = self.budget_id
        if subcontract == 'subcon':#add
            records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id and c.subcon)#add
        elif subcontract == 'separe':#add
            records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id and not c.subcon)#add
        else:
            records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id)

        for rec in records:
            if rec.quantity > 0:
                if self.concept_ids and rec.parent_id not in self.concept_ids:
                    continue
                if rec.type in ['labor', 'equip']:
                    if self.type_unit == 'day':
                        total_qty += rec.rec_total_days
                    elif self.type_unit == 'hour':
                        total_qty += rec.rec_total_hh
                    else:
                        total_qty += rec.quantity * rec.parent_id.quantity
                else:
                    total_qty += rec.quantity * rec.parent_id.quantity
        return total_qty

    @api.model
    def get_cost(self,resource_id):
        cost = 0
        budget = self.budget_id
        record = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id)
        first_record = record[:1]
        if first_record:
            cost = first_record.amount_fixed
        return cost

    @api.model
    def get_function(self,aux):
        values = self.budget_id.concept_ids
        resources = False
        if aux:
            resources = values.filtered(lambda c: c.type == 'aux')
        return resources

    @api.model
    def get_sucontract(self):
        resources = self.budget_id.concept_ids.filtered(lambda c: c.subcon)
        return resources

    @api.model
    def get_resources(self,material,labor,equipment,subcontract):
        if self.concept_ids:
            values = self.budget_id.concept_ids
            # quitamos los que su parent_id no esta en la lista
            values = values.filtered(lambda c: c.parent_id in self.concept_ids)
        else:
            values = self.budget_id.concept_ids

        domain = []
        if material:
            domain.append('material')
        if equipment:
            domain.append('equip')
        if labor:
            domain.append('labor')
        if subcontract:
            domain.append('subcontract')
        resources = values.filtered(lambda c: c.type in domain).mapped('product_id')
        if self.filter_categ:
            resources = resources.filtered(lambda p: p.categ_id.id == self.category_id.id)
        return resources

    @api.model
    def get_resources_concept(self,material,labor,equipment,subcontract):
        values = self.budget_id.concept_ids.sorted(key=lambda c: c.parent_id.id)
        domain = []
        if material:
            domain.append('material')
        if equipment:
            domain.append('equip')
        if labor:
            domain.append('labor')
        if self.fsubcontract:
            domain.append('subcontract')
        resources = values.filtered(lambda c: c.type in domain)
        if self.filter_categ:
            resources = resources.filtered(lambda p: p.product_id.categ_id.id == self.category_id.id)
        return resources

    @api.model
    def get_resources_total(self,material,labor,equipment,aux,subcontract, total_material, total_labor, total_equipment, total_aux, total_subcontract):
        values = self.budget_id.concept_ids
        if subcontract != 'not':
            values = values.filtered(lambda x: not x.subcon)
        result = []


        if self.concept_ids:
            # Mano de Obra
            if labor:
                result.append({'name':_('Total Labor'),'amount': total_labor})

            # Equipos
            if equipment:
                result.append({'name':_('Total Equipment'),'amount': total_equipment})


            # Materiales
            if material:
                result.append({'name':_('Total Materials'),'amount': total_material})

            # Subcontratos
            if subcontract:
                result.append({'name':_('Total Subcontracts'),'amount': total_subcontract})

            # Otros
            if aux:
                result.append({'name':_('Total Other'),'amount': total_aux})
        else:
            # Mano de Obra
            if labor and self.budget_id.amount_total_labor > 0:
                result.append({'name':_('Total Labor'),'amount': self.budget_id.amount_total_labor})

            # Equipos
            if equipment and self.budget_id.amount_total_equip > 0:
                result.append({'name':_('Total Equipment'),'amount': self.budget_id.amount_total_equip})


            # Materiales
            if material and self.budget_id.amount_total_material > 0:
                result.append({'name':_('Total Materials'),'amount': self.budget_id.amount_total_material})


            if subcontract and self.budget_id.amount_total_subcontract > 0:
                result.append({'name':_('Total Subcontracts'),'amount': self.budget_id.amount_total_subcontract})


            if aux and self.budget_id.amount_total_other > 0:
                total_aux = self.budget_id.amount_total_other
                result.append({'name':_('Total Other'),'amount': total_aux})

        return result

    @api.onchange('equipment', 'material', 'labor','aux','subcontract')
    def onchange_resource(self):
        self.resource_all = True if (self.equipment and self.material and self.labor and self.aux) else False

    @api.onchange('resource_all')
    def onchange_resource_all(self):
        if not self.resource_all and (self.equipment and self.material and self.labor and self.aux and self.fsubcontract):
            self.equipment = self.material = self.labor = self.aux = self.fsubcontract = False
        elif self.resource_all:
            self.equipment = self.material = self.labor = self.aux = self.fsubcontract = True

    def print_report(self):
        return self.env.ref('base_bim_2.bim_budget_resource').report_action(self)

    def get_resource_type(self,res_type):
        result = ''
        if res_type == 'aux':
            result = _('FUNCTION / ADMINISTRATIVE')
        elif res_type == 'H':
            result = _('LABOR')
        elif res_type == 'M':
            result = _('MATERIAL')
        elif res_type == 'Q':
            result = _('EQUIPMENT')
        elif res_type == 'S':
            result = _('SUBCONTRACT')

        return result

    @api.onchange('group_stage')
    def onchange_group_stage(self):
        if self.group_stage == 'all':
            self.stage_ids = self.budget_id.stage_ids.ids or []
        else:
            self.stage_ids = False

    def check_report_xls(self):
        total_material = 0
        total_labor = 0
        total_equipment = 0
        total_aux = 0
        total_subcontract = 0

        budget = self.budget_id
        stages = self.stage_ids
        num_stages = 0
        if self.group_stage != 'not' and not budget.stage_ids:
            raise ValidationError(_('No existen Etapas para el Presupuesto'))
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet('Resources')
        file_name = 'listado_recursos_%s' % (budget.name)
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        worksheet.write_merge(0, 0, 0, 10, _("LISTADO DE RECURSOS"), style_title)
        worksheet.write_merge(1,1,0,2, _("Project"))
        worksheet.write_merge(1,1,3,5, budget.name)
        worksheet.write_merge(1,1,6,8, _("Printing Date"))
        if self.filter_categ:
            worksheet.write_merge(1,1,9,11, _("Filter Category"))
        worksheet.write_merge(2,2,0,2, budget.project_id.nombre)
        worksheet.write_merge(2,2,3,5, budget.code)
        worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'))
        if self.filter_categ:
            worksheet.write_merge(2,2,9,11, self.category_id.name)

        # Agrupacion por Etapas
        if self.group_stage != 'not':
            worksheet.write_merge(4,4,0,0, _("Code"), style_border_table_top)
            worksheet.write_merge(4,4,1,5, _("Resource"), style_border_table_top)
            worksheet.write_merge(4,4,6,6, _("Type"), style_border_table_top)
            worksheet.write_merge(4,4,7,7, _("Unit"), style_border_table_top)
            col = 8
            for stage in stages:
                worksheet.write_merge(4,4,col,col, _(stage.name), style_border_table_top)
                col += 1
            worksheet.write_merge(4,4,col,col, "Cantidad",  style_border_table_top)
            worksheet.write_merge(4,4,col+1,col+1,  "Costo" , style_border_table_top)
            worksheet.write_merge(4,4,col+2,col+2, "Total", style_border_table_top)
        else:
            worksheet.write_merge(4,4,0,0, "Código", style_border_table_top)
            worksheet.write_merge(4,4,1,5, " Nombre", style_border_table_top)
            worksheet.write_merge(4,4,6,6, "Tipo", style_border_table_top)
            worksheet.write_merge(4,4,7,7, "Unidad", style_border_table_top)
            worksheet.write_merge(4,4,8,8, "Cantidad", style_border_table_top)
            worksheet.write_merge(4,4,9,9,"Costo", style_border_table_top)
            worksheet.write_merge(4,4,10,10, "Total", style_border_table_top)


        concept_resources = self.get_resources_concept(self.material,self.labor,self.equipment,self.fsubcontract)
        resources = self.get_resources(self.material,self.labor,self.equipment,self.fsubcontract)
        subcontracts = self.get_sucontract()
        functions = self.get_function(self.aux)
        row = 5
        
        # Agrupacion por Etapas
        if self.group_stage != 'not':
            days_after = days_before = 0
            num_stages = len(stages)

            for product in concept_resources.mapped('product_id'):
                if product.code:
                    code = product.code
                else:
                    code = product.id
                worksheet.write_merge(row,row,0,0, code, style_border_table_details)
                worksheet.write_merge(row,row,1,5, product.name, style_border_table_details)
                worksheet.write_merge(row,row,6,6, self.get_resource_type(product.resource_type), style_border_table_details)
                worksheet.write_merge(row,row,7,7, product.uom_id.name, style_border_table_details)
                qty = round(self.get_quantity(product.id,self.subcontract),3)
                _cost = round(self.get_cost(product.id),2)
                
                dict_days = {}
                for res in concept_resources.filtered(lambda i:i.product_id.id == product.id):
                    depart = self.get_departure_parent(res)
                    if depart:
                        start_date = depart.acs_date_start
                        end_date = depart.acs_date_end
                        days_diff = abs(int((start_date - end_date).days))
                        day_value = round(depart.quantity/days_diff,2)
                        while start_date <= end_date:
                            date = start_date.strftime("%Y-%m-%d")
                            if dict_days.get(date):
                                dict_days[date] = dict_days[date] + day_value
                            else:
                                dict_days[date] = day_value
                            start_date += timedelta(days=1)
                col = 8
                cont = 1
                for stage in stages:
                    qty_stage = 0
                    date_start = stage.date_start
                    date_stop = stage.date_stop
                    while date_start <= date_stop:
                        date = date_start.strftime("%Y-%m-%d")
                        qty_stage += dict_days.get(date,0.0)
                        date_start += timedelta(days=1)

                    cont += 1
                    worksheet.write_merge(row,row,col,col, round(qty_stage,3), style_border_table_details)
                    col += 1
                worksheet.write_merge(row,row,col,col, qty, style_border_table_details)
                worksheet.write_merge(row,row,col+1,col+1, _cost, style_border_table_details)
                worksheet.write_merge(row,row,col+2,col+2, round(_cost*qty,3), style_border_table_details)

                if get_resource_type == 'M':
                    total_material += round(self.get_total(res.product_id.id),3)
                elif get_resource_type == 'H':
                    total_labor += round(self.get_total(res.product_id.id),3)
                elif get_resource_type == 'Q':
                    total_equipment += round(self.get_total(res.product_id.id),3)
                elif get_resource_type == 'S':
                    total_subcontract += round(self.get_total(res.product_id.id),3)
                elif get_resource_type == 'aux':
                    total_aux += round(self.get_total(res.product_id.id),3)
                else:
                    total_aux += round(self.get_total(res.product_id.id),3)

                row += 1
        else:
            for res in resources:
                _cost = round(self.get_cost(res.id),2)
                if res.code:
                    code = res.code
                else:
                    code = res.id
                worksheet.write_merge(row,row,0,0, code, style_border_table_details)
                worksheet.write_merge(row,row,1,5, res.name, style_border_table_details)
                worksheet.write_merge(row,row,6,6, self.get_resource_type(res.resource_type), style_border_table_details)
                worksheet.write_merge(row,row,7,7, res.uom_id.name, style_border_table_details)
                _qty = round(self.get_quantity(res.id,self.subcontract),3)
                worksheet.write_merge(row,row,8,8, round(self.get_quantity(res.id,self.subcontract),3), style_border_table_details)
                worksheet.write_merge(row,row,9,9, _cost, style_border_table_details)
                worksheet.write_merge(row,row,10,10, round(_cost *_qty,2), style_border_table_details)


                if res.resource_type == 'M':
                    total_material += round(self.get_total(res.id,self.subcontract),2)
                elif res.resource_type == 'H':
                    total_labor += round(self.get_total(res.id,self.subcontract),2)
                elif res.resource_type == 'Q':
                    total_equipment += round(self.get_total(res.id,self.subcontract),2)
                elif res.resource_type == 'S':
                    total_subcontract += round(self.get_total(res.id,self.subcontract),2)
                elif res.resource_type == 'aux':
                    total_aux += round(self.get_total(res.id,self.subcontract),2)
                else:
                    total_aux += round(self.get_total(res.id,self.subcontract),2)


                row += 1

        if functions:
            for res in functions:
                worksheet.write_merge(row,row,0,0, res.code, style_border_table_details)
                worksheet.write_merge(row,row,1,5, res.name, style_border_table_details)
                worksheet.write_merge(row,row,6,6, self.get_resource_type(res.type), style_border_table_details)
                worksheet.write_merge(row,row,7,7, res.uom_id.name, style_border_table_details)
                worksheet.write_merge(row,row,8,8, res.amount_compute, style_border_table_details)#round(self.get_quantity_aux(res),3)
                worksheet.write_merge(row,row,9,9, "-", style_border_table_details)
                worksheet.write_merge(row,row,10,10, round(self.get_total_aux(res),2), style_border_table_details)

                if res.type == 'M':
                    total_material += round(self.get_total_aux(res),2)
                elif res.type == 'H':
                    total_labor += round(self.get_total_aux(res),2)
                elif res.type == 'Q':
                    total_equipment += round(self.get_total_aux(res),2)
                elif res.type == 'S':
                    total_subcontract += round(self.get_total_aux(res),2)
                elif res.type == 'aux':
                    total_aux += round(self.get_total_aux(res),2)
                else:
                    total_aux += round(self.get_total_aux(res),2)

                row += 1
        if self.subcontract == 'separe':
            worksheet.write_merge(row,row,0,0, 'Subcontratos', style_border_table_top)
            row += 1
            for sub in subcontracts:
                worksheet.write_merge(row,row,0,0, sub.code, style_border_table_details)
                worksheet.write_merge(row,row,1,5, sub.name, style_border_table_details)
                worksheet.write_merge(row,row,6,6, self.get_resource_type(sub.type), style_border_table_details)
                worksheet.write_merge(row,row,7,7, sub.uom_id.name, style_border_table_details)
                worksheet.write_merge(row,row,8,8, sub.quantity, style_border_table_details)
                worksheet.write_merge(row,row,9,9, "-", style_border_table_details)
                worksheet.write_merge(row,row,10,10, round(sub.balance,2), style_border_table_details)

                if get_resource_type == 'M':
                    total_material += round(sub.balance,2)
                elif get_resource_type == 'H':
                    total_labor += round(sub.balance,2)
                elif get_resource_type == 'Q':
                    total_equipment += round(sub.balance,2)
                elif get_resource_type == 'S':
                    total_subcontract += round(sub.balance,2)
                elif get_resource_type == 'aux':
                    total_aux += round(sub.balance,2)
                else:
                    total_aux += round(sub.balance,2)

                row += 1

        totals = self.get_resources_total(self.material,self.labor,self.equipment,self.aux,self.subcontract, total_material, total_labor, total_equipment, total_aux, total_subcontract)
        for tot in totals:
            if tot['amount'] <= 0:
                continue
            worksheet.write_merge(row,row,7+num_stages,8+num_stages, tot['name'], style_border_table_details)
            worksheet.write_merge(row,row,9+num_stages,10+num_stages, tot['amount'], style_border_table_details)
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
            'target': "self",
            'no_destroy': False,
        }
