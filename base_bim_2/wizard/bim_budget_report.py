from odoo import models, fields, api, _
import xlwt
from io import BytesIO
import base64
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class BimBudgetReportWizard(models.TransientModel):
    _name = "bim.budget.report.wizard"
    _description = "Wizard Report Budget"

    @api.model
    def default_get(self, fields):
        res = super(BimBudgetReportWizard, self).default_get(fields)
        res['budget_id'] = self._context.get('active_id', False)
        return res



    use_range = fields.Boolean('Use Range', default=False, help="If checked, the report will be generated for a range of concepts.")
    range_from = fields.Integer('From Page', default=0)
    range_to = fields.Integer('To Page', default=1)
    budget_id = fields.Many2one('bim.budget', "Budget", required=True)


    @api.depends('budget_id', 'range_from', 'range_to', 'use_range')
    def _compute_concepts(self):
        for rec in self:
            rec.bim_concepts_ids = False

            if not rec.use_range:
                rec.bim_concepts_ids = rec.budget_id.concept_ids.filtered(lambda x: x.type == 'departure').sorted(key=lambda x: (x.sequence))
            else:
                if rec.range_to > rec.range_from:
                    count = 0
                    for concept in rec.budget_id.concept_ids.filtered(lambda x: x.type == 'departure').sorted(key=lambda x: (x.sequence)):
                        count += 1
                        if count >= rec.range_from and count <= rec.range_to:
                            rec.bim_concepts_ids += concept


    display_type = fields.Selection([
        ('summary', 'Summarized'),
        ('detailed', 'Detailed'),
        ('full', 'Full'),
        ('programming', 'Programming'),
        ('compare', 'Cost Balance'),
        ('analysis_ev', 'Earned Value Analysis'),
        ('r_departure_asset_discount', 'APU formato estándar'),
        ('r_departure_list', 'Presupuesto formato estándar')
    ], string="Print Type", default='summary', help="Report grouping form.")

    summary_type = fields.Selection([
        ('chapter', 'Chapter'),
        ('departure', 'Budget Item'),
        ('resource', 'Resource'),
    ], string="Print level", default=False, help="Report detail level.")

    see_total = fields.Boolean('Total', default=True)

    compare_type = fields.Selection([
        ('departure', 'Budget Item'),
        ('cost_element', 'Cost Element'),
        ('cost_detail', 'Cost Detail'),
        ('cost_full_detail', 'Cost Full Detail'),
    ], string="Compare Type", default='departure', help="Report detail level.")

    total_type = fields.Selection([
        ('asset', 'Assets and discounts'),
        ('normal','Regular Totals'),
    ], string="Totalization", default='asset')

    show_cd = fields.Boolean('Mostrar CD', default=False, help="Si esta marcado, se mostrará el Costes Directos de MO, MAT, EQ en el reporte")

    type_price = fields.Selection([
        ('price', 'Price'),
        ('cost','Cost'),
    ], string="Type Price", default='cost')

    bim_concepts_ids = fields.Many2many('bim.concepts', string='Concepts', compute='_compute_concepts')



    filter_type = fields.Selection([
        ('space', 'Filter by Spaces'),
        ('object','Filter by Objects'),
    ], string="Filter Type", default='space')


    project_id = fields.Many2one('bim.project', "Project", related='budget_id.project_id')
    text = fields.Boolean('Notes', default=True)
    measures = fields.Boolean('Measurement', default=True)
    images = fields.Boolean('Images', default=True)
    filter_ok = fields.Boolean('Add filter')
    notes_ok = fields.Boolean('Include Notes', default=True)
    show_amount_and_price = fields.Boolean('Show Amount and Price', default=True)
    space_ids = fields.Many2many('bim.budget.space', string='Spaces')
    object_ids = fields.Many2many('bim.object', string='Project object')
    ev = fields.Boolean('Earned Value', default=True)
    projection = fields.Boolean('Projection', default=True)
    bim_tools = fields.Boolean('Tools',default=True)
    bim_parts = fields.Boolean(default=True)
    bim_attendance = fields.Boolean(default=True)
    bim_invoices = fields.Boolean(default=True)
    bim_picking_out = fields.Boolean(default=True)
    bim_open_balance = fields.Boolean(default=True)
    resource_breakdown = fields.Boolean(default=False)






    @api.onchange('display_type')
    def onchange_display_type(self):
        if self.budget_id and self.budget_id.utility > 0:
            self.type_price = 'price'
            self.see_total = False
        else:
            self.see_total = True
            self.type_price = 'cost'

    @api.onchange('filter_ok')
    def onchange_filter_ok(self):
        if self.filter_ok:
            self.total_type = 'normal'
        else:
            self.total_type = 'asset'

    @api.onchange('display_type')
    def onchange_amount_type(self):
        if not self.summary_type:
            self.summary_type = 'chapter'

    @api.onchange('summary_type')
    def onchange_summary_type(self):
        if self.summary_type == 'resource':
            self.resource_breakdown = False
        if self.summary_type == 'chapter':
            self.filter_ok = False

    @api.onchange('resource_breakdown')
    def onchange_resource_breakdown(self):
        if self.resource_breakdown:
            self.filter_ok = False

    @api.model
    def recursive_quantity(self, resource, parent, qty=None):
        qty = qty is None and resource.quantity or qty
        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource,parent.parent_id,qty_partial)
        else:
            return qty * parent.quantity

    def recursive_amount(self, resource, parent, amount=None):
        amount = amount is None and resource.balance or amount or 0.0
        if parent.type == 'departure':
            amount_partial = amount * parent.quantity
            return self.recursive_amount(resource, parent.parent_id, amount_partial)
        else:
            return amount * parent.quantity

    def get_execute_aux(self, child_ids, amount):
        ''' Este metodo Retorna el Monto ejecutado
        de Funciones buscando recursivamente en Hijos'''
        amount_execute = 0
        for record in child_ids:
            if record.type == 'aux':
                amount = record.amount_execute
                amount_execute += amount
            if record.type == 'departure':
                amount_execute += record.amount_execute
            if record.child_ids:
                return self.get_execute_aux(record.child_ids,amount_execute)
        return amount_execute

    def get_execute_childs(self, child_ids, amount):
        ''' Este metodo Retorna el Monto ejecutado
        de Funciones buscando recursivamente en Hijos'''
        amount_execute = amount
        con_obj = self.env['bim.concepts']
        for record in child_ids:
            if record.type == 'departure':
                for pick in record.picking_ids:
                    for move in pick.move_ids:
                        amount_execute += con_obj._get_value(move.product_uom_qty,move.product_id)
                for part in record.part_ids:
                    for line in part.lines_ids:
                        amount_execute += line.price_subtotal

            if record.child_ids:
                return self.get_execute_childs(record.child_ids,amount_execute)
        return amount_execute

    @api.model
    def get_filter_glosa(self):
        glosa = '-'
        list_val = []
        if self.filter_ok and self.filter_type == 'space':
            for space in self.space_ids:
                list_val.append(space.name)

        if self.filter_ok and self.filter_type == 'object':
            for obj in self.object_ids:
                list_val.append(obj.desc)
        if list_val:
            glosa = '-'.join(list_val)
        return glosa

    def get_execute_departure(self, concept):
        stock_obj = self.env['stock.picking']
        con_obj = self.env['bim.concepts']
        space_ids = self.space_ids.ids
        object_ids = self.object_ids.ids
        executed = 0
        aux_exe = 0
        products_exe = []

        if self.filter_type == 'space':
            parts_filter = concept.part_ids.filtered(lambda p: p.space_id.id in space_ids)
            picks_filter = concept.picking_ids.filtered(lambda p: p.bim_space_id.id in space_ids)

        elif self.filter_type == 'object':
            parts_filter = concept.part_ids.filtered(lambda p: p.space_id.object_id.id in object_ids)
            picks_filter = concept.picking_ids.filtered(lambda p: p.bim_object_id.id in object_ids)

        for pick in picks_filter:
            for move in pick.move_ids:
                products_exe.append(move.product_id.id)
                executed += con_obj._get_value(move.product_uom_qty,move.product_id)

        for part in parts_filter:
            for line in part.lines_ids:
                products_exe.append(line.name.id)
                executed += line.price_subtotal

        if any(rec.id for rec in concept.child_ids if rec.type == 'aux'):
            amount_execute = executed
            indicators = concept.equip_amount_count + concept.labor_amount_count + concept.material_amount_count
            aux_exe = (amount_execute / indicators) * concept.aux_amount_count

        if any(rec.id for rec in concept.child_ids if rec.type == 'departure'):
            executed += self.get_execute_childs(concept.child_ids,0)

        return executed + aux_exe

    @api.model
    def get_execute(self, concept):
        space_ids = self.space_ids.ids
        object_ids = self.object_ids.ids
        aux = 0
        execute_total = 0

        #FILTRO
        if self.filter_ok:
            if concept.type == 'chapter':
                for dep in concept.child_ids:
                    execute_total += self.get_execute_departure(dep)
            else:
                execute_total = self.get_execute_departure(concept)
        #TODOS
        else:
            products_exe = []
            if concept.type == 'chapter':
                aux = self.get_execute_aux(concept.child_ids,0)
                for dp in concept.child_ids:
                    execute_total += dp.amount_execute
                    if any(rec.id for rec in dp.child_ids if rec.type == 'departure'):
                        execute_total += self.get_execute_childs(dp.child_ids,0)
            else:
                aux = self.get_execute_aux(concept.child_ids,0)
                execute_total = concept.amount_execute_equip + concept.amount_execute_labor + concept.amount_execute_material
                if any(rec.id for rec in concept.child_ids if rec.type == 'departure'):
                    execute_total += self.get_execute_childs(concept.child_ids,0)

        return execute_total + aux

    @api.model
    def get_total(self, resource):
        budget = self.budget_id
        records = budget.concept_ids.filtered(lambda c: c.type == resource)
        total = 0

        for rec in records:
            total += self.recursive_amount(rec, rec.parent_id, None)
        return total

    @api.model
    def get_total_filter(self):
        space_ids = self.space_ids.ids
        object_ids = self.object_ids.ids
        budget = self.budget_id
        records = budget.concept_ids.filtered(lambda c: not c.parent_id and c.type == 'chapter')
        total_aux = total_eqp = total_lab = total_mat = 0

        for concept in records:
            lis = []
            dep_ids = self.get_departures(concept.child_ids,lis)
            dep_ids = set(dep_ids)
            for dep in self.env['bim.concepts'].browse(dep_ids):
                qty = 0
                for mea in dep.measuring_ids:
                    if self.filter_type == 'space':
                        if mea.space_id and mea.space_id.id in space_ids:
                            qty += mea.amount_subtotal

                    elif self.filter_type == 'object':
                        if mea.space_id and mea.space_id.object_id and mea.space_id.object_id.id in object_ids:
                            qty += mea.amount_subtotal

                total_aux += (dep.aux_amount_count * qty) / dep.quantity
                total_eqp += (dep.equip_amount_count * qty) / dep.quantity
                total_lab += (dep.labor_amount_count * qty) / dep.quantity
                total_mat += (dep.material_amount_count * qty) / dep.quantity

        return {'MO':total_lab,'MT':total_mat,'EQ':total_eqp,'AX':total_aux}

    @api.model
    def get_total_exe(self, chapter):
        records = chapter.concept_ids.filtered(lambda c: c.type not in resource)
        total = 0

        for rec in records:
            total += self.recursive_amount(rec, rec.parent_id, None)
        return total

    @api.model
    def get_quantity_filter(self, concept):
        """Filtro Para Reporte Detallado - Completo"""
        space_ids = self.space_ids.ids
        object_ids = self.object_ids.ids
        price = 0
        qty = 0

        if self.filter_ok:
            if concept.type == 'chapter':
                lis = []
                dep_ids = self.get_departures(concept.child_ids,lis)
                dep_ids = set(dep_ids)

                for dep in self.env['bim.concepts'].browse(dep_ids):
                    if dep.measuring_ids:
                        for mea in dep.measuring_ids:
                            if self.filter_type == 'space':
                                if mea.space_id and mea.space_id.id in space_ids:
                                    qty = 1.0
                                    price += mea.amount_subtotal * dep.amount_compute

                            if self.filter_type == 'object':
                                if mea.space_id and mea.space_id.object_id and mea.space_id.object_id.id in object_ids:
                                    qty = 1.0
                                    price += mea.amount_subtotal * dep.amount_compute


            elif concept.type == 'departure':
                if concept.measuring_ids:
                    price = concept.amount_compute
                    for mea in concept.measuring_ids:
                        if self.filter_type == 'space':
                            if mea.space_id.id in space_ids:
                                qty += mea.amount_subtotal
                        if self.filter_type == 'object':
                            if mea.space_id and mea.space_id.object_id and mea.space_id.object_id.id in object_ids:
                                qty += mea.amount_subtotal
                else:
                    qty = concept.quantity

                    for child in concept.child_ids:
                        qty_fil = 0
                        for mea in child.measuring_ids:
                            if self.filter_type == 'space':
                                if mea.space_id.id in space_ids:
                                    qty_fil += mea.amount_subtotal
                            if self.filter_type == 'object':
                                if mea.space_id and mea.space_id.object_id and mea.space_id.object_id.id in object_ids:
                                    qty_fil += mea.amount_subtotal
                        price += child.amount_compute * qty_fil

        if price > 0:
            return {'qty': round(qty,3), 'price': round(price,2)}
        else:
            return {'qty': 0, 'price': 0}


    @api.model
    def get_execute_filter(self, concept):
        """Filtro Para Reporte Comparativo (Ejecucion Real)"""
        space_ids = self.space_ids.ids
        object_ids = self.object_ids.ids
        qty = 0
        lis = []
        if self.filter_ok:
            if concept.type == 'chapter':
                dep_ids = self.get_departures(concept.child_ids,lis)
                dep_ids = set(dep_ids)
                for dep in self.env['bim.concepts'].browse(dep_ids):
                    # Revisamos las Partes
                    for part in dep.part_ids:
                        if self.filter_type == 'space':
                            if part.space_id and part.space_id.id in space_ids:
                                qty += 1
                        elif self.filter_type == 'object':
                            if part.space_id and part.space_id.object_id and part.space_id.object_id.id in object_ids:
                                qty += 1

                    # Revisamos los Picking
                    for pick in dep.picking_ids:
                        if self.filter_type == 'space':
                            if pick.bim_space_id and pick.bim_space_id.id in space_ids:
                                qty += 1
                        elif self.filter_type == 'object':
                            if pick.bim_object_id and pick.bim_object_id.id in object_ids:
                                qty += 1

            elif concept.type == 'departure':
                # Revisamos las Partes
                for part in concept.part_ids:
                    if self.filter_type == 'space':
                        if part.space_id and part.space_id.id in space_ids:
                            qty += 1
                    elif self.filter_type == 'object':
                        if part.space_id and part.space_id.object_id and part.space_id.object_id.id in object_ids:
                            qty += 1

                # Revisamos los Picking
                for pick in concept.picking_ids:
                    if self.filter_type == 'space':
                        if pick.bim_space_id and pick.bim_space_id.id in space_ids:
                            qty += 1
                    elif self.filter_type == 'object':
                        if pick.bim_object_id and pick.bim_object_id.id in object_ids:
                            qty += 1
        return round(qty,3)

   # Retorna partidas contenidos en el concepto
    def get_departures(self, child_ids, dep_ids):
        res = dep_ids
        for record in child_ids:
            if record.type in ['departure']:
                res.append(record.id)
            if record.child_ids:
                self.get_departures(record.child_ids,res)
        return res

    # ~ def get_departures(self, child_ids):
        # ~ res = []
        # ~ childs = child_ids
        # ~ while childs:
            # ~ for record in childs:
                # ~ if record.type in ['departure']:
                    # ~ res.append(record.id)
                # ~ if record.child_ids:
                    # ~ childs = record.child_ids
                # ~ else:
                    # ~ childs = False
        # ~ return res

   # Retorna Recursos contenidos en el concepto
    def get_resources(self, child_ids):
        res = []
        for record in child_ids:
            if record.product_id and record.type in ['material']:
                res.append(record.product_id.id)
            if record.child_ids:
                self.get_resources(record.child_ids)
        return res

    def check_report(self):
        self.ensure_one()
        data = {}
        data['id'] = self._context.get('active_id', [])
        data['docs'] = self._context.get('active_ids', [])
        data['model'] = self._context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read([])[0]
        return self._print_report(data)

    def _print_report(self, data):
        if self.display_type == 'summary':
            action = self.env.ref('base_bim_2.bim_budget_summary').report_action(self)
        elif self.display_type == 'full':
            action = self.env.ref('base_bim_2.bim_budget_full').report_action(self)
        elif self.display_type == 'programming':
            action = self.env.ref('base_bim_2.bim_budget_programming').report_action(self)
        elif self.display_type == 'analysis_ev':
            action = self.env.ref('base_bim_2.bim_budget_stage').report_action(self)
        elif self.display_type == 'r_departure_asset_discount':
            action = self.env.ref('base_bim_2.bim_budget_departure_asset_discount').report_action(self)
        elif self.display_type == 'r_departure_list':
            action = self.env.ref('base_bim_2.bim_budget_departure_list').report_action(self)
        elif self.display_type == 'compare':
            if self.env.user.has_group('base_bim_2.group_manager_bim') or self.env.user.has_group('base_bim_2.group_see_cost_bim'):
                pass
            else:
                raise UserError(_("Sorry! Report not available!"))
            if self.compare_type == 'departure':
                action = self.env.ref('base_bim_2.bim_budget_real_execute').report_action(self)
            elif self.compare_type == 'cost_full_detail':
                action = self.env.ref('base_bim_2.bim_budget_real_execute_full_detailed').report_action(self)
            else:
                action = self.env.ref('base_bim_2.bim_budget_real_execute_detailed').report_action(self)
        else:
            action = self.env.ref('base_bim_2.bim_budget').report_action(self)
        action.update({'close_on_report_download': True})
        return action


    def check_report_xls(self):
        budget = self.budget_id
        workbook = xlwt.Workbook(encoding="utf-8")
        file_name = "Reporte" + "_" + budget.code.replace(' ','_') + "_" + budget.name.replace(' ','_')

        if self.display_type == 'r_departure_asset_discount':
            file_name = "Reporte_por_apu" + "_" + (budget.code or '').replace(' ','_') + "_" + (budget.name or '').replace(' ','_')

            # ===== Estilos base que ya tenías (ajusto heights y mantengo Times) =====
            style_simple = xlwt.easyxf('align: wrap yes, horiz center;')
            style_simple_left = xlwt.easyxf('align: wrap yes, horiz left;')
            style_simple_right = xlwt.easyxf('align: wrap yes, horiz right;')
            style_title_blue = xlwt.easyxf('font: name Times New Roman, height 280, color-index blue, bold on; align: wrap yes, horiz center;')
            style_title_black = xlwt.easyxf('font: name Times New Roman, height 280, color-index black, bold on; align: wrap yes, horiz center;')
            style_title_black_left = xlwt.easyxf('font: name Times New Roman, height 220, color-index black, bold on; align: wrap yes, horiz left;')
            style_title_red_left = xlwt.easyxf('font: name Times New Roman, height 200, color-index red, bold on; align: wrap yes, horiz left;')
            style_number = xlwt.easyxf('align: horiz right;', num_format_str='#,##0.00')

            # ===== Helper de estilos de tabla (borde caja + rejilla + encabezado gris) =====
            def _mk_style(align='left', bold=False, bg=None, L='thin', R='thin', T='thin', B='thin', numfmt=None):
                parts = [
                    'font: name Times New Roman, height 200' + (', bold on' if bold else '') + ';',
                    f'align: wrap yes, horiz {align};',
                    f'borders: left {L}, right {R}, top {T}, bottom {B};'
                ]
                if bg:
                    parts.append(f'pattern: pattern solid, fore_colour {bg};')
                if numfmt:
                    return xlwt.easyxf(' '.join(parts), num_format_str=numfmt)
                return xlwt.easyxf(' '.join(parts))

            # encabezado de tabla
            th_left  = _mk_style('left',  True, None, L='thin', R='thin',  T='thin', B='thin')
            th_mid   = _mk_style('left',  True, None, L='thin',  R='thin',  T='thin', B='thin')
            th_right = _mk_style('left',  True, None, L='thin',  R='thin', T='thin', B='thin')

            # cuerpo texto
            td_left_txt  = _mk_style('left',  False, None, L='thin', R='thin',  T='thin', B='thin')
            td_mid_txt   = _mk_style('left',  False, None, L='thin',  R='thin',  T='thin', B='thin')
            td_right_txt = _mk_style('left',  False, None, L='thin',  R='thin', T='thin', B='thin')

            # cuerpo números
            td_left_num  = _mk_style('right', False, None, L='thin', R='thin',  T='thin', B='thin', numfmt='#,##0.00')
            td_mid_num   = _mk_style('right', False, None, L='thin',  R='thin',  T='thin', B='thin', numfmt='#,##0.00')
            td_right_num = _mk_style('right', False, None, L='thin',  R='thin', T='thin', B='thin', numfmt='#,##0.00')

            # pie / totales (cierre inferior grueso)
            foot_left_txt  = _mk_style('right', True, None, L='thin', R='thin',  T='thin', B='thin')
            foot_mid_num   = _mk_style('right', True, None, L='thin',  R='thin',  T='thin', B='thin', numfmt='#,##0.00')
            foot_mid_pct = _mk_style(
                'right', True, None,
                L='thin', R='thin', T='thin', B='thin',
                numfmt='0.00%'   # <-- aquí el cambio
                )
            foot_right_num = _mk_style('right', True, None, L='thin',  R='thin', T='thin', B='thin', numfmt='#,##0.00')

            # ===== Anchos de columnas (A..J) para que respire como el diseño =====
            def _colw(chars): return int(chars * 256)
            def _set_cols(ws):
                try:
                    ws.col(0).width = _colw(6)    # A
                    ws.col(1).width = _colw(4)    # B
                    ws.col(2).width = _colw(2)    # C (para merges)
                    ws.col(3).width = _colw(36)   # D Descripción
                    ws.col(4).width = _colw(10)   # E Und / Cantidad
                    ws.col(5).width = _colw(8)    # F
                    ws.col(6).width = _colw(10)   # G
                    ws.col(7).width = _colw(8)    # H
                    ws.col(8).width = _colw(12)   # I Total
                    ws.col(9).width = _colw(14)   # J
                except Exception:
                    pass

            _logger.info("APU UNITARIO O DESCUENTO POR ACTIVIDAD")


            departures = budget.concept_ids.filtered(lambda c: c.type == 'departure').sorted(key=lambda x: (x.sequence or 0))

            if self.use_range:
                departures = departures[(self.range_from - 1):self.range_to]

            _no = 0

            for departure in departures:
                _row_mat = 0
                _row_eqp = 0
                _row_lab = 0
                _row_sub = 0
                _row_per = 0

                administration_percent = departure.get_departure_budget_asset_percent([('asset_id.desc','in',('Administration','Administracion','Administración','Gastos Administración','Administración y Gastos Generales'))])
                # administration_percent = budget.social_benefits

                _utility = departure.get_departure_budget_asset_percent([('asset_id.desc','in',('Utility','Utilidad'))])
                if not administration_percent:
                    administration_percent = 0
                if not _utility:
                    _utility = 0

                _no += 1
                _logger.info("PARTIDA: %s", departure.name)
                worksheet = workbook.add_sheet("No " + str(_no))
                _set_cols(worksheet)

                row = 0
                # ===== Encabezado superior =====
                row += 1
                worksheet.write_merge(row, row, 0, 5, budget.company_id.name or "", style_title_black)
                worksheet.write_merge(row, row, 6, 9, "Partida: " + str(_no), style_title_black)
                row += 1

                rif = (budget.project_id.company_id.vat if budget.project_id and budget.project_id.company_id else "") or ""
                worksheet.write_merge(row, row, 0, 5, "RIF: " + rif, style_title_black_left)
                fecha = getattr(budget, 'date', None) or getattr(budget, 'date_start', None) or ""
                worksheet.write_merge(row, row, 6, 9, f"Fecha: {fecha}", style_title_black_left)
                row += 1

                presu_linea = f"PRESUPUESTO: {(budget.code or '')} - {(budget.name or '')}"
                worksheet.write_merge(row, row, 0, 9, presu_linea, style_title_black_left)
                row += 1

                obra = getattr(budget.project_id, 'nombre', '') or getattr(budget, 'project_name', '') or ''
                worksheet.write_merge(row, row, 0, 5, "OBRA / PROYECTO: " + obra, style_title_black_left)
                worksheet.write_merge(row, row, 6, 9, "CÓD. PRESUPUESTO: " + (budget.code or ''), style_title_black_left)
                row += 1

                propietaria = (budget.project_id and budget.project_id.customer_id and budget.project_id.customer_id.name) or "PROPIETARIA"
                worksheet.write_merge(row, row, 0, 5, str(propietaria), style_title_black_left)
                worksheet.write_merge(row, row, 6, 9, "", style_title_black)
                row += 1

                worksheet.write_merge(row, row, 0, 9, "ANALISIS DE PRECIO UNITARIO", style_title_blue)
                row += 1

                worksheet.write_merge(row, row, 0, 9, departure.name or "", style_title_black_left)
                row += 1

                worksheet.write_merge(row, row, 0, 3, "Código: " + (departure.code or ''), style_title_black_left)
                worksheet.write_merge(row, row, 4, 4, "Unidad: " + (departure.uom_id.name or ''), style_title_black_left)
                worksheet.write_merge(row, row, 5, 6, "Cantidad: " + str(departure.quantity or 0), style_title_black_left)
                worksheet.write_merge(row, row, 7, 8, "Rendimiento:", style_title_black_left)
                _row_per = row
                worksheet.write_merge(row, row, 9, 9, departure.performance, td_mid_num)
                row += 1

                mat_ids = departure.child_ids.filtered(lambda c: c.type == 'material').sorted(key=lambda x: (x.sequence or 0))
                if len(mat_ids) > 0:
                    # ====================== 1.- MATERIALES ======================
                    worksheet.write_merge(row, row, 0, 9, "1.- MATERIALES", style_title_black_left)
                    row += 1
                    worksheet.write_merge(row, row, 0, 1, "No",          th_left)
                    worksheet.write_merge(row, row, 2, 3, "Descripción", th_mid)
                    worksheet.write_merge(row, row, 4, 4, "Und",         th_mid)
                    worksheet.write_merge(row, row, 5, 5, "Cantidad",    th_mid)
                    worksheet.write_merge(row, row, 6, 6, "Desp",        th_mid)
                    worksheet.write_merge(row, row, 7, 7, "Precio",      th_mid)
                    worksheet.write_merge(row, row, 8, 8, "Total",       th_right)
                    row += 1

                    mat_first_excel = row + 1
                    _no_mat = 0
                    for mat in departure.child_ids.filtered(lambda c: c.type == 'material').sorted(key=lambda x: (x.sequence or 0)):
                        _no_mat += 1
                        worksheet.write_merge(row, row, 0, 1, _no_mat,                         td_left_txt)
                        worksheet.write_merge(row, row, 2, 3, mat.product_id.name or "",       td_mid_txt)
                        worksheet.write_merge(row, row, 4, 4, mat.uom_id.name if mat.uom_id else "", td_mid_txt)
                        worksheet.write_merge(row, row, 5, 5, mat.quantity or 0,               td_mid_num)
                        worksheet.write_merge(row, row, 6, 6, mat.waste or 0,                  td_mid_num)
                        unit_cost = mat.amount_fixed
                        worksheet.write(row, 7, unit_cost,                                     td_mid_num)  # no merge en números/fórmulas
                        excel_row = row + 1
                        worksheet.write(row, 8, xlwt.Formula(f"ROUND(F{excel_row}*(1+G{excel_row}/100)*H{excel_row},2)"), td_right_num)

                        row += 1

                    """
                    worksheet.write_merge(row, row, 5, 7, "Flete por Transporte:", td_right_txt)
                    worksheet.write(row, 8, 0, td_right_num)
                    row += 1
                    """

                    worksheet.write_merge(row, row, 5, 7, "Total Materiales:", foot_left_txt)
                    _row_mat = row + 1
                    mat_last_data_excel = row - 1
                    worksheet.write(row, 8, xlwt.Formula(f"ROUND(SUM(I{mat_first_excel}:I{mat_last_data_excel+1}),2)"), foot_right_num)
                    worksheet.write(row, 9, xlwt.Formula(f"ROUND(I{row+1},2)"), foot_right_num)
                    row += 1
                else:
                    _row_mat = row + 1

                # ====================== 2.- EQUIPOS ======================
                equip_ids = departure.child_ids.filtered(lambda c: c.type == 'equip').sorted(key=lambda x: (x.sequence or 0))
                if len(equip_ids) > 0:
                    row += 1
                    worksheet.write_merge(row, row, 0, 9, "2.- EQUIPOS", style_title_black_left)
                    row += 1
                    worksheet.write_merge(row, row, 0, 1, "No",          th_left)
                    worksheet.write_merge(row, row, 2, 3, "Descripción", th_mid)
                    worksheet.write_merge(row, row, 4, 4, "Und",         th_mid)
                    worksheet.write_merge(row, row, 5, 5, "Cantidad",    th_mid)
                    worksheet.write_merge(row, row, 6, 6, "Desp",        th_mid)
                    worksheet.write_merge(row, row, 7, 7, "Precio",      th_mid)
                    worksheet.write_merge(row, row, 8, 8, "Total",       th_right)
                    row += 1

                    eq_first_excel = row + 1
                    _no_eqp = 0
                    for equip in equip_ids:
                        _no_eqp += 1
                        worksheet.write_merge(row, row, 0, 1, _no_eqp,                          td_left_txt)
                        worksheet.write_merge(row, row, 2, 3, equip.product_id.name or "",      td_mid_txt)
                        worksheet.write_merge(row, row, 4, 4, equip.uom_id.name if equip.uom_id else "", td_mid_txt)
                        worksheet.write_merge(row, row, 5, 5, equip.quantity or 0,              td_mid_num)
                        worksheet.write_merge(row, row, 6, 6, equip.depreciation or 0,                 td_mid_num)
                        unit_cost = equip.amount_fixed
                        worksheet.write(row, 7, unit_cost,                                      td_mid_num)
                        excel_row = row + 1
                        worksheet.write(row, 8, xlwt.Formula(f"ROUND( (F{excel_row}*G{excel_row}*H{excel_row}) ,2)"), td_right_num)

                        row += 1

                    worksheet.write_merge(row, row, 5, 7, "Total Equipos:", foot_left_txt)
                    _row_eqp = row + 1
                    eq_last_data_excel = row
                    worksheet.write(row, 8, xlwt.Formula(f"ROUND(SUM(I{eq_first_excel}:I{eq_last_data_excel}),2)"), foot_right_num)
                    worksheet.write(row, 9, xlwt.Formula(f"ROUND(I{row+1}/J{_row_per+1} ,2)"), foot_right_num)
                    row += 1
                else:
                    _row_eqp = row + 1

                # ====================== 4.- SUB CONTRATO ======================
                subcontrat_ids = departure.child_ids.filtered(lambda c: c.type == 'subcontract').sorted(key=lambda x: (x.sequence or 0))
                if len(subcontrat_ids) > 0:
                    row += 1
                    worksheet.write_merge(row, row, 0, 9, "4.- SUB CONTRATO", style_title_black_left)
                    row += 1
                    worksheet.write_merge(row, row, 0, 1, "No",          th_left)
                    worksheet.write_merge(row, row, 2, 3, "Descripción", th_mid)
                    worksheet.write_merge(row, row, 4, 4, "Und",         th_mid)
                    worksheet.write_merge(row, row, 5, 5, "Cantidad",    th_mid)
                    worksheet.write_merge(row, row, 6, 6, "Desp",        th_mid)
                    worksheet.write_merge(row, row, 7, 7, "Precio",      th_mid)
                    worksheet.write_merge(row, row, 8, 8, "Total",       th_right)
                    row += 1

                    sub_first_excel = row + 1
                    _no_subcontract = 0
                    for subcontract in subcontrat_ids:
                        _no_subcontract += 1
                        worksheet.write_merge(row, row, 0, 1, _no_subcontract,                               td_left_txt)
                        worksheet.write_merge(row, row, 2, 3, subcontract.product_id.name or "",             td_mid_txt)
                        worksheet.write_merge(row, row, 4, 4, subcontract.uom_id.name if subcontract.uom_id else "", td_mid_txt)
                        worksheet.write_merge(row, row, 5, 5, subcontract.quantity or 0,                     td_mid_num)
                        worksheet.write_merge(row, row, 6, 6, subcontract.waste or 0,                        td_mid_num)
                        # unit_cost = round((subcontract.amount_fixed / subcontract.quantity) if (subcontract.quantity or 0) > 0 else 0, 2)
                        worksheet.write(row, 7, subcontract.amount_fixed,                                                  td_mid_num)
                        excel_row = row + 1
                        worksheet.write(row, 8, xlwt.Formula(f"ROUND(F{excel_row}*(1+G{excel_row}/100)*H{excel_row},2)"), td_right_num)
                        _row_sub = row
                        row += 1

                    worksheet.write_merge(row, row, 5, 7, "Total Subcontrato:", foot_left_txt)
                    _row_sub = row + 1

                    sub_last_data_excel = row - 1
                    worksheet.write(row, 8, xlwt.Formula(f"ROUND(SUM(I{sub_first_excel}:I{sub_last_data_excel}),2)"), foot_right_num)
                    worksheet.write(row, 9, xlwt.Formula(f"ROUND(I{row+1},2)"), foot_right_num)
                    row += 1
                else:
                    _row_sub = row + 1

                labor_ids = departure.child_ids.filtered(lambda c: c.type == 'labor').sorted(key=lambda x: (x.sequence or 0))
                # ====================== 3.- MANO DE OBRA ======================
                row += 1
                worksheet.write_merge(row, row, 0, 9, "3.- MANO DE OBRA", style_title_black_left)
                row += 1
                worksheet.write_merge(row, row, 0, 1, "No",          th_left)
                worksheet.write_merge(row, row, 2, 3, "Descripción", th_mid)
                worksheet.write_merge(row, row, 4, 4, "Cantidad",    th_mid)
                worksheet.write_merge(row, row, 5, 5, "Jornal",      th_mid)
                worksheet.write_merge(row, row, 6, 6, "Bono",        th_mid)
                worksheet.write_merge(row, row, 7, 7, "T.Jornal",    th_mid)
                worksheet.write_merge(row, row, 8, 8, "T.Bono",      th_right)
                row += 1

                labor_first_excel = row + 1
                _no_labor = 0
                for labor in labor_ids:
                    _no_labor += 1
                    worksheet.write_merge(row, row, 0, 1, _no_labor,                    td_left_txt)
                    worksheet.write_merge(row, row, 2, 3, labor.product_id.name or "",  td_mid_txt)
                    worksheet.write_merge(row, row, 4, 4, labor.quantity or 0,          td_mid_num)
                    worksheet.write_merge(row, row, 5, 5, labor.amount_fixed or 0,      td_mid_num)
                    if departure.use_foot_bonus:
                        foot_bonus = departure.foot_bonus
                    else:
                        foot_bonus = budget.foot_bonus
                    worksheet.write_merge(row, row, 6, 6, foot_bonus,td_mid_num)
                    excel_row = row + 1
                    worksheet.write(row, 7, xlwt.Formula(f"ROUND(E{excel_row}*F{excel_row},2)"), td_mid_num)   # T.Jornal
                    worksheet.write(row, 8, xlwt.Formula(f"ROUND(E{excel_row}*G{excel_row},2)"), td_right_num) # T.Bono

                    row += 1

                worksheet.write_merge(row, row, 4, 6, "Sub-Total Mano de Obra:", foot_left_txt)
                worksheet.write(row, 7, xlwt.Formula(f"ROUND(SUM(H{labor_first_excel}:H{row}),2)"), foot_mid_num)
                worksheet.write(row, 8, xlwt.Formula(f"ROUND(SUM(I{labor_first_excel}:I{row}),2)"), foot_right_num)
                row += 1

                pres_sociales = budget.social_benefits
                worksheet.write_merge(row, row, 4, 6, str(pres_sociales) + "% Prestaciones Sociales:", foot_left_txt)
                worksheet.write(row, 7, xlwt.Formula(f"ROUND(H{row}*{pres_sociales/100},2)"), foot_mid_num)
                worksheet.write(row, 8, "", foot_right_num)
                row += 1

                worksheet.write_merge(row, row, 4, 6, "Total Jornal y Bono:", foot_left_txt)
                worksheet.write(row, 7, xlwt.Formula(f"ROUND((H{ row -1} + H{row}),2)"), foot_mid_num)
                worksheet.write(row, 8, xlwt.Formula(f"ROUND(I{row-1},2)"), foot_right_num)
                row += 1

                worksheet.write_merge(row, row, 4, 6, "Total Mano de Obra:", foot_left_txt)
                worksheet.write_merge(row, row, 7, 8, xlwt.Formula(f"ROUND((H{row}+I{row}),2)"), foot_mid_num)
                worksheet.write(row, 9, xlwt.Formula(f"ROUND(H{row+1}/J{_row_per+1} ,2)"), foot_right_num)
                _row_lab = row + 1

                row += 2

                worksheet.write_merge(row, row, 6, 8, "Costo Directo Sub-Total A:", foot_left_txt)

                worksheet.write(
                            row, 9,
                            xlwt.Formula(f"ROUND(SUM(J{_row_mat},J{_row_eqp},J{_row_lab},J{_row_sub}),2)"),
                            foot_mid_num
                        )

                # Escribimos los % en cada uno de los tipos
                if len(mat_ids) > 0:
                    worksheet.write( _row_mat - 2, 9, xlwt.Formula(f"J{_row_mat}/J{row+1}"), foot_mid_pct )
                if len(equip_ids) > 0:
                    worksheet.write( _row_eqp - 2, 9, xlwt.Formula(f"J{_row_eqp}/J{row+1}"), foot_mid_pct )
                if len(labor_ids) > 0:
                    worksheet.write( _row_lab - 2, 9, xlwt.Formula(f"J{_row_lab}/J{row+1}"), foot_mid_pct )
                if len(subcontrat_ids) > 0:
                    worksheet.write( _row_sub - 2, 9, xlwt.Formula(f"J{_row_sub}/J{row+1}"), foot_mid_pct )



                row += 1


                if departure.use_administration:
                    administration_percent = departure.administration

                worksheet.write_merge(row, row, 6, 8, str(administration_percent) + " % Administración y Gastos Generales:", foot_left_txt)
                # =REDONDEAR(N36*0,15; 2)

                _logger.info("administration_percent: %s", administration_percent)

                worksheet.write_merge(row, row, 9, 9, xlwt.Formula(f"ROUND( J{row} * {administration_percent}/100  ,2)"), foot_mid_num)
                row += 1
                worksheet.write_merge(row, row, 6, 8, "Sub-Total B:", foot_left_txt)
                worksheet.write_merge(row, row, 9, 9, xlwt.Formula(f"ROUND( J{row} +  J{row-1}  ,2)"), foot_mid_num)
                row += 1
                if departure.use_utility:
                    _utility = departure.utility
                worksheet.write_merge(row, row, 6, 8, str(_utility) + " % Utilidad o Imprevistos:", foot_left_txt)
                worksheet.write_merge(row, row, 9, 9, xlwt.Formula(f"ROUND( J{row} * {_utility}/100  ,2)"), foot_mid_num)
                row += 1
                worksheet.write_merge(row, row, 6, 8, "Sub-Total C:", foot_left_txt)
                worksheet.write_merge(row, row, 9, 9, xlwt.Formula(f"ROUND(SUM(J{row}+J{row-1}),2)"), foot_mid_num)
                row += 1
                worksheet.write_merge(row, row, 6, 8, "0,00 Financiamiento:", foot_left_txt)
                worksheet.write_merge(row, row, 9, 9, 0, foot_mid_num)
                row += 1
                worksheet.write_merge(row, row, 6, 8, "Precio Unitario:", foot_left_txt)
                worksheet.write_merge(row, row, 9, 9, xlwt.Formula(f"ROUND(SUM(J{row}+J{row-1}),2)"), foot_mid_num)
                row += 1

        else:
            worksheet = workbook.add_sheet('Budget')
            style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center;')
            style_filter_title = xlwt.easyxf('font: color-index black, bold on; align: wrap yes, horiz center;')
            style_filter_title2 = xlwt.easyxf('align: wrap yes, horiz center;')
            style_summary = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin;')
            style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on; align: wrap yes, horiz center;')
            style_border_table_bottom = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on;')
            style_border_table_details_chapters = xlwt.easyxf('borders: bottom thin;')
            style_border_table_details_departed = xlwt.easyxf('borders: bottom thin;')
            style_border_table_details = xlwt.easyxf('borders: bottom thin;')


            if self.summary_type in ['resource']:
                worksheet.write_merge(0, 0, 0, 9, _("BUDGET REPORT"), style_title)
                worksheet.write_merge(1,1,0,2, _("Project"),style_filter_title)
                worksheet.write_merge(1,1,3,5, budget.name,style_filter_title)
                worksheet.write_merge(1,1,6,8, _("Printing Date"),style_filter_title)
                if self.filter_ok:
                    worksheet.write_merge(1,1,9,9, _("Added Filter"),style_filter_title)
                worksheet.write_merge(2,2,0,2, budget.project_id.nombre,style_filter_title2)
                worksheet.write_merge(2,2,3,5, budget.code,style_filter_title2)
                worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'),style_filter_title2)
                if self.filter_ok:
                    worksheet.write_merge(2,2,9,9, self.get_filter_glosa(),style_filter_title2)

                row = 5
                # Header table
                worksheet.write_merge(row,row,0,1, _("CODE"), style_border_table_top)
                worksheet.write_merge(row,row,2,2, _("INSUMO"), style_border_table_top)
                worksheet.write_merge(row,row,3,8, _("CRITERION"), style_border_table_top)
                worksheet.write_merge(row,row,9,9, _("UNIT"), style_border_table_top)
                worksheet.write_merge(row,row,10,10, _("QUANTITY"), style_border_table_top)
                worksheet.write_merge(row,row,11,11, _("PRICE"), style_border_table_top)
                worksheet.write_merge(row,row,12,12, _("AMOUNT"), style_border_table_top)

                # Imprimimos los capitulos
                chapters = budget.concept_ids.filtered(lambda c: c.type == 'chapter').sorted(key=lambda x: (x.sequence))
                total = 0
                __counter = 0

                for chapter in chapters:
                    row += 1
                    worksheet.write_merge(row,row,0,1, chapter.code, style_border_table_details_chapters)
                    worksheet.write_merge(row,row,2,2, "", style_border_table_details_chapters)
                    worksheet.write_merge(row,row,3,8, chapter.name, style_border_table_details_chapters)
                    worksheet.write_merge(row,row,9,9, "", style_border_table_details_chapters)
                    worksheet.write_merge(row,row,10,10, chapter.quantity, style_border_table_details_chapters)
                    worksheet.write_merge(row,row,11,11, chapter.amount_compute, style_border_table_details_chapters)
                    worksheet.write_merge(row,row,12,12, chapter.balance, style_border_table_details_chapters)





                    departures = chapter.child_ids.filtered(lambda c: c.type == 'departure')
                    # Buscamos las partidas que tienen como padre el capitulo
                    if departures:
                        for departure in departures:
                            row += 1
                            worksheet.write_merge(row,row,0,1, departure.code, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,2,2, "", style_border_table_details_chapters)
                            worksheet.write_merge(row,row,3,8, departure.name, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,9,9, departure.uom_id.name if departure.uom_id else "", style_border_table_details_chapters)
                            worksheet.write_merge(row,row,10,10, departure.quantity, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,11,11, departure.amount_compute, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,12,12, departure.balance, style_border_table_details_chapters)




                            # Imprimimos los recursos
                            if departure.child_ids:
                                for resource in departure.child_ids:
                                    if resource.product_id:
                                        row += 1
                                        code = resource.product_id.code
                                        if not code:
                                            code = resource.product_id.id
                                        worksheet.write_merge(row,row,0,1, "", style_border_table_details)
                                        worksheet.write_merge(row,row,2,2, code, style_border_table_details)
                                        worksheet.write_merge(row,row,3,8, resource.product_id.name, style_border_table_details)
                                        worksheet.write_merge(row,row,9,9, resource.uom_id.name if resource.uom_id else "", style_border_table_details)
                                        worksheet.write_merge(row,row,10,10, resource.quantity, style_border_table_details)
                                        worksheet.write_merge(row,row,11,11, resource.amount_compute, style_border_table_details)
                                        worksheet.write_merge(row,row,12,12, resource.balance, style_border_table_details)

            else:
                if self.display_type == 'summary':
                    worksheet.write_merge(0, 0, 0, 11, _("SUMMARY BUDGET REPORT"), style_title)
                    worksheet.write_merge(1,1,0,3, _("Project"),style_filter_title)
                    worksheet.write_merge(2,2,0,3, budget.project_id.nombre,style_filter_title2)
                    worksheet.write_merge(1,1,4,8, budget.name,style_filter_title)
                    worksheet.write_merge(2,2,4,8, budget.code,style_filter_title2)
                    worksheet.write_merge(1,1,9,11, _("Printing Date"),style_filter_title)
                    worksheet.write_merge(2,2,9,11, datetime.now().strftime('%d-%m-%Y'),style_filter_title2)

                    row = 4
                    row_to = row + 1

                    if self.total_type == 'normal':
                        mt = round(self.get_total('material'),2)
                        mo = round(self.get_total('labor'),2)
                        eq = round(self.get_total('equip'),2)
                        tot = mt + mo + eq
                        others = round((budget.balance - tot),2)
                        total = round(budget.balance,2)

                        worksheet.write_merge(row,row_to,0,3, _("Total Materials"), style_summary)
                        worksheet.write_merge(row,row_to,4,5, mt, style_summary)
                        row += 2
                        row_to = row + 1
                        worksheet.write_merge(row,row_to,0,3, _("Total Labor"), style_summary)
                        worksheet.write_merge(row,row_to,4,5, mo, style_summary)
                        row += 2
                        row_to = row + 1
                        worksheet.write_merge(row,row_to,0,3, _("Total Equipment"), style_summary)
                        worksheet.write_merge(row,row_to,4,5, eq, style_summary)
                        row += 2
                        row_to = row + 1
                        worksheet.write_merge(row,row_to,0,3, _("Other"), style_summary)
                        worksheet.write_merge(row,row_to,4,5, others, style_summary)
                        row += 2
                        row_to = row + 1
                        worksheet.write_merge(row,row_to,0,3, "TOTAL", style_summary)
                        worksheet.write_merge(row,row_to,4,5, total, style_summary)
                        row += 1

                    else:
                        for asset in budget.asset_ids:
                            if asset.asset_id.show_on_report:
                                worksheet.write_merge(row,row,0,3, asset.asset_id.desc, style_summary)
                                worksheet.write_merge(row,row,4,5, round(asset.total,2), style_summary)
                                row += 1



                elif self.display_type == 'r_departure_list':
                    worksheet.write_merge(0, 0, 0, 13, "REPORTE DE PRESUPUESTO", style_title)
                    worksheet.write_merge(1,1,0,2, "Proyecto",style_filter_title)
                    worksheet.write_merge(1,1,3,5, budget.name,style_filter_title)
                    worksheet.write_merge(1,1,6,8, "Impreso",style_filter_title)
                    if self.filter_ok:
                        worksheet.write_merge(1,1,9,13, _("Added Filter"),style_filter_title)
                    worksheet.write_merge(2,2,0,2, budget.project_id.nombre,style_filter_title2)
                    worksheet.write_merge(2,2,3,5, budget.code,style_filter_title2)
                    worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'),style_filter_title2)
                    if self.filter_ok:
                        worksheet.write_merge(2,2,9,13, self.get_filter_glosa(),style_filter_title2)

                    row = 4
                    # Header table
                    worksheet.write_merge(row,row,0,0, "#", style_border_table_top)
                    worksheet.write_merge(row,row,1,1, "Part.", style_border_table_top)
                    worksheet.write_merge(row,row,2,7, "Descripción.", style_border_table_top)
                    worksheet.write_merge(row,row,8,8, "Und", style_border_table_top)
                    worksheet.write_merge(row,row,9,9, "Cantidad", style_border_table_top)
                    worksheet.write_merge(row,row,10,10, "PU", style_border_table_top)
                    worksheet.write_merge(row,row,11,11, "Total", style_border_table_top)

                    chapters = budget.concept_ids.filtered(lambda c: not c.parent_id)
                    total = 0
                    row += 1
                    __counter = 0
                    for chapter in chapters:
                        __counter += 1
                        balance = round(chapter.balance, 2)
                        execute = round(chapter.balance_execute, 2)
                        difference = balance - execute
                        worksheet.write_merge(row,row,0,0, __counter, style_border_table_details_chapters)
                        worksheet.write_merge(row,row,1,1, chapter.code, style_border_table_details_chapters)
                        worksheet.write_merge(row,row,2,7, chapter.name, style_border_table_details_chapters)
                        worksheet.write_merge(row,row,8,8, "", style_border_table_details_chapters)
                        worksheet.write_merge(row,row,9,9, "", style_border_table_details_chapters)
                        worksheet.write_merge(row,row,10,10, "", style_border_table_details_chapters)
                        worksheet.write_merge(row,row,11,11, "", style_border_table_details_chapters)
                        row += 1

                        for child in chapter.child_ids:
                            __counter += 1
                            child_balance = round(child.balance, 2)
                            # child_execute = round(self.get_execute(child), 2)
                            child_execute = round(child.balance_execute, 2)
                            child_difference = child_balance - child_execute

                            worksheet.write_merge(row,row,0,0, __counter, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,1,1, child.code, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,2,7, child.name, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,8,8, child.uom_id.name if child.uom_id else "", style_border_table_details_chapters)
                            worksheet.write_merge(row,row,9,9, child.quantity, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,10,10, child.amount_compute, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,11,11, child.balance, style_border_table_details_chapters)
                            row += 1




                elif self.display_type == 'compare':
                    worksheet.write_merge(0, 0, 0, 13, _("REAL EXECUTION REPORT"), style_title)
                    worksheet.write_merge(1,1,0,2, _("Project"),style_filter_title)
                    worksheet.write_merge(1,1,3,5, budget.name,style_filter_title)
                    worksheet.write_merge(1,1,6,8, _("Printing Date"),style_filter_title)
                    if self.filter_ok:
                        worksheet.write_merge(1,1,9,13, _("Added Filter"),style_filter_title)
                    worksheet.write_merge(2,2,0,2, budget.project_id.nombre,style_filter_title2)
                    worksheet.write_merge(2,2,3,5, budget.code,style_filter_title2)
                    worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'),style_filter_title2)
                    if self.filter_ok:
                        worksheet.write_merge(2,2,9,13, self.get_filter_glosa(),style_filter_title2)

                    row = 4
                    # Header table
                    worksheet.write_merge(row,row,8,9, _("BUDGET"), style_border_table_top)
                    worksheet.write_merge(row,row,10,11, _("REAL EXECUTED"), style_border_table_top)
                    row_to = row + 1
                    worksheet.write_merge(row,row_to,12,13, _("DIFFERENCE"), style_border_table_top)
                    row += 1
                    worksheet.write_merge(row,row,0,1, _("CODE"), style_border_table_top)
                    worksheet.write_merge(row,row,2,7, _("CONCEPT"), style_border_table_top)
                    worksheet.write_merge(row,row,8,8, _("QUANTITY"), style_border_table_top)
                    worksheet.write_merge(row,row,9,9, _("BUDGET"), style_border_table_top)
                    worksheet.write_merge(row,row,10,10, _("QUANTITY"), style_border_table_top)
                    worksheet.write_merge(row,row,11,11, _("REAL"), style_border_table_top)
                    chapters = budget.concept_ids.filtered(lambda c: not c.parent_id)
                    total = 0
                    row += 1
                    for chapter in chapters:
                        balance = 0
                        execute = 0
                        difference = 0
                        if self.filter_ok:
                            if self.get_execute_filter(chapter) > 0:
                                balance = round(chapter.balance,2)
                                execute = round(self.get_execute(chapter),2)
                                difference = balance - execute
                                worksheet.write_merge(row,row,0,1, chapter.code, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,2,7, chapter.name, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,8,8, "-", style_border_table_details_chapters)
                                worksheet.write_merge(row,row,9,9, balance, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,10,10, "-", style_border_table_details_chapters)
                                worksheet.write_merge(row,row,11,11, execute, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,12,13, difference, style_border_table_details_chapters)
                                row += 1

                                for child in chapter.child_ids:
                                    if self.get_execute_filter(child) > 0:
                                        child_balance = round(child.balance, 2)
                                        child_execute = round(self.get_execute(child), 2)
                                        child_difference = child_balance - child_execute

                                        worksheet.write_merge(row,row,0,1, child.code, style_border_table_details_departed)
                                        worksheet.write_merge(row,row,2,7, child.name, style_border_table_details_departed)
                                        worksheet.write_merge(row,row,8,8, child.quantity, style_border_table_details_departed)
                                        worksheet.write_merge(row,row,9,9, child_balance, style_border_table_details_departed)
                                        worksheet.write_merge(row,row,10,10, "-", style_border_table_details_departed)
                                        worksheet.write_merge(row,row,11,11, child_execute, style_border_table_details_departed)
                                        worksheet.write_merge(row,row,12,13, child_difference, style_border_table_details_departed)
                                        row += 1
                        else:
                            balance = round(chapter.balance, 2)
                            execute = round(chapter.balance_execute, 2)
                            difference = balance - execute

                            worksheet.write_merge(row,row,0,1, chapter.code, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,2,7, chapter.name, style_border_table_details_chapters)
                            worksheet.write_merge(row,row,8,8, "-", style_border_table_details_chapters)
                            worksheet.write_merge(row, row, 9, 9, balance,style_border_table_details_chapters)
                            worksheet.write_merge(row, row, 10, 10, "-",style_border_table_details_chapters)
                            worksheet.write_merge(row, row, 11, 11, execute,style_border_table_details_chapters)
                            worksheet.write_merge(row, row, 12, 13, difference,style_border_table_details_chapters)
                            row += 1

                            for child in chapter.child_ids:
                                child_balance = round(child.balance, 2)
                                # child_execute = round(self.get_execute(child), 2)
                                child_execute = round(child.balance_execute, 2)
                                child_difference = child_balance - child_execute

                                worksheet.write_merge(row,row,0,1, child.code, style_border_table_details_departed)
                                worksheet.write_merge(row,row,2,7, child.name, style_border_table_details_departed)
                                worksheet.write_merge(row,row,8,8, child.quantity, style_border_table_details_departed)
                                worksheet.write_merge(row,row,9,9, child_balance, style_border_table_details_departed)
                                worksheet.write_merge(row,row,10,10, "-", style_border_table_details_departed)
                                worksheet.write_merge(row,row,11,11, child_execute, style_border_table_details_departed)
                                worksheet.write_merge(row,row,12,13, child_difference, style_border_table_details_departed)
                                row += 1

                else:# (DETALLADO - COMPLETO)
                    if self.show_amount_and_price:
                        worksheet.write_merge(0, 0, 0, 11, _("BUDGET REPORT"), style_title)
                    else:
                        worksheet.write_merge(0, 0, 0, 9, _("BUDGET REPORT"), style_title)
                    worksheet.write_merge(1,1,0,2, _("Project"),style_filter_title)
                    worksheet.write_merge(1,1,3,5, budget.name,style_filter_title)
                    worksheet.write_merge(1,1,6,8, _("Printing Date"),style_filter_title)
                    if self.filter_ok:
                        worksheet.write_merge(1,1,9,9, _("Added Filter"),style_filter_title)
                    worksheet.write_merge(2,2,0,2, budget.project_id.nombre,style_filter_title2)
                    worksheet.write_merge(2,2,3,5, budget.code,style_filter_title2)
                    worksheet.write_merge(2,2,6,8, datetime.now().strftime('%d-%m-%Y'),style_filter_title2)
                    if self.filter_ok:
                        worksheet.write_merge(2,2,9,9, self.get_filter_glosa(),style_filter_title2)

                    row = 5
                    # Header table
                    worksheet.write_merge(row,row,0,1, _("CODE"), style_border_table_top)
                    worksheet.write_merge(row,row,2,7, _("CRITERION"), style_border_table_top)
                    worksheet.write_merge(row,row,8,8, _("UNIT"), style_border_table_top)
                    if self.show_amount_and_price:
                        worksheet.write_merge(row,row,9,9, _("QUANTITY"), style_border_table_top)
                        worksheet.write_merge(row,row,10,10, _("PRICE"), style_border_table_top)
                        worksheet.write_merge(row,row,11,11, _("AMOUNT"), style_border_table_top)
                    else:
                        worksheet.write_merge(row,row,9,9, _("AMOUNT"), style_border_table_top)
                    row += 1

                    if self.summary_type in ['resource']:
                        parents = budget.concept_ids.filtered(lambda c: not c.parent_id)
                        for parent in parents:
                            if self.filter_ok:
                                filter_val = self.get_quantity_filter(parent)
                                if filter_val['qty'] > 0:
                                    worksheet.write_merge(row,row,0,1, parent.code, style_border_table_details_chapters)
                                    worksheet.write_merge(row,row,2,7, parent.name, style_border_table_details_chapters)
                                    worksheet.write_merge(row,row,8,8, parent.uom_id and parent.uom_id.name or '', style_border_table_details_chapters)
                                    if self.show_amount_and_price:
                                        worksheet.write_merge(row,row,9,9, parent.quantity, style_border_table_details_chapters)
                                        worksheet.write_merge(row,row,10,10, filter_val['price'], style_border_table_details_chapters)
                                        worksheet.write_merge(row,row,11,11, filter_val['price'], style_border_table_details_chapters)
                                    else:
                                        worksheet.write_merge(row,row,9,9, filter_val['price'], style_border_table_details_chapters)
                                    row += 1

                                    if self.text and parent.note and self.display_type == 'full':
                                        worksheet.write_merge(row,row,0,9, parent.note, style_border_table_details)
                                        row += 1

                                    if self.summary_type in ['departure','resource']:
                                        for child in parent.child_ids:
                                            filter_child = self.get_quantity_filter(child)
                                            style_child = child.type == 'departure' and style_border_table_details_departed or style_border_table_details_chapters

                                            if filter_child['qty'] > 0:
                                                worksheet.write_merge(row,row,0,1, child.code, style_child)
                                                worksheet.write_merge(row,row,2,7, child.name, style_child)
                                                worksheet.write_merge(row,row,8,8, child.uom_id and child.uom_id.name or '', style_child)
                                                if self.show_amount_and_price:
                                                    worksheet.write_merge(row,row,9,9, filter_child['qty'], style_child)
                                                    worksheet.write_merge(row,row,10,10, filter_child['price'], style_child)
                                                    worksheet.write_merge(row,row,11,11, filter_child['qty'] * filter_child['price'], style_child)
                                                else:
                                                    worksheet.write_merge(row,row,9,9, filter_child['qty'] * filter_child['price'], style_child)
                                                row += 1

                                                # EXTRA: Si hay un hijo partida o capitulo
                                                if any(ext.type in ['departure','chapter'] for ext in child.child_ids) and self.summary_type in ['departure']:
                                                    for extra in child.child_ids:
                                                        filter_ext = self.get_quantity_filter(extra)
                                                        style_ext = extra.type == 'departure' and style_border_table_details_departed or style_border_table_details_chapters
                                                        if filter_ext['qty'] > 0:
                                                            worksheet.write_merge(row,row,0,1, extra.code, style_ext)
                                                            worksheet.write_merge(row,row,2,7, extra.name, style_ext)
                                                            worksheet.write_merge(row,row,8,8, extra.uom_id and extra.uom_id.name or '', style_ext)
                                                            if self.show_amount_and_price:
                                                                worksheet.write_merge(row,row,9,9, filter_ext['qty'], style_ext)
                                                                worksheet.write_merge(row,row,10,10, filter_ext['price'], style_ext)
                                                                worksheet.write_merge(row,row,11,11, filter_ext['price']*filter_ext['qty'], style_ext)
                                                            else:
                                                                worksheet.write_merge(row,row,9,9, filter_ext['price']*filter_ext['qty'], style_ext)
                                                            row += 1
                                                            if self.measures and extra.measuring_ids and self.display_type == 'full':
                                                                worksheet.write_merge(row,row,1,1, _("Group"), style_border_table_bottom)
                                                                worksheet.write_merge(row,row,2,4, _("Description"), style_border_table_bottom)
                                                                worksheet.write_merge(row,row,5,5, _("Quant(N)"), style_border_table_bottom)
                                                                worksheet.write_merge(row,row,6,6, _("Length(X)"), style_border_table_bottom)
                                                                worksheet.write_merge(row,row,7,7, _("Width(Y)"), style_border_table_bottom)
                                                                worksheet.write_merge(row,row,8,8, _("Height(Z)"), style_border_table_bottom)
                                                                if self.show_amount_and_price:
                                                                    worksheet.write_merge(row,row,9,9, _("Formula"), style_border_table_bottom)
                                                                    worksheet.write_merge(row,row,10,10, "Subtotal", style_border_table_bottom)
                                                                else:
                                                                    worksheet.write_merge(row,row,9,9, "Subtotal", style_border_table_bottom)
                                                                row += 1

                                                                if self.filter_type == 'space':
                                                                    measures_filter = extra.measuring_ids.filtered(lambda m: m.space_id.id in self.space_ids.ids)
                                                                else:
                                                                    measures_filter = extra.measuring_ids.filtered(lambda m: m.space_id.object_id.id in self.object_ids.ids)

                                                                for msr in measures_filter:
                                                                    worksheet.write_merge(row,row,1,1, msr.space_id.display_name or '', style_border_table_details)
                                                                    worksheet.write_merge(row,row,2,4, msr.name or '', style_border_table_details)
                                                                    worksheet.write_merge(row,row,5,5, msr.qty, style_border_table_details)
                                                                    worksheet.write_merge(row,row,6,6, msr.length, style_border_table_details)
                                                                    worksheet.write_merge(row,row,7,7, msr.width, style_border_table_details)
                                                                    worksheet.write_merge(row,row,8,8, msr.height, style_border_table_details)
                                                                    if self.show_amount_and_price:
                                                                        worksheet.write_merge(row,row,9,9, msr.formula.name or '', style_border_table_details)
                                                                        worksheet.write_merge(row,row,10,10, round(msr.amount_subtotal,2), style_border_table_details)
                                                                    else:
                                                                        worksheet.write_merge(row,row,9,9, round(msr.amount_subtotal,2), style_border_table_details)
                                                                    row += 1

                                                if self.text and child.note and self.display_type == 'full':
                                                    worksheet.write_merge(row,row,0,9, child.note, style_border_table_details)
                                                    row += 1
                                                if self.measures and child.measuring_ids and self.display_type == 'full':
                                                    worksheet.write_merge(row,row,1,1, _("Group"), style_border_table_bottom)
                                                    worksheet.write_merge(row,row,2,4, _("Description"), style_border_table_bottom)
                                                    worksheet.write_merge(row,row,5,5, _("Quant(N)"), style_border_table_bottom)
                                                    worksheet.write_merge(row,row,6,6, _("Length(X)"), style_border_table_bottom)
                                                    worksheet.write_merge(row,row,7,7, _("Width(Y)"), style_border_table_bottom)
                                                    worksheet.write_merge(row,row,8,8, _("Height(Z)"), style_border_table_bottom)
                                                    if self.show_amount_and_price:
                                                        worksheet.write_merge(row,row,9,9, _("Formula"), style_border_table_bottom)
                                                        worksheet.write_merge(row,row,10,10, "Subtotal", style_border_table_bottom)
                                                    else:
                                                        worksheet.write_merge(row,row,9,9, "Subtotal", style_border_table_bottom)
                                                    row += 1

                                                    if self.filter_type == 'space':
                                                        measures_filter = child.measuring_ids.filtered(lambda m: m.space_id.id in self.space_ids.ids)
                                                    else:
                                                        measures_filter = child.measuring_ids.filtered(lambda m: m.space_id.object_id.id in self.object_ids.ids)

                                                    for msr in measures_filter:
                                                        worksheet.write_merge(row,row,1,1, msr.space_id.display_name or '', style_border_table_details)
                                                        worksheet.write_merge(row,row,2,4, msr.name or '', style_border_table_details)
                                                        worksheet.write_merge(row,row,5,5, msr.qty, style_border_table_details)
                                                        worksheet.write_merge(row,row,6,6, msr.length, style_border_table_details)
                                                        worksheet.write_merge(row,row,7,7, msr.width, style_border_table_details)
                                                        worksheet.write_merge(row,row,8,8, msr.height, style_border_table_details)
                                                        if self.show_amount_and_price:
                                                            worksheet.write_merge(row,row,9,9, msr.formula.name or '', style_border_table_details)
                                                            worksheet.write_merge(row,row,10,10, round(msr.amount_subtotal,2), style_border_table_details)
                                                        else:
                                                            worksheet.write_merge(row,row,9,9, round(msr.amount_subtotal,2), style_border_table_details)
                                                        row += 1

                                                if child.child_ids and self.summary_type in ['resource']:
                                                    for resource in child.child_ids:
                                                        worksheet.write_merge(row,row,0,1, resource.code, style_border_table_details)
                                                        worksheet.write_merge(row,row,2,7, resource.name, style_border_table_details)
                                                        worksheet.write_merge(row,row,8,8, resource.uom_id and resource.uom_id.name or '', style_border_table_details)
                                                        if self.show_amount_and_price:
                                                            worksheet.write_merge(row,row,9,9, resource.quantity, style_border_table_details)
                                                            worksheet.write_merge(row,row,10,10, round(resource.amount_compute,2), style_border_table_details)
                                                            worksheet.write_merge(row,row,11,11, round(resource.balance,2), style_border_table_details)
                                                        else:
                                                            worksheet.write_merge(row,row,9,9, round(resource.balance,2), style_border_table_details)
                                                        row += 1
                                                        if self.text and resource.note and self.display_type == 'full':
                                                            worksheet.write_merge(row,row,0,9, resource.note, style_border_table_details)
                                                            row += 1

                            # (DETALLADO - COMPLETO SIN FILTRO)
                            else:
                                worksheet.write_merge(row,row,0,1, parent.code, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,2,7, parent.name, style_border_table_details_chapters)
                                worksheet.write_merge(row,row,8,8, parent.uom_id and parent.uom_id.name or '', style_border_table_details_chapters)
                                if self.show_amount_and_price:
                                    worksheet.write_merge(row,row,9,9, parent.quantity, style_border_table_details_chapters)
                                    worksheet.write_merge(row,row,10,10, round(parent.amount_compute,2), style_border_table_details_chapters)
                                    worksheet.write_merge(row,row,11,11, round(parent.balance,2), style_border_table_details_chapters)
                                else:
                                    worksheet.write_merge(row,row,9,9, round(parent.balance,2), style_border_table_details_chapters)
                                row += 1
                                if self.text and parent.note and self.display_type == 'full':
                                    worksheet.write_merge(row,row,0,9, parent.note, style_border_table_details)
                                    row += 1
                                if self.summary_type in ['departure','resource']:
                                    for child in parent.child_ids:
                                        if child.type == 'departure':
                                            worksheet.write_merge(row,row,0,1, child.code, style_border_table_details_departed)
                                            worksheet.write_merge(row,row,2,7, child.name, style_border_table_details_departed)
                                            worksheet.write_merge(row,row,8,8, child.uom_id and child.uom_id.name or '', style_border_table_details_departed)
                                            if self.show_amount_and_price:
                                                worksheet.write_merge(row,row,9,9, child.quantity, style_border_table_details_departed)
                                                worksheet.write_merge(row,row,10,10, round(child.amount_compute,2), style_border_table_details_departed)
                                                worksheet.write_merge(row,row,11,11, round(child.balance,2), style_border_table_details_departed)
                                            else:
                                                worksheet.write_merge(row,row,9,9, round(child.balance,2), style_border_table_details_departed)
                                            row += 1
                                        else:
                                            worksheet.write_merge(row,row,0,1, child.code, style_border_table_details)
                                            worksheet.write_merge(row,row,2,7, child.name, style_border_table_details)
                                            worksheet.write_merge(row,row,8,8, child.uom_id and child.uom_id.name or '', style_border_table_details)
                                            if self.show_amount_and_price:
                                                worksheet.write_merge(row,row,9,9, child.quantity, style_border_table_details)
                                                worksheet.write_merge(row,row,10,10, round(child.amount_compute,2), style_border_table_details)
                                                worksheet.write_merge(row,row,11,11, round(child.balance,2), style_border_table_details)
                                            else:
                                                worksheet.write_merge(row,row,9,9, round(child.balance,2), style_border_table_details)
                                            row += 1
                                        if self.text and child.note and self.display_type == 'full':
                                            worksheet.write_merge(row,row,0,9, child.note, style_border_table_details)
                                            row += 1
                                        if self.measures and child.measuring_ids and self.display_type == 'full':
                                            worksheet.write_merge(row,row,1,1, _("Group"), style_border_table_bottom)
                                            worksheet.write_merge(row,row,2,4, _("Description"), style_border_table_bottom)
                                            worksheet.write_merge(row,row,5,5, _("Quant(N)"), style_border_table_bottom)
                                            worksheet.write_merge(row,row,6,6, _("Length(X)"), style_border_table_bottom)
                                            worksheet.write_merge(row,row,7,7, _("Width(Y)"), style_border_table_bottom)
                                            worksheet.write_merge(row,row,8,8, _("Height(Z)"), style_border_table_bottom)
                                            if self.show_amount_and_price:
                                                worksheet.write_merge(row,row,9,9, _("Formula"), style_border_table_bottom)
                                                worksheet.write_merge(row,row,10,10, "Subtotal", style_border_table_bottom)
                                            else:
                                                worksheet.write_merge(row,row,9,9, "Subtotal", style_border_table_bottom)
                                            row += 1
                                            for msr in child.measuring_ids:
                                                worksheet.write_merge(row,row,1,1, msr.space_id.display_name or '', style_border_table_details)
                                                worksheet.write_merge(row,row,2,4, msr.name or '', style_border_table_details)
                                                worksheet.write_merge(row,row,5,5, msr.qty, style_border_table_details)
                                                worksheet.write_merge(row,row,6,6, msr.length, style_border_table_details)
                                                worksheet.write_merge(row,row,7,7, msr.width, style_border_table_details)
                                                worksheet.write_merge(row,row,8,8, msr.height, style_border_table_details)
                                                if self.show_amount_and_price:
                                                    worksheet.write_merge(row,row,9,9, msr.formula.name or '', style_border_table_details)
                                                    worksheet.write_merge(row,row,10,10, round(msr.amount_subtotal,2), style_border_table_details)
                                                else:
                                                    worksheet.write_merge(row,row,9,9, round(msr.amount_subtotal,2), style_border_table_details)
                                                row += 1

                                        if child.child_ids and self.summary_type in ['resource']:
                                            for resource in child.child_ids:
                                                worksheet.write_merge(row,row,0,1, resource.code, style_border_table_details)
                                                worksheet.write_merge(row,row,2,7, resource.name, style_border_table_details)
                                                worksheet.write_merge(row,row,8,8, resource.uom_id and resource.uom_id.name or '', style_border_table_details)

                                                if self.show_amount_and_price:
                                                    worksheet.write_merge(row,row,9,9, resource.quantity, style_border_table_details)
                                                    worksheet.write_merge(row,row,10,10, round(resource.amount_compute,2), style_border_table_details)
                                                    worksheet.write_merge(row,row,11,11, round(resource.balance,2), style_border_table_details)
                                                else:
                                                    worksheet.write_merge(row,row,9,9, round(resource.balance,2), style_border_table_details)
                                                row += 1
                                                if self.text and resource.note and self.display_type == 'full':
                                                    worksheet.write_merge(row,row,0,9, resource.note, style_border_table_details)
                                                    row += 1
                        # TOTALES (CON FILTRO)
                        if self.filter_ok:
                            total_filter = self.get_total_filter()
                            if self.show_amount_and_price:
                                if total_filter['MT'] > 0:
                                    worksheet.write_merge(row,row,8,10, _("Total Materials"), style_summary)
                                    worksheet.write_merge(row,row,11,11, total_filter['MT'], style_summary)
                                    row += 1
                                if total_filter['MO'] > 0:
                                    worksheet.write_merge(row,row,8,10, _("Total Labor"), style_summary)
                                    worksheet.write_merge(row,row,11,11, total_filter['MO'], style_summary)
                                    row += 1
                                if total_filter['EQ'] > 0:
                                    worksheet.write_merge(row,row,8,10, _("Total Equipment"), style_summary)
                                    worksheet.write_merge(row,row,11,11, total_filter['EQ'], style_summary)
                                    row += 1
                                if total_filter['AX'] > 0:
                                    worksheet.write_merge(row,row,8,10, _("Other"), style_summary)
                                    worksheet.write_merge(row,row,11,11, total_filter['AX'], style_summary)
                                    row += 1
                                worksheet.write_merge(row,row,8,10, "TOTAL", style_summary)
                                worksheet.write_merge(row,row,11,11, total_filter['MT']+total_filter['MO']+total_filter['EQ']+total_filter['AX'], style_summary)
                            else:
                                if total_filter['MT'] > 0:
                                    worksheet.write_merge(row,row,6,8, _("Total Materials"), style_summary)
                                    worksheet.write_merge(row,row,9,9, total_filter['MT'], style_summary)
                                    row += 1
                                if total_filter['MO'] > 0:
                                    worksheet.write_merge(row,row,6,8, _("Total Labor"), style_summary)
                                    worksheet.write_merge(row,row,9,9, total_filter['MO'], style_summary)
                                    row += 1
                                if total_filter['EQ'] > 0:
                                    worksheet.write_merge(row,row,6,8, _("Total Equipment"), style_summary)
                                    worksheet.write_merge(row,row,9,9, total_filter['EQ'], style_summary)
                                    row += 1
                                if total_filter['AX'] > 0:
                                    worksheet.write_merge(row,row,6,8, _("Other"), style_summary)
                                    worksheet.write_merge(row,row,9,9, total_filter['AX'], style_summary)
                                    row += 1
                                worksheet.write_merge(row,row,6,8, "TOTAL", style_summary)
                                worksheet.write_merge(row,row,9,9, total_filter['MT']+total_filter['MO']+total_filter['EQ']+total_filter['AX'], style_summary)

                        # TOTALES (SIN FILTRO)
                        else:
                            if self.show_amount_and_price:
                                if self.total_type == 'normal':
                                    mt = round(self.get_total('material'),2)
                                    mo = round(self.get_total('labor'),2)
                                    eq = round(self.get_total('equip'),2)
                                    tot = mt + mo + eq
                                    others = round((budget.balance - tot),2)
                                    total = round(budget.balance,2)
                                    if mt > 0:
                                        worksheet.write_merge(row,row,8,10, _("Total Materials"), style_summary)
                                        worksheet.write_merge(row,row,11,11, mt, style_summary)
                                        row += 1
                                    if mo > 0:
                                        worksheet.write_merge(row,row,8,10, _("Total Labor"), style_summary)
                                        worksheet.write_merge(row,row,11,11, mo, style_summary)
                                        row += 1
                                    if eq > 0:
                                        worksheet.write_merge(row,row,8,10, _("Total Equipment"), style_summary)
                                        worksheet.write_merge(row,row,11,11, eq, style_summary)
                                        row += 1
                                    if others > 0:
                                        worksheet.write_merge(row,row,8,10, _("Others"), style_summary)
                                        worksheet.write_merge(row,row,11,11, others, style_summary)
                                        row += 1
                                    worksheet.write_merge(row,row,8,10, "TOTAL", style_summary)
                                    worksheet.write_merge(row,row,11,11, total, style_summary)
                                else:
                                    for asset in budget.asset_ids:
                                        if asset.asset_id.show_on_report:
                                            worksheet.write_merge(row,row,8,10, asset.asset_id.desc, style_summary)
                                            worksheet.write_merge(row,row,11,11, round(asset.total,2), style_summary)
                                            row += 1
                            else:
                                if self.total_type == 'normal':
                                    mt = round(self.get_total('material'),2)
                                    mo = round(self.get_total('labor'),2)
                                    eq = round(self.get_total('equip'),2)
                                    tot = mt + mo + eq
                                    others = round((budget.balance - tot),2)
                                    total = round(budget.balance,2)
                                    if mt > 0:
                                        worksheet.write_merge(row,row,6,8, _("Total Materials"), style_summary)
                                        worksheet.write_merge(row,row,9,9, mt, style_summary)
                                        row += 1
                                    if mo > 0:
                                        worksheet.write_merge(row,row,6,8, _("Total Labor"), style_summary)
                                        worksheet.write_merge(row,row,9,9, mo, style_summary)
                                        row += 1
                                    if eq > 0:
                                        worksheet.write_merge(row,row,6,8, _("Total Equipment"), style_summary)
                                        worksheet.write_merge(row,row,9,9, eq, style_summary)
                                        row += 1
                                    if others > 0:
                                        worksheet.write_merge(row,row,8,10, _("Others"), style_summary)
                                        worksheet.write_merge(row,row,11,11, others, style_summary)
                                        row += 1
                                    worksheet.write_merge(row,row,6,8, "TOTAL", style_summary)
                                    worksheet.write_merge(row,row,9,9, total, style_summary)
                                else:
                                    for asset in budget.asset_ids:
                                        if asset.asset_id.show_on_report:
                                            worksheet.write_merge(row,row,6,8, asset.asset_id.desc, style_summary)
                                            worksheet.write_merge(row,row,9,9, round(asset.total,2), style_summary)
                                            row += 1

                    else:
                        _logger.info(self.summary_type)
                        raise UserError("Este reporte no esta Implementado.")


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


