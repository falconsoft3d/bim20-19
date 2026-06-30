# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import  timedelta, datetime
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split
CONCEPT_TYPES = {
    'L': 'labor',
    'Q': 'equip',
    'M': 'material',
    'A': 'aux',
    'S': 'subcontract',
}
CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux','S': 'subcontract'}

import logging
_logger = logging.getLogger(__name__)

class BimConcepts(models.Model):
    _name = 'bim.concepts'
    _order = "sequence, id"
    _description = "Concept (Chapters-Sub-Chapters-Items-Resources)"


    def update_p(self):
        for rec in self:
            rec.budget_id.update_amount()

    @api.constrains('code', 'type', 'budget_id')
    def _check_unique_concept_code(self):
        for concept in self:
            # Verifica si el código debe ser único según la configuración
            bim_general_config_id = self.env['bim.general.config'].sudo().search([
                ('key', '=', 'apu_unique')
            ], limit=1)

            value = bim_general_config_id.value if bim_general_config_id else '0'

            if value == '1' and concept.code and concept.type in ['chapter', 'departure']:
                # Busca duplicados dentro del mismo presupuesto
                duplicates = self.search_count([
                    ('code', '=', concept.code),
                    ('type', 'in', ['chapter', 'departure']),
                    ('budget_id', '=', concept.budget_id.id),
                    ('id', '!=', concept.id)  # Excluye el registro actual
                ])
                if duplicates > 0:
                    raise ValidationError(
                        _("Ya existe un Concepto con el código '%s' en el presupuesto: %s") %
                        (concept.code, concept.budget_id.name)
                    )

    @api.model
    def default_get(self, default_fields):
        values = super(BimConcepts, self).default_get(default_fields)
        parent_id = self._context.get('default_parent_id', False)
        budget_id = self._context.get('default_budget_id', False)
        active_id = self._context.get('active_id')
        # Agregando Hijo
        if parent_id:
            parent = self.browse(parent_id)
            values['budget_id'] = parent.budget_id.id
            values['sequence'] = len(parent.child_ids) + 1
            if parent.type in ('chapter'):
                values['type'] = 'departure'
            elif parent.type in ('departure'):
                values['type'] = 'material'
            elif parent.type in ('aux'):
                values['type'] = 'material'
            else:
                values['type'] = 'aux'
        # Agregando al mismo nivel
        else:
            values['type'] = 'chapter'
            if budget_id:
                values['budget_id'] = budget_id
            else:
                # En la recarga de vista el "active_id" esta manteniendo el id del Presupuesto
                budget = self.env['bim.budget'].browse(active_id)
                values['budget_id'] = budget.id
        return values

    @api.depends('parent_id', 'type')
    def _get_valid_certification(self):
        for rec in self:
            rec.to_certify = (rec.type == 'departure' and rec.parent_id.type == 'chapter') and True or False
            rec.auto_certify = (rec.type == 'aux' and rec.parent_id.type == 'chapter') and True or False
            rec.manual_certify = (rec.type in ['labor', 'equip', 'material'] and rec.parent_id.type == 'chapter') and True or False

    @api.depends('picking_ids')
    def _get_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    def exe_propagar(self):
        #  busca todos los conceptos con igual product_id y le pone el mismo precio
        for rec in self:
            if rec.product_id:
                concepts = self.env['bim.concepts'].search([
                    ('product_id', '=', rec.product_id.id),
                    ('id', '!=', rec.id),
                    ('budget_id', '=', rec.budget_id.id),
                ])
                for concept in concepts:
                    concept.write({
                        'amount_fixed': rec.amount_fixed,
                        'uom_id': rec.uom_id.id,
                    })

    def exe_resequential(self):
        for rec in self:
            counter = [1]  # mutable: se comparte en toda la recursión
            self._resequential_flat(rec, rec.code, counter)

    def _resequential_flat(self, parent, root_code, counter):
        children = self.env['bim.concepts'].search(
            [('parent_id', '=', parent.id)],
            order='sequence'
        )

        for child in children:
            new_code = f"{root_code}.{counter[0]}"

            child.write({
                'sequence': counter[0],
                'code': new_code,
            })

            counter[0] += 1

            # 🔁 sigue con nietos, pero SIN reiniciar counter
            self._resequential_flat(child, root_code, counter)

    @api.depends('part_ids')
    def _get_part_count(self):
        for rec in self:
            rec.part_count = len(rec.part_ids)

    @api.depends('parent_id')
    def _get_level(self):
        level = 1
        for record in self:
            parent = record.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            record.level = level

    @api.depends(
        'certification_stage_ids',
        'certification_stage_ids.stage_id',
        'certification_stage_ids.budget_qty',
        'certification_stage_ids.certif_qty',
        'certification_stage_ids.certif_percent',
        'certification_stage_ids.amount_budget',
        'certification_stage_ids.stage_state')
    def _compute_stage(self):
        for record in self:
            record.amount_stage_cert = sum(stage.certif_qty for stage in record.certification_stage_ids if stage.stage_state in ['process', 'approved'])

    @api.depends(
        'measuring_ids',
        'measuring_ids.qty',
        'measuring_ids.name',
        'measuring_ids.length',
        'measuring_ids.width',
        'measuring_ids.height',
        'measuring_ids.formula',
        'measuring_ids.space_id',
        'measuring_ids.stage_id')
    def _compute_measure(self):
        for record in self:
            record.amount_measure = sum(measure.amount_subtotal for measure in record.measuring_ids if measure.characteristic != 'null')
            record.amount_measure_cert = sum(me.amount_subtotal for me in record.measuring_ids if me.stage_id and me.stage_state in ['process', 'approved'] and me.characteristic != 'null')

    @api.depends(
        'code', 'type_cert', 'parent_id', 'update', 'parent_id.update',
        'budget_type', 'quantity_cert', 'amount_fixed_cert', 'amount_compute_cert')
    def _compute_amount_cert(self):
        for record in self:
            balance_cert = 0
            # if record.budget_type == 'certification':
            amount = record.amount_fixed_cert if record.type_cert == 'fixed' else record.amount_compute_cert

            if record.type in ['equip']:
                balance_cert = record.quantity_cert * amount / record.parent_id.performance if record.parent_id and record.parent_id.performance > 0 else record.quantity_cert * amount
            elif record.type in ['labor']:
                balance_cert = record.rec_total_labor * record.parent_id.quantity_cert / record.parent_id.performance if record.parent_id and record.parent_id.performance > 0 else record.quantity_cert * amount
            else:
                balance_cert = record.quantity_cert * amount


            if record.type == 'chapter':
                balance_cert = sum(child.balance_cert for child in record.child_ids)

            record.balance_cert = balance_cert

    @api.depends('quantity', 'type', 'amount_fixed', 'amount_compute', 'product_id', 'update', 'depreciation', 'amount_type')
    def _compute_amount(self):
        for record in self:
            price = record.amount_fixed if (record.type in ['labor', 'equip', 'material', 'subcontract'] or record.amount_type == 'fixed') else record.amount_compute

            if record.budget_id.type_calc == 'apu' and record.type in ['departure']:
                if record.assumed_price > 0:
                    apu_total = record.assumed_price
                else:
                    apu_total = record.apu_total

                record.balance = round(apu_total,2) * record.quantity
            else:
                if record.type in ['labor', 'equip'] and record.parent_id.performance > 0  and record.parent_id.hours_day > 0 and record.budget_id.type_calc == 'standard':
                    record.balance = record.quantity * price * record.parent_id.hours_day / record.parent_id.performance
                else:
                    record.balance = record.quantity * price

                if record.depreciation > 0:
                    record.balance = record.balance * record.depreciation

            if record.amount_type == 'fixed' and record.type in ['departure']:
                record.balance = record.amount_fixed * record.quantity

            if record.type in ['material'] and record.waste > 0:
                record.balance = record.balance * (1 + record.waste / 100)


            if record.use_utility:
                _utility = record.utility
            else:
                _utility = record.budget_id.utility

            if _utility > 0 and record.budget_id.type_calc == 'standard' :
                record.sale_price = price + price * _utility / 100
                record.sale_amount =   round(record.sale_price,2) * record.quantity
            else:
                record.sale_price = price
                record.sale_amount = record.balance


            if record.code and record.name:
                if "%" in record.code and "Transp" in record.name or "TRANSP" in record.name:
                    record.asset_type = "transport"

            if record.type in ['chapter'] and record.child_ids:
                record.sale_price = sum(l.sale_amount for l in record.child_ids)
                record.sale_amount = record.sale_price * record.quantity

    @api.depends(
        'child_ids.type',
        'child_ids.update',
        'child_ids.quantity',
        'child_ids.currency_id',
        'child_ids.product_id',
        'child_ids.amount_fixed',
        'opening_balance',
        'type', 'amount_fixed', 'product_id', 'parent_id', 'update', 'parent_id.update')
    def _compute_price(self):
        for record in self:
            price_pres = 0
            price_cert = 0

            # Presupuesto
            if record.type in ['labor', 'equip', 'material', 'aux', 'subcontract'] or record.amount_type == 'fixed':
                price_pres = record.amount_fixed
            else:
                if record.budget_id.type_calc == 'apu' and record.type in ['departure']:
                    price_pres = record.apu_total
                else:
                    price_pres = sum(l.balance for l in record.child_ids)

                # Recalculo funciones
                if any(l.id for l in record.child_ids if l.type == 'aux'):
                    for res in record.child_ids:
                        if res.type == 'aux':
                            res.onchange_function()

            # # Certificacion
            # if record.budget_type == 'certification':
            if record.type in ['labor', 'equip', 'material', 'subcontract']:
                price_cert = price_pres
            else:
                if record.type_cert == 'fixed':
                    price_cert = record.amount_fixed_cert if record.amount_fixed_cert != 0 else price_pres
                else:
                    price_cert = price_pres if record.type in ['departure', 'aux'] else sum(l.balance_cert for l in record.child_ids)
                    if record.sale_amount > 0:
                        price_cert = record.sale_price
                record.set_qty_cert_child()

            record.amount_compute = price_pres
            record.amount_compute_cert = price_cert

            if record.budget_id.type_calc in ['apu','apu-hh'] and record.type in ['departure']:
                if record.assumed_price > 0:
                    record.amount_compute = record.assumed_price
                else:
                    record.amount_compute = record.apu_total


    def _compute_execute(self):
        stock_obj = self.env['stock.picking']
        part_obj = self.env['bim.part']
        invoice_line_obj = self.env['account.move.line']
        attend_obj = self.env['hr.attendance']
        tool_obj = self.env['bim.tool.use']
        rent_obj = self.env['bim.tool.rent']
        for record in self:
            execute_equip = execute_labor = execute_material = executed = 0
            quantity = 1
            departure = record.get_departure_parent(record.parent_id)
            balance_execute = 0
            if record.type == 'material':
                if departure:
                    pickings = stock_obj.search([('bim_concept_id', '=', departure.id)])
                    for pick in pickings:
                        for move in pick.move_ids:
                            if move.product_id == record.product_id:
                                quantity += move.product_uom_qty
                                executed += move.product_cost * move.product_uom_qty if move.product_cost > 0 else record._get_value(move.product_uom_qty, move.product_id)

            elif record.type == 'labor':
                if departure:
                    for part in departure.part_ids.filtered_domain([('state','=','validated')]):
                        for line in part.lines_ids:
                            if line.resource_type == 'H' and line.name == record.product_id:
                                quantity += line.product_uom_qty
                                executed += line.price_subtotal

            elif record.type == 'equip':
                if departure:
                    for part in departure.part_ids.filtered_domain([('state','=','validated')]):
                        for line in part.lines_ids:
                            if line.resource_type == 'Q' and line.name == record.product_id:
                                quantity += line.product_uom_qty
                                executed += line.price_subtotal

                    rent_obj_search = rent_obj.search([
                                                        ('concept_id', '=', departure.id),
                                                        ('state', 'in', ['rented', 'finished']),
                                                       ])
                    if rent_obj_search:
                        for line in rent_obj_search.rent_line_ids:
                            if line.product_id == record.product_id:
                                quantity += line.product_uom_qty
                                executed += line.price_total

            elif record.type == 'aux':
                if departure:
                    total_indicators = departure.equip_amount_count + departure.labor_amount_count + departure.material_amount_count
                    executed = (departure.amount_execute / total_indicators * departure.aux_amount_count) if total_indicators else 0.0  # self.recursive_amount(record,record.parent_id,None)# #

            elif record.type == 'departure':
                pickings = stock_obj.search([('include_for_bim', '=', True),('bim_concept_id', '=', record.id),('picking_type_code','!=','incoming'),('returned','=',False),('state','=','done')])
                pickings += stock_obj.search([('include_for_bim', '=', True),('bim_concept_id', '=', record.id),('picking_type_code','=','incoming'),('returned','=',True),('state','=','done')])
                for pick in pickings:
                    factor = 1
                    if pick.picking_type_code == 'incoming' and pick.returned == True:
                        factor = -1

                    for move in pick.move_ids:
                        quantity += move.product_uom_qty * factor
                        executed += move.product_cost * move.product_uom_qty * factor if move.product_cost > 0 else record._get_value(move.product_uom_qty, move.product_id) * factor
                        execute_material += move.product_cost * move.product_uom_qty * factor if move.product_cost > 0 else record._get_value(move.product_uom_qty, move.product_id) * factor

                # Partes de Q o H
                parts = part_obj.search([('concept_id', '=', record.id),('state','=','validated')])
                for part in parts:
                    for line in part.lines_ids:
                        if line.resource_type == 'Q':
                            quantity += line.product_uom_qty
                            executed += line.price_subtotal
                            execute_equip += line.price_subtotal

                        elif line.resource_type == 'H':
                            quantity += line.product_uom_qty
                            executed += line.price_subtotal
                            execute_labor += line.price_subtotal

                # Tools
                rent_obj_search = rent_obj.search([
                    ('concept_id', '=', record.id),
                    ('state', 'in', ['rented', 'finished']),
                ])
                if rent_obj_search:
                    for line in rent_obj_search.rent_line_ids:
                        quantity += line.product_uom_qty
                        executed += line.price_total
                        execute_equip += line.price_total


                invoice_domain = [('display_type', '=', 'product'),
                                  ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
                                  ('move_id.state', '=', 'posted'),('move_id.include_for_bim', '=', True),('concept_id', '=', record.id)]
                invoice_lines = invoice_line_obj.search(invoice_domain)
                product_invoiced_price_total = 0
                for line in invoice_lines:
                    factor = 1
                    if line.move_id.move_type == 'in_refund':
                        factor = -1
                    if self.env.company.include_vat_in_indicators:
                        product_invoiced_price_total += line.price_total * factor
                    else:
                        product_invoiced_price_total += line.price_subtotal * factor
                execute_material += product_invoiced_price_total

                attendance_domain = [('concept_id', '=', record.id), ('check_out', '!=', False)]
                attendances = attend_obj.search(attendance_domain)
                attendance_cost = 0
                for attendance in attendances:
                    attendance_cost += attendance.attendance_cost
                execute_labor += attendance_cost
                
                #Herramientas
                tools = tool_obj.search([('concept_id','=',record.id)])
                tool_cost = 0
                for tool in tools:
                    tool_cost += tool.total
                execute_equip += tool_cost

            else:
                executed = 0
                for child in record.child_ids:
                    tmp = child.amount_execute
                    if child.type == 'departure' or child.type == 'chapter':
                        balance_execute += child.balance_execute
                    executed += tmp

            record.amount_execute_equip = execute_equip
            record.amount_execute_labor = execute_labor
            record.amount_execute_material = execute_material
            if record.type == 'chapter' and not record.parent_id:
                record.balance_execute = balance_execute
            else:
                record.balance_execute = execute_equip + execute_labor + execute_material
            # if executed > 0:
            #     record.amount_execute = executed
            # else:
            record.amount_execute = record.balance_execute
            child_executed = 0
            child_execute_equip = 0
            child_execute_labor = 0
            child_execute_material = 0
            child_balance_execute = 0
            child_opening_balance = 0
            if record.child_ids and record.parent_id:
                for child in record.child_ids:
                    child._compute_execute()
                    child_executed += child.amount_execute
                    child_execute_equip += child.amount_execute_equip
                    child_execute_labor += child.amount_execute_labor
                    child_execute_material += child.amount_execute_material
                    child_balance_execute += child.balance_execute
                    child_opening_balance += child.opening_balance + child.child_opening_balance

            record.child_amount_execute = child_executed
            record.child_amount_execute_equip = child_execute_equip
            record.child_amount_execute_labor = child_execute_labor
            record.child_amount_execute_material = child_execute_material
            record.child_opening_balance = child_opening_balance

            if record.type == 'chapter' and not record.parent_id:
                record.child_balance_execute = child_balance_execute
            else:
                record.child_balance_execute = child_execute_equip + child_execute_labor + child_execute_material

            record.amount_execute += record.child_amount_execute + record.opening_balance
            record.balance_execute += record.child_amount_execute + record.opening_balance

    sequence = fields.Integer('Sequence', default=1)
    display_name = fields.Char(compute='_compute_display_name', store=True, index=True)
    name = fields.Text("Name", required=True, index=True)
    code = fields.Char("Code", required=True, index=True)
    to_measure = fields.Boolean('Enter measurement')
    to_certify = fields.Boolean('Certification applies', compute="_get_valid_certification")
    auto_certify = fields.Boolean('Automatic Certification', compute="_get_valid_certification")
    manual_certify = fields.Boolean('Manual Certification', compute="_get_valid_certification")

    acs_date_start = fields.Datetime("Start Date", default=lambda self: self.budget_id.date_start)
    acs_date_end = fields.Datetime("End Date", default=lambda self: self.budget_id.date_start)

    duration = fields.Float('Duration (d)', digits='BIM Duration')
    level = fields.Integer(string='Level', compute="_get_level")
    picking_count = fields.Integer(string='Delivery N°', compute="_get_picking_count")
    part_count = fields.Integer(string='Part', compute="_get_part_count")
    note = fields.Text("Notes", default="")
    hito = fields.Boolean('Milestone')
    not_can_update_cost = fields.Boolean('Not Update Cost', default=False)

    budget_id = fields.Many2one('bim.budget', "Budget", required=True)
    parent_id = fields.Many2one('bim.concepts', "Parent")
    uom_id = fields.Many2one('uom.uom', string='UoM', domain="[]")
    product_id = fields.Many2one('product.product', "Product", ondelete='restrict')
    rubro_id = fields.Many2one('bim.rubro', string='Rubro', related='product_id.rubro_id', store=True)
    srubro_id = fields.Many2one('bim.rubro', string='Subrubro', related='product_id.srubro_id', store=True)


    virtual_product_id = fields.Many2one('virtual.product', "Virtual Product", ondelete='restrict')
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', required=True, readonly=True)

    filter_type_domain = fields.Char(compute='_compute_filter_type_domain',  help="Technical field used to have a dynamic domain in the form view.")
    filter_product_domain = fields.Char(compute='_compute_filter_product_domain')
    filter_product_domain_aux = fields.Char(compute='_compute_filter_product_domain')

    equip_amount_count = fields.Float('Total equipment')
    labor_amount_count = fields.Float('Total labor')
    material_amount_count = fields.Float('Total material')
    aux_amount_count = fields.Float('Total Function')
    subcontract_amount_counts = fields.Float('Total Subcontract Count')

    assumed_price = fields.Float('Precio Fijo', digits='BIM price')
    amount_assumed_price = fields.Float('IP Fijo', digits='BIM price', compute='_compute_amount_assumed_price', store=True)
    id_import = fields.Char('ID Import', copy=False, index=True)
    parent_id_import = fields.Char('Parent ID Import', copy=False, index=True)

    @api.depends('assumed_price', 'apu_total', 'quantity')
    def _compute_amount_assumed_price(self):
        for record in self:
            if record.assumed_price > 0:
                record.amount_assumed_price = (record.apu_total * record.quantity - record.assumed_price * record.quantity) * -1
            else:
                record.amount_assumed_price = 0



    def paste_apu(self):
        _logger.info('begin paste_apu')
        user = self.env.user
        _logger.info(user.concept_template_ids)
        _logger.info(user.concept_bim_concept_ids)
        _logger.info(user.copy_bim_budget_ids)

        # APUs
        if user.concept_template_ids:
            _logger.info('concept_template_ids')
            for apu in user.concept_template_ids:
                departure = self.child_ids.create({
                        'budget_id': self.budget_id.id,
                        'parent_id': self.id,
                        'name': apu.name,
                        'code': apu.code,
                        'type': 'departure',
                        'quantity': apu.quantity,
                        'uom_id': apu.uom_id.id if apu.uom_id else False,
                        'performance_type': apu.performance_type,
                        'hours_day': apu.hours_day,
                        'performance': apu.performance,
                        'note': apu.notes,
                        'concept_phase_id' : apu.concept_phase_id.id,
                        'sub_phase_id' : apu.sub_phase_id.id,
                        'concept_specialty_id' : apu.concept_specialty_id.id,
                        'concept_template_id': apu.id,
                })
                for line in apu.template_line_ids:
                    vals = {
                        'budget_id': departure.budget_id.id,
                        'parent_id': departure.id,
                        'name': line.name,
                        'code': line.code,
                        'quantity': line.quantity,
                        'amount_fixed': line.price,
                        'available': line.available,
                        'product_id': line.product_id.id if line.product_id else False,
                        'uom_id': line.uom_id.id if line.uom_id else False,
                        'type': CONCEPT_TYPE[line.type],
                    }
                    rec_ = departure.child_ids.create(vals)
                    if rec_.type == 'material':
                        rec_.waste = line.dep
                    elif rec_.type == 'equip':
                        rec_.depreciation = line.dep


        # Departures
        if user.concept_bim_concept_ids:
            _logger.info('concept_bim_concept_ids')
            for apu in user.concept_bim_concept_ids:
                if apu.type == 'departure':
                    departure = self.child_ids.create({
                            'budget_id': self.budget_id.id,
                            'parent_id': self.id,
                            'name': apu.name,
                            'code': apu.code,
                            'type': 'departure',
                            'quantity': apu.quantity,
                            'uom_id': apu.uom_id.id if apu.uom_id else False,
                            'performance_type': apu.performance_type,
                            'hours_day': apu.hours_day,
                            'performance': apu.performance,
                            'note': apu.note,
                            'concept_phase_id' : apu.concept_phase_id.id,
                            'sub_phase_id' : apu.sub_phase_id.id,
                            'concept_specialty_id' : apu.concept_specialty_id.id,
                            'concept_template_id': apu.concept_template_id.id,
                    })
                    for line in apu.child_ids:
                        vals = {
                            'budget_id': departure.budget_id.id,
                            'parent_id': departure.id,
                            'name': line.name,
                            'code': line.code,
                            'quantity': line.quantity,
                            'amount_fixed': line.amount_fixed,
                            'available': line.available,
                            'product_id': line.product_id.id if line.product_id else False,
                            'uom_id': line.uom_id.id if line.uom_id else False,
                            'type': line.type,
                        }
                        rec_ = departure.child_ids.create(vals)
                        if rec_.type == 'material':
                            rec_.waste = line.waste
                        elif rec_.type == 'equip':
                            rec_.depreciation = line.depreciation

        # Budgets
        if user.copy_bim_budget_ids:
            _logger.info('Budgets')
            for budget in user.copy_bim_budget_ids:
                _logger.info('Budget: %s', budget.name)
                for apu in budget.concept_ids:
                    if apu.type == 'departure':
                        departure = self.child_ids.create({
                                'budget_id': self.budget_id.id,
                                'parent_id': self.id,
                                'name': apu.name,
                                'code': apu.code,
                                'type': 'departure',
                                'quantity': apu.quantity,
                                'uom_id': apu.uom_id.id if apu.uom_id else False,
                                'performance_type': apu.performance_type,
                                'hours_day': apu.hours_day,
                                'performance': apu.performance,
                                'note': apu.note,
                                'concept_phase_id' : apu.concept_phase_id.id,
                                'sub_phase_id' : apu.sub_phase_id.id,
                                'concept_specialty_id' : apu.concept_specialty_id.id,
                                'concept_template_id': apu.concept_template_id.id,
                        })
                        for line in apu.child_ids:
                            vals = {
                                'budget_id': departure.budget_id.id,
                                'parent_id': departure.id,
                                'name': line.name,
                                'code': line.code,
                                'quantity': line.quantity,
                                'amount_fixed': line.amount_fixed,
                                'available': line.available,
                                'product_id': line.product_id.id if line.product_id else False,
                                'uom_id': line.uom_id.id if line.uom_id else False,
                                'type': line.type,
                            }
                            rec_ = departure.child_ids.create(vals)
                            if rec_.type == 'material':
                                rec_.waste = line.waste
                            elif rec_.type == 'equip':
                                rec_.depreciation = line.depreciation


        _logger.info('end paste_apu')
        user.concept_template_ids = False
        user.concept_bim_concept_ids = False
        user.copy_bim_budget_ids = False



    @api.depends('equip_amount_count', 'labor_amount_count', 'material_amount_count', 'aux_amount_count', 'subcontract_amount_counts')
    def _compute_resume_amount_count(self):
        for record in self:
            if record.amount_type == 'compute':
                record.resume_equip_amount_count = record.equip_amount_count / record.quantity if record.quantity > 0 else 0
                record.resume_labor_amount_count = record.labor_amount_count / record.quantity if record.quantity > 0 else 0
                record.resume_material_amount_count = record.material_amount_count / record.quantity if record.quantity > 0 else 0
                record.resume_aux_amount_count = record.aux_amount_count / record.quantity if record.quantity > 0 else 0
                record.resume_subcontract_amount_counts = record.subcontract_amount_counts / record.quantity if record.quantity > 0 else 0
            else:
                record.resume_equip_amount_count = 0
                record.resume_labor_amount_count = 0
                record.resume_material_amount_count = 0
                record.resume_aux_amount_count = record.balance / record.quantity if record.quantity > 0 else 0
                record.resume_subcontract_amount_counts = 0


    resume_equip_amount_count = fields.Monetary('Total equipment R', compute= _compute_resume_amount_count)
    resume_labor_amount_count = fields.Monetary('Total labor R', compute= _compute_resume_amount_count)
    resume_material_amount_count = fields.Monetary('Total Material R', compute= _compute_resume_amount_count)
    resume_aux_amount_count = fields.Monetary('Total Function R', compute= _compute_resume_amount_count)
    resume_subcontract_amount_counts = fields.Monetary('Res Total Subcontract R', compute= _compute_resume_amount_count)

    resume_hh = fields.Float('horas/hombres', digits='BIM qty')
    resume_dh = fields.Float('días/hombres', digits='BIM qty')
    resume_he = fields.Float('horas/equipo', digits='BIM qty')
    resume_de = fields.Float('días/equipo', digits='BIM qty')

    child_ids = fields.One2many('bim.concepts', 'parent_id', 'Childs')
    departure_child_count = fields.Integer(compute='sub_departure_child_count')
    measuring_ids = fields.One2many('bim.concept.measuring', 'concept_id', 'Measurement')
    options_ids = fields.One2many('bim.concept.options', 'concept_id', 'Options')

    certification_stage_ids = fields.One2many('bim.certification.stage', 'concept_id', 'Certification')
    concepts_image_ids = fields.One2many(comodel_name="bim.checklist.images", inverse_name="checklist_id", string="Checklist Images")
    attachment_ids = fields.Many2many('ir.attachment', string='Images')
    picking_ids = fields.One2many('stock.picking', 'bim_concept_id', 'Stock')
    part_ids = fields.One2many('bim.part', 'concept_id', 'Parts')
    bim_predecessor_concept_ids = fields.One2many('bim.predecessor.concept', 'concept_id', 'Predecessors')
    subcon = fields.Boolean("Sub Contract")
    id_bim = fields.Char("ID BIM")

    gantt_type = fields.Selection(related='budget_id.gantt_type')
    available = fields.Float('Availability', default=1, digits=(10, 2))
    day_price = fields.Monetary("Day Price")

    quantity = fields.Float("Quantity", default=1, digits='BIM qty')

    @api.depends('parent_id', 'type', 'quantity', 'parent_id.quantity')
    def compute_quantity_parent(self):
        for record in self:
            if record.parent_id:
                if record.type in ['labor', 'subcontract']:
                    record.quantity_parent = record.quantity * record.parent_id.quantity
                elif record.type in ['material', 'equip']:
                    record.quantity_parent = record.quantity * record.parent_id.quantity
                else:
                    record.quantity_parent = record.quantity


    quantity_parent = fields.Float("Cantidad P", digits='BIM qty' , compute='compute_quantity_parent', store=True)
    depreciation = fields.Float(default=1.0, digits=(10, 6))
    indirect = fields.Boolean("Indirect")
    weight = fields.Float('Weight', compute="_compute_weight", store=True, digits=(10, 2))
    balance = fields.Float(string='Balance', compute="_compute_amount", store=True, digits='BIM price')
    amount_fixed = fields.Float("Cost", digits='BIM price')
    amount_compute = fields.Float("Calculated Price", compute="_compute_price", store=True, digits='BIM price')
    amount_measure = fields.Float("Total Quantity", compute="_compute_measure", store=True)
    budget_type = fields.Selection(related='budget_id.type', store=True, readonly=True)
    property_ids = fields.Many2many('real.estate.property', string='Properties')

    rec_total_days = fields.Float('Total Días', readonly=True)
    rec_total_hh = fields.Float('Total HH', readonly=True)
    rec_tota_bonus = fields.Float('Total Bonos', readonly=True)
    rec_ben_sociales = fields.Float('R Beneficios Sociales', readonly=True)
    rec_total_labor = fields.Float('Importe MO', readonly=True)

    subcontract_type = fields.Selection([
        ('service', 'Service'),
        ('rent', 'Rent')
        ], default='service')

    update = fields.Selection([
        ('stop', 'Stop'),
        ('start', 'Start')], default='stop')

    amount_type = fields.Selection([
        ('compute', 'Calculated'),
        ('fixed', 'Manual'),
        ('locked', 'Lock')], string="Price Type", default='compute')



    type = fields.Selection([
        ('chapter', 'CHAPTER'),
        ('departure', 'BUDGET ITEM'),
        ('labor', 'LABOR'),
        ('equip', 'EQUIPMENT'),
        ('material', 'MATERIAL'),
        ('aux', 'FUNCTION / ADMINISTRATIVE'),
        ('subcontract', 'SUBCONTRACT')], string="Concept Type")

    type_error = fields.Selection([
            ('no-error', 'no-error'),
            ('chapter-mat', 'chapter-mat'),
            ('departure-departure', 'departure-departure'),
            ('mat-other', 'mat-other'),
        ]
        , default='no-error')

    # Ejecucion
    amount_execute = fields.Float("Exec Price", digits='BIM price', store=True)
    opening_balance = fields.Float("Opening Balance", digits='BIM price', store=True, compute='compute_opening_balance')
    child_opening_balance = fields.Float("Child Opening Balance", digits='BIM price', store=True)
    child_amount_execute = fields.Float("Child Exec Price", digits='BIM price', store=True)
    qty_execute = fields.Float("Qty Execute",  digits='BIM qty E')
    balance_execute = fields.Monetary(string="Exec balance", store=True)
    balance_execute_percent = fields.Monetary('(%) Cost', compute='_compute_balance_execute_percent')
    balance_execute_profit = fields.Monetary('Profit', compute='_compute_balance_execute_profit')
    child_balance_execute = fields.Monetary(string="Exec balance Child", store=True)
    amount_execute_equip = fields.Monetary('Exec equipment', store=True)
    amount_execute_labor = fields.Monetary('Exec labor', store=True)
    amount_execute_material = fields.Monetary('Exec material', store=True)
    # Hijos
    child_amount_execute_equip = fields.Monetary('Exec equipment Child', store=True)
    child_amount_execute_labor = fields.Monetary('Child Exec labor Child', store=True)
    child_amount_execute_material = fields.Monetary('Exec material Child', store=True)

    # Certificacion
    amount_fixed_cert = fields.Monetary("Cert Price", copy=False)
    amount_compute_cert = fields.Float("Cert Calculated Price", compute="_compute_price", copy=False, store=True)
    balance_cert = fields.Monetary(string="Cert Balance", compute="_compute_amount_cert", store=True, copy=False)
    quantity_cert = fields.Float("Cert Quant", default=0, digits='BIM qty', copy=False)
    amount_measure_cert = fields.Float("Total Certification x measures", compute="_compute_measure", digits='BIM qty', copy=False, store=True)
    amount_stage_cert = fields.Float("Total Stages", compute="_compute_stage", digits='BIM qty', copy=False)
    percent_cert = fields.Float("(%) Quant Budget", default=0, copy=False)
    type_cert = fields.Selection([
        ('measure', 'Measurement'),
        ('stage', 'Stages'),
        ('fixed', 'Manual')], string="Certification Type", default='measure', copy=False)
    export_tmp_id = fields.Integer()
    opening_balance_ids = fields.One2many('bim.opening.balance', 'concept_id', 'Opening Balances')
    project_id = fields.Many2one('bim.project', related='budget_id.project_id', store=True)
    project_part = fields.Boolean(related='budget_id.state_id.project_part')
    company_id = fields.Many2one('res.company', related='budget_id.company_id')
    performance_calculation = fields.Boolean(related='company_id.performance_calculation')
    performance_type = fields.Selection([('hours','Hours'),('days','Days')], default='days')
    hours_day = fields.Integer(default=lambda self: self.env.company.working_hours)
    performance = fields.Float(string='Performance', digits="BIM Performance")
    compute_performance = fields.Float(compute='_compute_performance_method', store=True, default=False, digits="BIM qty")
    concept_template_id = fields.Many2one('bim.concept.template')
    concept_template_line_id = fields.Many2one('bim.concept.template.line', ondelete='restrict')
    allow_certification = fields.Boolean(related='budget_id.state_id.allow_certification')
    param_attribute_ids = fields.One2many('bim.concepts.parameter.attribute', 'concept_id')
    show_virtual_product = fields.Boolean('Show Virtual Product')
    asset_type = fields.Selection([('transport','Transport'),('benefits','Social benefits')])
    utility = fields.Float('Utility (%)', related='budget_id.utility')
    sale_price = fields.Float('Price', digits='BIM price')
    sale_amount = fields.Float('Sale Amount', digits='BIM price')
    budget_parent_id = fields.Many2one('bim.budget', string='Parent Budget', related='budget_id.parent_id', store=True)
    bim_concept_id = fields.Many2one('bim.concepts', string='Concept', ondelete='cascade')
    brigade_ids = fields.Many2many('bim.resource.template', string='Brigades')
    bim_concept_parent_ids = fields.One2many('bim.concept.parent', 'concept_id', 'Measurement Parents')


    # ------------------------- APUs -------------------------------#

    apu_total_materials = fields.Float('Total Materials')
    apu_total_transport = fields.Float('Total Transport')
    apu_total_equipment = fields.Float('Total Equipment')
    apu_total_labor = fields.Float('Total Labor')

    apu_duration = fields.Float('Apu Duration (hr)')
    apu_equipment = fields.Float('Apu Equipment')
    apu_labor = fields.Float('Apu Labor')

    apu_total_labor_indirect = fields.Float('Total Labor Indirect')
    apu_social_benefit = fields.Float('Social Benefit')
    apu_foot_bonus = fields.Float('Apu Bono')
    waste = fields.Float('Waste (%)')
    apu_waste = fields.Float('Waste')
    apu_total_bonus = fields.Float('Total Alimentación')
    apu_total_all_labor = fields.Float('Total All Labor')
    apu_total_all_subcontract = fields.Float('Total All Subcontract')
    apu_direct_cost = fields.Float('Direct Cost')

    apu_subtota_b = fields.Float('Subtotal B')
    # default budget_id utility
    apu_utility = fields.Float('Utility')
    apu_administration = fields.Float('Administration')

    apu_utility_t = fields.Float('Utilidad T.')
    apu_administration_t = fields.Float('Administración T.')



    show_utility_tree = fields.Float('Utilidad %', compute='_compute_show_utility_tree')
    apu_financing = fields.Float('Financiamiento')
    apu_total = fields.Float('Total')

    apu_day_duration = fields.Float('Duración en Días')
    apu_men_hours = fields.Float('Horas Hombre')
    hh_unid = fields.Float('HH/Unid')
    company_id = fields.Many2one('res.company', related='budget_id.company_id', store=True)

    use_foot_bonus = fields.Boolean(string='Usar Bono')
    foot_bonus = fields.Float(string='Bono')

    use_utility = fields.Boolean(string='Usar Utilidad')
    utility = fields.Float(string='Utilidad')

    use_administration = fields.Boolean(string='Usar Administración')
    administration = fields.Float(string='Administración')

    use_social_benefits = fields.Boolean(string='Usar Beneficios Sociales')
    social_benefits = fields.Float(string='Beneficios Sociales')

    stage_id = fields.Many2one('bim.budget.stage', "Stage")

    type_calc = fields.Selection(string="type of calculation", related='budget_id.type_calc', store=True)


    qty_total_material = fields.Float('Cantidad Total',
                                      help="Calcula la cantidad diviendo este campo por la cantidad en la partida que lo contiene.")

    concept_phase_id = fields.Many2one('concept.phase', string='Phase')
    sub_phase_id = fields.Many2one('concept.phase', string='Sub Phase')
    concept_specialty_id = fields.Many2one('concept.specialty', string='Specialty')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    ipp = fields.Float('IPP', compute='_compute_ipp', help="Indice de Productividad del Presupuesto", store=True)
    type_contract = fields.Selection([
        ('contract', 'Contract'),
        ('increases', 'Increases'),
        ('extras', 'Extras'),
        ('reduction', 'Reduction'),
        ('studies', 'Studies'),
        ('final', 'Final')],
        string='Type Contract', default='contract', required=True)


    def create_apu(self):
        bim_concept_template_id = self.env['bim.concept.template'].search([('code', '=', self.code)])
        if bim_concept_template_id:
            raise UserError("Ya existe un concepto con el mismo código en la plantilla de conceptos.")

        values = {
            'name': self.name,
            'code': self.code,
            'quantity': 1,
            'type_calc': self.budget_id.type_calc,
            'performance': self.performance,
            'uom_id': self.uom_id.id,
        }

        new_bim_concept_template_id = self.env['bim.concept.template'].create(values)

        if new_bim_concept_template_id:
            for child in self.child_ids:
                type = 'A'
                if child.type == 'labor':
                    type = 'H'
                elif child.type == 'equip':
                    type = 'Q'
                elif child.type == 'material':
                    type = 'M'

                quantity = child.quantity

                print('quantity', quantity)

                values = {
                    'template_id': new_bim_concept_template_id.id,
                    'type': type,
                    'code': child.code,
                    'name': child.name,
                    'product_id': child.product_id.id,
                    'uom_id': child.uom_id.id,
                    'quantity': quantity,
                    'price': child.amount_fixed,
                }

                print('values', values)

                self.env['bim.concept.template.line'].create(values)


    @api.depends('labor_amount_count', 'quantity', 'type')
    def _compute_ipp(self):
        for record in self:
            if record.type in ['departure'] and record.quantity > 0:
                total_hh = sum(record.child_ids.filtered_domain([('type','=','labor')]).mapped('quantity')) * record.quantity
                record.ipp = total_hh / record.quantity
            else:
                record.ipp = 0


    def calc_cost_from_price(self):
        for record in self:
            if record.amount_type == 'fixed':
                if record.use_utility and record.utility > 0:
                    _utility = record.utility
                else:
                    _utility = record.budget_id.utility

                if _utility > 0:
                    record.amount_fixed = record.sale_price / (1 + _utility / 100)
                else:
                    record.amount_fixed = record.sale_price
            else:
                raise UserError("Esta partida no es de tipo manual, no le puedes actualizar el coste.")

    def _compute_show_utility_tree(self):
        for record in self:
            if not record.type in ['chapter']:
                if record.use_utility and record.utility > 0:
                    record.show_utility_tree = record.utility
                else:
                    record.show_utility_tree = record.budget_id.utility
            else:
                if record.balance > 0:
                    record.show_utility_tree = (record.sale_amount - record.balance)/record.balance * 100
                else:
                    record.show_utility_tree = 0


    # onchange qty_total_material
    @api.onchange('qty_total_material')
    def _onchange_qty_total_material(self):
        if self.qty_total_material > 0:
            if self.parent_id.quantity > 0:
                self.quantity = self.qty_total_material / self.parent_id.quantity

    def calculate_apu(self):
        self._compute_apu_total_materials()
        self._compute_apu_total_transport()
        self._compute_apu_total_equipment()
        self._compute_apu_total_labor()
        self._compute_apu_total_labor_indirect()
        self._compute_apu_total_all_subcontract()
        self._compute_apu_social_benefit()
        self._compute_apu_total_bonus()
        self._compute_apu_total_all_labor()
        self._compute_apu_direct_cost()
        self._compute_apu_administration()
        self._compute_apu_subtota_b()
        self._compute_apu_utility()
        self._compute_apu_financing()
        self._compute_apu_total()

        if self.quantity > 0:
            self.apu_day_duration = self.performance / self.quantity
        else:
            self.apu_day_duration = 1

        domain = [('type','=','labor')]
        number_men = sum(self.child_ids.filtered_domain(domain).mapped('quantity'))
        self.apu_men_hours = self.apu_day_duration * self.hours_day * number_men

        if self.quantity > 0:
            self.hh_unid = self.apu_men_hours / self.quantity
        else:
            self.hh_unid = 0


    def _compute_apu_total_materials(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type','=','material')]
                record.apu_total_materials = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
            else:
                record.apu_total_materials = 0

    def _compute_apu_total_transport(self):
        for record in self:
            record.apu_total_transport = 0
        """
        for record in self:
            if record.type == 'departure':
                domain = [('asset_type','=','transport')]
                record.apu_total_transport = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
            else:
                record.apu_total_transport = 0
                """

    def _compute_apu_total_equipment(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type','=','equip')]
                record.apu_total_equipment = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
            else:
                record.apu_total_equipment = 0

            if record.type_calc == 'apu-hh':
                record.apu_equipment = record.apu_total_equipment * record.apu_duration


    def _compute_apu_total_all_subcontract(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type','=','subcontract')]
                record.apu_total_all_subcontract = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
            else:
                record.apu_total_all_subcontract = 0


    def _compute_apu_total_labor_indirect(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type','=','labor'),('indirect','=',True)]
                record.apu_total_labor_indirect = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
            else:
                record.apu_total_labor_indirect = 0

    def _compute_apu_total_labor(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type','=','labor'),('indirect','=',False)]
                record.apu_total_labor = sum(record.child_ids.filtered_domain(domain).mapped('balance'))
                apu_duration = sum(record.child_ids.filtered_domain(domain).mapped('quantity'))
                if record.type_calc == 'apu-hh':
                    if record.performance > 0:
                        record.apu_duration = record.performance / apu_duration if apu_duration > 0 else 1
                    else:
                        record.apu_duration = 1
                    record.apu_labor = record.apu_total_labor * record.apu_duration
            else:
                record.apu_total_labor = 0

    def _compute_apu_social_benefit(self):
        for record in self:
            if record.type == 'departure':
                domain = [('type', '=', 'labor')]
                child_ids = record.child_ids.filtered_domain(domain)
                if record.use_social_benefits:
                    record.apu_social_benefit = record.social_benefits * record.apu_total_labor / 100
                    for child in child_ids:
                        child.rec_ben_sociales = child.balance * record.apu_social_benefit / 100

                else:
                    record.apu_social_benefit = record.budget_id.social_benefits * record.apu_total_labor / 100
                    for child in child_ids:
                        child.rec_ben_sociales = child.balance * record.budget_id.social_benefits / 100
            else:
                record.apu_social_benefit = 0


    def _compute_apu_total_bonus(self):
        for record in self:
            if record.type == 'departure':
                if record.use_foot_bonus:
                    foot_bonus = record.foot_bonus
                else:
                    foot_bonus = record.budget_id.foot_bonus
                domain = [('type', '=', 'labor')]
                child_ids = record.child_ids.filtered_domain(domain)
                apu_foot_bonus = 0
                for child in child_ids:
                    if child.foot_bonus > 0 and not record.use_foot_bonus:
                        foot_bonus = child.foot_bonus
                    apu_foot_bonus += foot_bonus * child.quantity
                    child.rec_tota_bonus = foot_bonus * child.quantity

                record.apu_foot_bonus = apu_foot_bonus
                record.apu_total_bonus = record.apu_foot_bonus
            else:
                record.apu_total_bonus = 0



    def _compute_apu_total_all_labor(self):
        for record in self:
            if record.type == 'departure':
                record.apu_total_all_labor = record.apu_total_labor + record.apu_total_labor_indirect + record.apu_social_benefit + record.apu_total_bonus
            else:
                record.apu_total_all_labor = 0


    def _compute_apu_direct_cost(self):
        for record in self:
            if record.type == 'departure':
                if not record.type_calc == 'apu-hh':
                    if record.performance > 0:
                        record.apu_direct_cost = record.apu_total_all_subcontract + record.apu_total_materials + record.apu_total_transport + record.apu_total_equipment/record.performance + record.apu_total_all_labor/record.performance
                    else:
                        record.apu_direct_cost = record.apu_total_all_subcontract + record.apu_total_materials + record.apu_total_transport + record.apu_total_equipment + record.apu_total_all_labor
                else:
                    record.apu_direct_cost = record.apu_total_all_subcontract + record.apu_total_materials + record.apu_total_transport + record.apu_equipment + record.apu_labor

            else:
                record.apu_direct_cost = 0


    def _compute_apu_administration(self):
        for record in self:
            if record.type == 'departure':
                if self.use_administration:
                    administration_percent = record.administration
                else:
                    administration_percent = record.get_departure_budget_asset_percent([('asset_id.desc','in',('Administration','Administracion','Administración','Gastos Administración','Administración y Gastos Generales'))])

                record.apu_administration = administration_percent * record.apu_direct_cost / 100
                record.apu_administration_t = round(record.apu_administration,2) * record.quantity
            else:
                record.apu_administration = 0


    def _compute_apu_subtota_b(self):
        for record in self:
            if record.type == 'departure':
                record.apu_subtota_b = record.apu_direct_cost + record.apu_administration
            else:
                record.apu_subtota_b = 0


    def _compute_apu_financing(self):
        for record in self:
            if record.type == 'departure':
                _f = record.get_departure_budget_asset_percent([('asset_id.desc','in',('FINANCIAMIENTO','Financiamiento','Financing'))])
                record.apu_financing= _f * record.apu_subtota_b / 100
            else:
                record.apu_financing = 0



    def _compute_apu_utility(self):
        for record in self:
            if record.type == 'departure':
                # departure.get_departure_budget_asset_percent([('asset_id.desc','in',('Utility','Utilidad'))])
                if record.use_utility:
                    _utility = record.utility
                else:
                    if record.budget_id.utility > 0:
                        _utility = record.budget_id.utility
                    else:
                        _utility = record.get_departure_budget_asset_percent([('asset_id.desc','in',('Utility','Utilidad'))])
                record.apu_utility = _utility * record.apu_subtota_b / 100
                record.apu_utility_t = round(record.apu_utility,2) * record.quantity
            else:
                record.apu_utility = 0


    def _compute_apu_total(self):
        for record in self:
            if record.type == 'departure':
                record.apu_total = record.apu_subtota_b + record.apu_utility + record.apu_financing
            else:
                record.apu_total = 0



    # ------------------------- APUs -------------------------------#

    # ----------------------------------------------------------------#
    # ---------------- ONCHANGE METHODS ------------------------------#
    # ----------------------------------------------------------------#

    @api.onchange('virtual_product_id')
    def _onchange_virtual_product_id(self):
        if self.virtual_product_id:
            self.name = self.virtual_product_id.name
            self.amount_fixed = self.virtual_product_id.purchase_price

    @api.onchange('hours_day')
    def onchange_hours_day(self):
        if self.hours_day <= 0 and self.performance_type == 'days':
            raise UserError(_("Day hours can not be zero or less!"))

    @api.onchange('day_price')
    def onchange_day_price(self):
        self.amount_fixed = self.day_price / self.hours_day


    @api.onchange('performance_type')
    def onchange_performance_type(self):
        if self.company_id:
            self.hours_day = self.company_id.working_hours

    @api.depends('performance','available','hours_day','performance_type')
    def _compute_performance_method(self):
        for concept in self:
            if concept.company_id.calc_performance:
                concept.compute_performance = False
                factor = False
                if concept.type == 'departure' and concept.performance_calculation:
                    if concept.performance_type == 'hours':
                        factor = concept.performance
                    elif concept.performance_type == 'days' and concept.hours_day > 0:
                        factor = concept.performance / concept.hours_day
                    if factor and factor != 0:
                        for resource in concept.child_ids.filtered_domain([('type','in',('equip','labor'))]):
                            resource.quantity = resource.available / factor
                elif concept.type in ('labor','equip') and concept.performance_calculation:
                    if concept.parent_id.performance_type == 'hours':
                        factor = concept.parent_id.performance
                    elif concept.parent_id.performance_type == 'days' and concept.parent_id.hours_day > 0:
                        factor = concept.parent_id.performance / concept.parent_id.hours_day
                    if factor and factor != 0:
                        concept.quantity = concept.available / factor

    @api.depends('child_ids')
    def sub_departure_child_count(self):
        for record in self:
            record.departure_child_count = len(record.child_ids.filtered_domain([('type','=','departure')]))

    @api.onchange('type')
    def onchange_concept_type(self):
        if self.parent_id.type == 'chapter' and self.type in ['labor', 'equip', 'material', 'aux']:
            self.type_error = 'chapter-mat'

        elif self.parent_id.type in ['labor', 'equip', 'material', 'aux']:
            self.type_error = 'mat-other'

        else:
            self.type_error = 'no-error'

        if self.type == 'chapter' and self.parent_id.id != False and self.parent_id.type != 'chapter':
            raise UserError(_('It is not possible to add a Chapter as child of other concept of type Chapter as well'))

        if not self.acs_date_start and self.budget_id:
            self.acs_date_start = self.budget_id.date_start

        if self.name == False:
            self.amount_type = 'compute'

            if self.type == 'departure':
                self.amount_type = self.env.user.company_id.amount_type


    @api.depends('measuring_ids', 'amount_measure', 'amount_measure_cert')
    @api.onchange('measuring_ids')
    def onchange_qty(self):
        for record in self:
            if record.measuring_ids:
                record.quantity = abs(record.amount_measure)
                if record.type_cert == 'measure':
                    record.quantity_cert = abs(record.amount_measure_cert)

    @api.depends('certification_stage_ids', 'amount_stage_cert')
    @api.onchange('certification_stage_ids')
    def onchange_stage(self):
        for record in self:
            record.quantity_cert = record.amount_stage_cert

    @api.onchange('amount_type')
    def onchange_amount_type(self):
        # Inicializando Price Presupuesto en tipo Manual
        if self.amount_type == 'fixed' and self.amount_fixed != self.amount_compute:
            self.amount_fixed = self.amount_compute

    @api.depends('amount_compute_cert', 'amount_compute')
    @api.onchange('type_cert')
    def onchange_type_cert(self):
            # Inicializando Price certificacion en tipo Manual
        if self.type_cert == 'fixed' and self.amount_fixed_cert != self.amount_compute_cert:
            self.amount_fixed_cert = self.amount_compute_cert

        if self.type_cert == 'stage':
            self.generate_stage_list()

    @api.onchange('parent_id')
    def onchange_parent(self):
        if self.parent_id:
            obj = self.env['bim.concepts'].search([('parent_id', '=', self.parent_id.id)])
            last = len(obj)
            self.code = self.parent_id.code + "." + str(last+1)


    def create_product_from_vp(self):
        virtual_product = self.virtual_product_id
        product_convert = self.env['product.product']
        if not virtual_product.product_id:
            product_data = {
                "name": virtual_product.name,
                "default_code": virtual_product.reference,
                "barcode": virtual_product.barcode,
                "list_price": virtual_product.sales_price,
                "standard_price": virtual_product.purchase_price,
                "type": "product",
            }
            new_product = product_convert.sudo().create(product_data)
            virtual_product.product_id = new_product.id
        else:
            new_product = virtual_product.product_id

        virtual_product.convert_pp = True
        self.product_id = new_product.id
        self.virtual_product_id = False
        self.show_virtual_product = False
        self.amount_fixed = new_product.standard_price


    @api.onchange('stage_id')
    def onchange_stage_id(self):
        _logger.info('onchange_stage_id')
        if self.stage_id:
            self.acs_date_start = self.stage_id.date_start
            self.acs_date_end = self.stage_id.date_stop

    def resource_execution_dates(self):
        days = []
        if self.type in ('labor','equip'):
            date_start = self.parent_id.acs_date_start
            date_end = self.parent_id.acs_date_end
            while date_start <= date_end:
                date_start = datetime(date_start.year, date_start.month, date_start.day,00,00,00)
                days.append(datetime.strftime(date_start, '%Y-%m-%d'))
                date_start += timedelta(days=1)
        return days
    def is_day_in_execution_dates(self, date):
        return date in self.resource_execution_dates()


    @api.depends('code', 'parent_id', 'sequence')
    @api.onchange('type', 'code', 'sequence')
    def onchange_function(self):
        # Inicializacion de certificacion para recurso hijo de capitulo
        if self.type in ['labor', 'equip', 'material'] and self.parent_id.type == 'chapter':
            self.type_cert = 'fixed'

        # Validacion de orden de tipos
        elif self.type == 'chapter':
            self.quantity = 1
            if self.measuring_ids:
                self.measuring_ids = [(5,)]

        # Certificacion de Funciones
        elif self.type == 'aux':
            self.type_cert = 'measure' if self.auto_certify else 'fixed'
            if not self.uom_id:
                self.uom_id = self.env.ref('base_bim_2.product_uom_percent', raise_if_not_found=False)

            if self.code and '%' in self.code:
                concepts_to_check = self.parent_id.child_ids
                pos = self.code.find('%')
                concept_type = False
                if "*" in self.code:
                    pos = self.code.find('*')
                    concept_type = self.code[pos+1:pos+2]
                    if concept_type in CONCEPT_TYPES.keys():
                        concepts_to_check = concepts_to_check.filtered_domain([('type','=',CONCEPT_TYPES.get(concept_type))])
                if pos == 0 or concept_type:
                    afecto = sum(child.balance for child in concepts_to_check if child.sequence < self.sequence)
                    afecto_cert = sum(child.balance_cert for child in concepts_to_check if child.sequence < self.sequence)
                else:
                    pre = self.code[:pos]
                    afecto = sum(child.balance for child in concepts_to_check if child.sequence < self.sequence and child.code.find(pre) == 0)
                    afecto_cert = sum(child.balance_cert for child in concepts_to_check if child.sequence < self.sequence and child.code.find(pre) == 0)
                self.quantity = afecto * 0.01

                if self.auto_certify:
                    self.percent_cert = (afecto_cert / afecto) * 100 if afecto > 0 else self.parent_id.percent_cert

            else:
                self.type_cert = 'fixed'
                afecto = sum(child.balance for child in self.parent_id.child_ids if child.sequence < self.sequence)
                afecto_cert = sum(child.balance for child in self.parent_id.child_ids if child.sequence < self.sequence)
                if self.quantity == 0:
                    self.quantity = afecto * 0.01

                if self.auto_certify:
                    self.percent_cert = (afecto_cert / afecto) * 100 if afecto > 0 else self.parent_id.percent_cert

            if self.code and '#' in self.code:
                afecto = self.budget_id.balance - self.balance
                afecto_cert = sum(concept.balance_cert for concept in self.budget_id.concept_ids.filtered(lambda c: c.type == 'chapter'))
                self.quantity = afecto * 0.01
                self.percent_cert = ((afecto_cert - self.balance_cert) / afecto) * 100


    @api.onchange('name','code')
    def onchange_name(self):
        for record in self:
            if record.code and record.name:
                if "%" in record.code and "Transp" in record.name or "TRANSP" in record.name:
                    record.asset_type = "transport"
            if record.name and not record.uom_id and record.type in ['departure']:
                obj_uom = self.env['uom.uom'].search([('default_bim_unit','=',True)], limit=1)
                if obj_uom:
                    record.uom_id = obj_uom.id


    @api.onchange('product_id')
    def onchange_product(self):
        self.subcon = self.product_id.sub_contract
        self.name = self.product_id.name
        self.code = self.product_id.default_code or self.code
        self.uom_id = self.product_id.uom_id.id
        self.id_bim = self.product_id.id_bim
        self.depreciation = self.product_id.depreciation

        if self.type in ['labor']:
            self.foot_bonus = self.product_id.bonus

        if self.product_id.resource_type == 'P':
            self.show_virtual_product = True
        else:
            self.show_virtual_product = False

        if self.type in ['labor', 'equip', 'material','subcontract']:
            find = False
            if self.budget_id.project_id.price_agreed_ids:
                for product in self.budget_id.project_id.price_agreed_ids:
                    if self.product_id.id == product.product_id.id:
                        self.amount_fixed = product.price_agreed
                        find = True
                        break
            if not find and self.product_id:
                if self.env.company.type_work == 'pricelist':
                    pricelist = self.budget_id.pricelist_id
                    product_context = dict(self.env.context, partner_id=self.budget_id.project_id.customer_id.id, date=self.budget_id.date_start, uom=self.uom_id.id)
                    price = pricelist.with_context(product_context)._get_product_price(self.product_id, self.quantity or 1.0)
                    self.amount_fixed = pricelist.with_context(product_context)._get_product_price(self.product_id, self.quantity or 1.0)
                elif self.env.company.type_work == 'costlist':
                    if self.budget_id.cost_list_id:
                         product_cost = self.budget_id.cost_list_id._get_product_bim_cost_list(self.product_id)
                         if product_cost:
                             self.amount_fixed = product_cost
                         else:
                             self.amount_fixed = self.product_id.standard_price
                    else:
                        self.amount_fixed = self.product_id.standard_price
                elif self.env.company.type_work == 'cost':
                    self.amount_fixed = self.product_id.standard_price
                else:
                    self.amount_fixed = self.product_id.lst_price





    @api.depends('percent_cert', 'type_cert', 'amount_measure_cert', 'quantity_cert')
    @api.onchange('quantity_cert', 'type_cert')
    def onchange_qty_certification(self):
        for record in self:
            # Porcentaje (%) Nivel actual y padre
            if record.quantity > 0:
                record.percent_cert = (record.quantity_cert / record.quantity) * 100

    @api.depends('percent_cert', 'quantity', 'amount_measure_cert', 'amount_stage_cert')
    @api.onchange('percent_cert', 'type_cert')
    def onchange_percent_certification(self):
        for record in self:
            if record.type_cert == 'stage':
                record.quantity_cert = record.amount_stage_cert
            elif record.type_cert == 'measure':
                record.quantity_cert = record.amount_measure_cert
            else:
                record.quantity_cert = (record.quantity * record.percent_cert) / 100

            if record.auto_certify:
                record.quantity_cert = (record.quantity * record.percent_cert) / 100

    @api.depends('opening_balance_ids.amount','opening_balance_ids.active')
    def compute_opening_balance(self):
        for record in self:
            balance = 0
            for balance_rec in record.opening_balance_ids.filtered_domain([('active','=',True)]):
                balance += balance_rec.amount
            record.opening_balance = balance

    def _compute_balance_execute_percent(self):
        for record in self:
            record.balance_execute_percent = (record.balance_execute / record.balance) if record.balance else 0

    def _compute_balance_execute_profit(self):
        for record in self:
            record.balance_execute_profit = record.balance - record.balance_execute

    # --------------------------------------------------------------#
    # ---------------- MODELS METHODS ------------------------------#
    # --------------------------------------------------------------#

    def name_get(self):
        reads = self.read(['name', 'code'])
        res = []
        for record in reads:
            name = record['name']
            if record['code']:
                name = record['code'] + ' ' + name
            res.append((record['id'], name))
        return res

    def write(self, vals):
        res = super(BimConcepts, self).write(vals)
        for concept in self:
            concept._check_bugdet_lock()
        if 'sequence' in vals:
            for concept in self:
                concept.onchange_function()
        return res

    def update_amount(self):
        for record in self:
            record.onchange_dates()
            if record.budget_id.type_calc in ['apu', 'apu-hh']:
                record.calculate_apu()
                record._compute_amount_assumed_price()


            record._compute_price()
            record._compute_amount()
            record._compute_execute()
            record._compute_ipp()

            if record.to_certify:
                record._compute_amount_cert()
                record.onchange_qty_certification()
                record.onchange_percent_certification()
            else:
                if not record.balance or float_is_zero(record.balance, precision_rounding=record.currency_id.rounding):
                    record.percent_cert = 0.0
                else:
                    record.percent_cert = (record.balance_cert / record.balance) * 100
                record.quantity_cert = (record.quantity * record.percent_cert) / 100

            # Calcular los totales por tipo
            material = 0
            labor = 0
            equip = 0
            aux = 0
            subcontract = 0

            if record.amount_type == 'compute':
                if record.budget_id.type_calc == 'standard':
                    for child in self.child_ids:
                        child.update_amount()
                        if child.type == 'material':
                            material += child.balance
                        elif child.type == 'labor':
                            labor += child.balance
                        elif child.type == 'equip':
                            equip += child.balance
                        elif child.type == 'aux':
                            aux += child.balance
                        elif child.type == 'subcontract':
                            subcontract += child.balance

                    # AUX
                    record.aux_amount_count = aux * record.quantity

                    # MATERIAL
                    record.material_amount_count = material * record.quantity

                    # LABOR
                    labor = labor * record.quantity
                    record.labor_amount_count = labor




                    # EQUIPMENT
                    equip = equip * record.quantity
                    record.equip_amount_count = equip

                    # SUNCONTRACT
                    record.subcontract_amount_counts =subcontract * record.quantity

                else:
                    record.aux_amount_count = 0
                    record.material_amount_count = record.apu_total_materials * record.quantity
                    record.subcontract_amount_counts = record.apu_total_all_subcontract * record.quantity
                    labor_amount_count = record.apu_total_all_labor * record.quantity
                    equip_amount_count = record.apu_total_equipment * record.quantity

                    if record.performance > 0:
                        labor_amount_count = labor_amount_count / record.performance
                        equip_amount_count = equip_amount_count / record.performance
                    record.labor_amount_count = labor_amount_count
                    record.equip_amount_count = equip_amount_count
            else:
                record.aux_amount_count = record.balance
                record.material_amount_count = 0
                record.labor_amount_count = 0
                record.equip_amount_count = 0
                record.subcontract_amount_counts = 0

        # Calculamos las hh
        hh_cant_mo = sum(record.child_ids.filtered_domain([('type','=','labor')]).mapped('quantity'))
        hh_un = (record.hours_day * hh_cant_mo) / record.performance if record.performance > 0 else 0
        record.resume_hh = hh_un * record.quantity
        record.resume_dh = record.resume_hh / record.hours_day if record.hours_day > 0 else 0

        # Calculamos las horas equipos
        hh_cant_eq = sum(record.child_ids.filtered_domain([('type','=','equip')]).mapped('quantity'))
        hh_un = (record.hours_day * hh_cant_eq) / record.performance if record.performance > 0 else 0
        record.resume_he = hh_un * record.quantity
        record.resume_de = record.resume_he / record.hours_day if record.hours_day > 0 else 0

        # Calculamos los valores en los recursos

        for child in record.child_ids:
            if child.type in ['labor', 'equip']:
                child.rec_total_labor = child.balance + child.rec_tota_bonus + child.rec_ben_sociales
                if record.performance > 0:
                    child.rec_total_days = child.quantity / record.performance * record.quantity
                    child.rec_total_hh = child.rec_total_days * record.hours_day
                else:
                    child.rec_total_days = child.quantity * record.quantity
                    child.rec_total_hh = child.rec_total_days * record.hours_day




    def get_concept_attendance_records(self):
        attendance_domain = [('concept_id', '=', self.id), ('check_out', '!=', False)]
        attendances = self.env['hr.attendance'].search(attendance_domain)
        total_attendances = sum(atten.attendance_cost for atten in attendances)
        return attendances, total_attendances

    def get_concept_invoice_line_totals(self):
        invoice_lines = self.env['account.move.line'].search(
            [('concept_id', '=', self.id), ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),('display_type', '=', 'product'), ('move_id.state', '=', 'posted')])
        invoices_list = set(invoice_lines.move_id)
        invoices = []
        include_vat = self.budget_id.company_id.include_vat_in_indicators
        concept_invoice_total = 0
        for invoice in invoices_list:
            factor = 1
            if invoice.move_type == 'in_refund':
                factor = -1
            if invoice.include_for_bim:
                invoice_line_ids = invoice_lines.filtered_domain([('move_id','=',invoice.id)])
                invoice_total = sum(line.price_total * factor if include_vat else line.price_subtotal * factor for line in invoice_line_ids)
                invoices.append({'invoice_id': invoice, 'invoice_total': invoice_total, 'invoice_lines': invoice_line_ids})
                concept_invoice_total += invoice_total
        return invoices, concept_invoice_total

    def get_concept_picking_move_totals(self):
        picking_obj = self.env['stock.picking']
        domain = [('bim_concept_id', '=', self.id), ('picking_type_code', '=', 'outgoing'), ('state', '=', 'done'),('include_for_bim', '=', True)]
        pickings = picking_obj.search(domain)
        concept_picking_total = 0
        picking_list = []
        for picking in pickings:
            concept_picking_total += picking.total_cost
            picking_list.append({'picking_id': picking, 'picking_total': picking.total_cost})
        domain = [('bim_concept_id', '=', self.id), ('picking_type_code', '=', 'incoming'), ('state', '=', 'done'), ('returned', '=', True),('include_for_bim', '=', True)]
        pickings = picking_obj.search(domain)
        for picking in pickings:
            concept_picking_total -= picking.total_cost
            picking_list.append({'picking_id': picking, 'picking_total': picking.total_cost * -1})
        return picking_list, concept_picking_total

    def get_concept_open_balance_totals(self):
        open_bal_obj = self.env['bim.opening.balance']
        domain = [('concept_id', '=', self.id), ('active', '=', True)]
        balances = open_bal_obj.search(domain)
        concept_balance_total = 0
        balance_list = []
        for balance in balances:
            concept_balance_total += balance.amount
            balance_list.append({'balance_id': balance, 'balance_total': balance.amount})
        return balance_list, concept_balance_total

    def get_concept_tools_totals(self):
        tool_obj = self.env['bim.tool.use']
        domain = [('concept_id', '=', self.id)]
        lines_tool = tool_obj.search(domain)
        tool_total = 0
        tool_list = []
        for tool in lines_tool:
            tool_total += tool.total
            tool_list.append({'tool_id': tool, 'tool_total': tool.total})
        return tool_list, tool_total



    def update_certify(self):
        for record in self:
            record._compute_amount_cert()

    def update_budget_type(self):
        for record in self:
            if record.budget_type == 'certification':
                if record.type_cert == 'fixed' and record.amount_fixed_cert != record.amount_compute_cert:
                    record.amount_fixed_cert = record.amount_compute_cert

    def generate_stage_list(self):
        for record in self:
            if not record.certification_stage_ids:
                if not record.budget_id.stage_ids:
                    raise UserError(_("Current Budget {} has not stages. Please generate them first!").format(record.budget_id.display_name))
                cont = 1
                lines = []
                for stage in record.budget_id.stage_ids:
                    line = {
                        'stage_id': stage.id,
                        'concept_id': record.id,
                        'budget_qty': record.quantity if cont == 1 else 0.0,
                        'certif_qty': 0.0,
                        'certif_percent': 0.0,
                        'amount_budget': record.balance if cont == 1 else 0.0}
                    lines.append((0, 0, line))
                    cont += 1
                record.certification_stage_ids = lines

    def update_stage_list(self, stage):
        for record in self:
            found = False
            for measure in record.certification_stage_ids:
                if measure.stage_id == stage:
                    found = True
                    break
            if not found:
                vals = {
                    'stage_id': stage.id,
                    'concept_id': record.id,
                    'budget_qty': record.quantity,
                    'certif_qty': 0.0,
                    'certif_percent': 0.0,
                    'amount_budget': record.balance
                }
                self.env['bim.certification.stage'].create(vals)

    @api.model
    def get_first_attachment(self, res_id):
        record = self.browse(res_id)
        return record.attachment_ids[0].datas if record.attachment_ids else False

    """
    @api.depends('gantt_type', 'child_ids', 'duration',
                 'acs_date_start', 'acs_date_end',
                 'parent_id.acs_date_start', 'parent_id.acs_date_end',
                 'budget_id.date_start', 'budget_id.date_end',
                 'bim_predecessor_concept_ids')

    def _compute_dates(self):
        for record in self:
            if not record.stage_id:
                today = record.budget_id.date_start
                if record.type not in ['chapter', 'departure']:
                    record.acs_date_start = record.parent_id.acs_date_start
                    record.acs_date_end = record.parent_id.acs_date_end
                    continue
                if not record.budget_id.do_compute:
                    continue
                # Verificamos si tiene predecesoras
                date_start = date_end = False
                for pred in record.bim_predecessor_concept_ids:
                    if pred.pred_type in 'ff':
                        date_end = pred.name.acs_date_end + timedelta(days=pred.difference)
                    elif pred.pred_type == 'fs':
                        date_start = pred.name.acs_date_end + timedelta(days=pred.difference)
                    elif pred.pred_type == 'sf':
                        date_end = pred.name.acs_date_start + timedelta(days=pred.difference)
                    elif pred.pred_type == 'ss':
                        date_start = pred.name.acs_date_start + timedelta(days=pred.difference)

                if date_start or date_end:
                    if not date_end:
                        date_end = date_start + timedelta(days=record.duration)
                    elif not date_start:
                        date_start = date_end - timedelta(days=record.duration)

                if record.gantt_type == 'begin':
                    record.acs_date_end = date_end or record.acs_date_end or today
                    record.acs_date_start = date_start or ((date_end or record.acs_date_end) - timedelta(days=record.duration))
                elif record.gantt_type == 'end':
                    record.acs_date_start = date_start or record.acs_date_start or today
                    record.acs_date_end = date_end or ((date_start or record.acs_date_start) + timedelta(days=record.duration))
                else:
                    record.acs_date_start = date_start or min([d for d in record.child_ids.mapped('acs_date_start') if d], default=today)
                    record.acs_date_end = date_end or max([d for d in record.child_ids.mapped('acs_date_end') if d], default=today)
            else:
                record.acs_date_start = record.stage_id.date_start
                record.acs_date_end = record.stage_id.date_stop

    def _inverse_date_start(self):
        for record in self:
            if not record.stage_id:
                if not record.budget_id.do_compute:
                    continue
                if record.acs_date_start and record.duration:
                    record.acs_date_end = record.acs_date_start + timedelta(days=record.duration)
            else:
                record.acs_date_end = record.stage_id.date_stop

    def _inverse_date_end(self):
        for record in self:
            if not record.stage_id:
                if not record.budget_id.do_compute:
                    continue
                if record.acs_date_end and record.duration:
                    record.acs_date_start = record.acs_date_end - timedelta(days=record.duration)
            else:
                record.acs_date_start = record.stage_id.date_start"""



    @api.onchange('duration')
    def onchange_duration(self):
        if not self.budget_id.type_duration == 'date':
            if self.acs_date_start and self.duration:
                self.acs_date_end = self.acs_date_start + timedelta(days=self.duration)
            else:
                if self.acs_date_start:
                    self.acs_date_end = self.acs_date_start

    @api.onchange('acs_date_start', 'acs_date_end', 'performance', 'performance_type', 'quantity')
    def onchange_dates(self):
        for record in self:
            bim_calendar_id = record.budget_id.bim_calendar_id
            if not record.acs_date_start:
                record.acs_date_start = record.budget_id.date_start
            if record.budget_id.type_duration == 'performance':
                 record.duration = record.quantity / record.performance if record.performance > 0 else 0
                 record.acs_date_end = record.acs_date_start + timedelta(days=record.duration)
            elif record.budget_id.type_duration == 'manual':
                continue
            else:
                if not bim_calendar_id:
                    record.duration = (record.acs_date_end - record.acs_date_start).days + 1
                else:
                    begin_date = record.acs_date_start + timedelta(hours=record.company_id.server_hour_difference)
                    end_date = record.acs_date_end + timedelta(hours=record.company_id.server_hour_difference)
                    record.duration = bim_calendar_id.get_working_days_count(begin_date, end_date)

    @api.onchange('percent_cert','certification_stage_ids')
    def _compute_check_percent_certification(self):
        for concept in self:
            if concept.budget_id.limit_certification and concept.budget_id.limit_certification_percent < concept.percent_cert:
                pass
                    # raise UserError(_("Concept: {} has surpassed its budget certification limit!").format(concept.display_name))

    def _check_percent_certification(self):
        for concept in self:
            if concept.budget_id.limit_certification and concept.budget_id.limit_certification_percent < concept.percent_cert:
                certifiable = False
            else:
                certifiable = True
            return certifiable

    @api.depends('product_id', 'uom_id', 'quantity')
    def _compute_weight(self):
        peso_category = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for record in self:
            if record.product_id and record.uom_id and record.uom_id.category_id == peso_category:
                record.weight = record.product_id.weight * record.uom_id.factor * record.quantity
            else:
                record.weight = 0.0

    @api.depends('name', 'code', 'parent_id')
    def _compute_display_name(self):
        for concept in self:
            name = '[%s] %s' % (concept.code, concept.name)
            concept.display_name = name

    @api.depends('type')
    def _compute_filter_type_domain(self):
        for move in self:
            if move.type == 'departure':
                move.filter_type_domain = 'chapter'
            else:
                move.filter_type_domain = 'departure'

    @api.depends('type')
    def _compute_filter_product_domain(self):
        for rec in self:
            if rec.type == 'equip':
                rec.filter_product_domain = 'Q'
                rec.filter_product_domain_aux = 'HR'
            elif rec.type == 'labor':
                rec.filter_product_domain = 'H'
                rec.filter_product_domain_aux = 'H'
            elif rec.type == 'material':
                rec.filter_product_domain = 'M'
                rec.filter_product_domain_aux = 'M'
            elif rec.type == 'subcontract':
                rec.filter_product_domain = 'S'
                rec.filter_product_domain_aux = 'S'
            elif rec.type == 'aux':
                rec.filter_product_domain = 'A'
                rec.filter_product_domain_aux = 'F'
            else:
                rec.filter_product_domain = 'M'
                rec.filter_product_domain_aux = 'Q'

    def recursive_amount(self, concept, parent, amount=None):
        amount = amount is None and concept.balance or amount or 0.0
        if parent.type == 'departure':
            amount_partial = amount * parent.quantity
            return self.recursive_amount(concept, parent.parent_id, amount_partial)
        else:
            return amount * parent.quantity

    def _get_value(self, quantity, product):
        ''' Este metodo Retorna Retorna el Monto
        en un Movimiento del Product (stock.move)'''
        if product.cost_method == 'fifo':
            quantity = product.quantity_svl
            if float_is_zero(quantity, precision_rounding=product.uom_id.rounding):
                value = 0.0
            average_cost = product.value_svl / quantity
            value = quantity * average_cost
        else:
            value = quantity * product.standard_price
        return float(value)

    def recursive_quantity(self, resource, parent, qty=None):
        qty = qty is None and resource.quantity_cert or qty
        if parent.type == 'departure':
            qty_partial = qty * parent.quantity_cert
            return self.recursive_quantity(resource, parent.parent_id, qty_partial)
        else:
            return qty * parent.quantity_cert

    def set_recursive_quantity_cert(self, child_ids, qty_cert):
        ''' Este metodo actualiza los Hijos de Partidas
        certificadas con la Quantity afectada'''
        for record in child_ids:

            parent = record.parent_id
            qty_afected = parent.quantity_cert * record.quantity
            record.quantity_cert = qty_afected + qty_cert

            if record.child_ids:
                qty_cert = qty_afected
                return record.set_recursive_quantity_cert(record.child_ids, qty_cert)

    def set_qty_cert_child(self):
        ''' Este metodo es llamado desde xxxxxxx
        para actualizar la Quantity certificada de los Hijos'''
        for record in self:
            if record.to_certify:
                record.set_recursive_quantity_cert(record.child_ids, 0)
                for child in record.child_ids:
                    if child.child_ids:
                        record.set_recursive_quantity_cert(child.child_ids, 0)

    def update_concept(self):
        ''' Este metodo es llamado desde el menú contextual
        en la vista hierarchy para actualizar la rama'''
        for child in self.child_ids:
            child.update_concept()
        self.update_amount()

    def cert_massive(self):
        ''' Este metodo es llamado desde el menú contextual
        en la vista hierarchy para certificación masiva'''
        action = {
            'type': 'ir.actions.act_window',
            'name': 'New Mass Certification',
            'res_model': 'bim.massive.certification.by.line',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_budget_id': self.budget_id.id, 'default_project_id': self.budget_id.project_id.id}
        }
        return action

    def _compute_planned_quantity(self, date_start, date_end):
        for record in self:
            budget_qty = record.quantity
            # fechas del concepto

            if record.acs_date_start:
                date_start_concept = record.acs_date_start.date()

            if record.acs_date_end:
                date_end_concept = record.acs_date_end.date()

            if not record.acs_date_start  or not record.acs_date_end:
                return 0

            if date_end_concept < date_start:
                return 0

            elif date_start_concept > date_end:
                return 0
            elif date_end_concept < date_end:
                return budget_qty
            else:
                duraration_stage = (date_end - date_start).days
                duration_concept = (date_end_concept - date_start_concept).days
                duration_concept_stage = (date_end - date_start_concept).days
                percent = (duration_concept_stage / duration_concept if duration_concept > 0 else 0)
                return percent * budget_qty


    def get_resources(self, child_ids, res_ids):
        ''' Este metodo Retorna los ids de los
        recursos(concept) contenidos en los Hijos recibidos'''
        res = res_ids
        for record in child_ids:
            if record.type in ['labor', 'equip', 'material', 'aux']:
                res.append(record.id)
            if record.child_ids:
                record.get_resources(record.child_ids, res)
        return res

    def get_departure_parent(self, parent):
        ''' Este metodo Retorna partida padre del
         Concept'''
        result = False
        for cpt in parent:
            if cpt.type == 'departure':
                result = cpt
            else:
                cpt.get_departure_parent(cpt.parent_id)
        return result

    def get_departures(self, child_ids):
        ''' Este metodo Retorna partidas contenidos
        en el Concept'''
        res = []
        for record in child_ids:
            if record.type in ['departure']:
                res.append(record.id)
            if record.child_ids:
                record.get_departures(record.child_ids)
        return res

    def get_resource_from_type(self, child_ids, res_type):
        ''' Este metodo Retorna Recursos (Products)
        contenidos en el Concept'''
        res = []
        for record in child_ids:
            if record.product_id and record.type == res_type:
                res.append(record.product_id.id)
            if record.child_ids:
                record.get_resource_from_type(record.child_ids, res_type)
        return res

    def move_record(self, action):
        sibblings = self.search([('parent_id', '=', self.parent_id.id), ('budget_id', '=', self.budget_id.id), ('id', '!=', self.id)])
        before = after = self.browse()
        for sibbling in sibblings:
            if (sibbling.sequence == self.sequence and sibbling.code < self.code) or (sibbling.sequence < self.sequence):
                before += sibbling
            else:
                after += sibbling
        if action == 'move_up' and before:
            self.sequence = before[-1].sequence if len(before) > 1 else 0
            before[-1].sequence = self.sequence + 1
            next_seq = self.sequence + 1
        elif action == 'move_down' and after:
            next_seq = self.sequence + 1
            after[0].sequence = self.sequence
            self.sequence = next_seq
            after = after[1:]
        else:
            next_seq = self.sequence

        for after_sib in after:
            after_sib.sequence = next_seq + 1
            next_seq += 1

        return True

    def do_nature(self):
        """ Dummy, debe existir """
        return

    def _check_bugdet_lock(self):
        for record in self:
            if record.budget_id.state_id.lock_budget:
                raise ValidationError(_('Concepts in budget state %s are not allow to me created/ modified or deleted!')%record.budget_id.state_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        concepts = super().create(vals_list)
        for concept in concepts:
            concept._check_bugdet_lock()
            if concept.parent_id:
                sibblings = concept.parent_id.child_ids - concept
                if sibblings:
                    concept.sequence = sibblings.sorted('sequence')[-1].sequence + 1
        return concepts

    def unlink(self):
        for record in self:
            record._check_bugdet_lock()
            if record.balance_cert > 0:
                raise ValidationError(_('You cannot delete concepts that contain certifications.'))
            if record.picking_ids:
                raise ValidationError(_('You cannot delete concepts that contain outbound entries.'))
            if record.part_ids:
                raise ValidationError(_('You cannot delete items that contain parts of labor or equipment.'))
            record.child_ids.unlink()
        return super().unlink()

    def get_real_executed_for_departure(self, bim_parts, bim_attendance, bim_invoices, bim_picking_out, bim_open_balance, bim_tools):
        total_executed = 0
        if bim_parts:
            for part in self.part_ids.filtered_domain([('state', '=', 'validated')]):
                total_executed += part.part_total
        if bim_attendance:
            total_executed += self.get_concept_attendance_records()[1]
        if bim_invoices:
            total_executed += self.get_concept_invoice_line_totals()[1]
        if bim_picking_out:
            total_executed += self.get_concept_picking_move_totals()[1]
        if bim_open_balance:
            total_executed += self.get_concept_open_balance_totals()[1]
        if bim_tools:
            total_executed += self.get_concept_tools_totals()[1]
        return total_executed

    def get_real_executed_for_chapter(self, bim_parts, bim_attendance, bim_invoices, bim_picking_out, bim_open_balance, bim_tools):
        total_executed = 0
        for chapter in self:
            if bim_parts:
                for part in chapter.part_ids.filtered_domain([('state', '=', 'validated')]):
                    total_executed += part.part_total
            if bim_attendance:
                total_executed += chapter.get_concept_attendance_records()[1]
            if bim_invoices:
                total_executed += chapter.get_concept_invoice_line_totals()[1]
            if bim_picking_out:
                total_executed += chapter.get_concept_picking_move_totals()[1]
            if bim_open_balance:
                total_executed += chapter.get_concept_open_balance_totals()[1]
            if bim_tools:
                total_executed += chapter.get_concept_tools_totals()[1]
            for grand_child in chapter.child_ids.filtered_domain([('type','in',['chapter','departure'])]):
                total_executed += grand_child.get_real_executed_for_chapter(bim_parts, bim_attendance, bim_invoices, bim_picking_out, bim_open_balance, bim_tools)
        return total_executed


    # --------------------------------------------------------------------#
    # ---------------- ACTION VIEWS METHODS ------------------------------#
    # --------------------------------------------------------------------#
    def action_view_parameter_values(self):
        action = self.env.ref('base_bim_2.action_bim_concept_parameter').sudo().read()[0]
        action['domain'] = [('concept_id', '=', self.id)]
        return action

    def action_view_equip(self):
        childs = self.mapped('child_ids')
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('id', 'in', childs.ids), ('parent_id', '=', self.id), ('type', '=', 'equip')]
        return action

    def action_view_material(self):
        childs = self.mapped('child_ids')
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('id', 'in', childs.ids), ('parent_id', '=', self.id), ('type', '=', 'material')]
        return action

    def action_view_labor(self):
        childs = self.mapped('child_ids')
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('id', 'in', childs.ids), ('parent_id', '=', self.id), ('type', '=', 'labor')]
        return action

    def action_view_departure(self):
        childs = self.mapped('child_ids')
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('id', 'in', childs.ids), ('parent_id', '=', self.id), ('type', '=', 'departure')]
        return action

    def action_view_picking(self):
        action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]
        pickings = self.mapped('picking_ids')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        # Prepare the context.
        #picking_id = pickings.filtered(lambda l: l.picking_type_id.code == 'outgoing')
        # if picking_id:
        #    picking_id = picking_id[0]
        # else:
        #    picking_id = pickings[0]
        #action['context'] = dict(self._context, default_partner_id=self.partner_id.id, default_picking_id=picking_id.id, default_picking_type_id=picking_id.picking_type_id.id, default_origin=self.name, default_group_id=picking_id.group_id.id)
        return action

    def action_view_part(self):
        parts = self.mapped('part_ids')
        action = self.env.ref('base_bim_2.action_bim_part').sudo().read()[0]

        if len(parts) > 0:
            action['domain'] = [('id', 'in', parts.ids)]
            action['context'] = {'default_concept_id': self.id, 'default_budget_id': self.budget_id.id,'default_project_id': self.budget_id.project_id.id, 'default_elements_readonly': True}
            return action
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Budget',
                'res_model': 'bim.part',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_concept_id': self.id, 'default_budget_id': self.budget_id.id,'default_project_id': self.budget_id.project_id.id, 'default_elements_readonly': True}
            }
    # 'default_budget_id': self.budget_id.id,'default_project_id': self.budget_id.project_id.id
    def action_view_concept(self):
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('budget_id', '=', self.budget_id.id)]
        action['context'] = {'default_budget_id': self.budget_id.id}
        action['context'].update({'budget_type': self.budget_id.type})
        return action

    def get_departure_total(self, concept_type=False, domain=[], mapped_field='balance'):
        self.ensure_one()
        if concept_type:
            domain.append(('type', '=', concept_type))
        return sum(self.child_ids.filtered_domain(domain).mapped(mapped_field))

    def get_bonus_total(self, concept_type=False, domain=[], mapped_field='available'):
        self.ensure_one()
        if concept_type:
            domain.append(('type', '=', concept_type))

        sum_available = sum(self.child_ids.filtered_domain(domain).mapped(mapped_field))

        foot_bonus = self.budget_id.foot_bonus

        sum_available_porcent = sum_available * foot_bonus

        return sum_available_porcent

    def get_departure_budget_asset_percent(self, domain=[]):
        self.ensure_one()
        domain.append(('budget_id', '=', self.budget_id.id))
        assets = self.env['bim.budget.assets'].search(domain,limit=1)
        if assets:
            return assets.value
        return False

class BimConceptOptions(models.Model):
    _name = 'bim.concept.options'
    _description = "Bim Concept Options"

    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Char(string='Description', required=True)
    qty = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Price', required=True)
    price_subtotal = fields.Float(string='Subtotal', compute='_compute_amount', store=True)
    concept_id = fields.Many2one('bim.concepts', "Budget Item")

    @api.depends('qty', 'price_unit')
    def _compute_amount(self):
        for record in self:
            record.price_subtotal = record.qty * record.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.lst_price

class BimConceptMeasuring(models.Model):
    _name = 'bim.concept.measuring'
    _description = "Budget Measurement"

    @api.depends('qty', 'length', 'width', 'height', 'formula')
    def _compute_amount(self):
        for record in self:
            if record.formula:
                X = x = b = B = record.length
                Y = y = c = C = record.width
                Z = z = d = D = record.height
                try:
                    record.amount_subtotal = record.qty * eval(str(record.formula.formula))
                except:
                    raise UserError(_('There is an error in formula'))
            else:
                record.amount_subtotal = record.qty * ((record.length > 0 and record.length or 1) * (record.width > 0 and record.width or 1) * (record.height > 0 and record.height or 1))

    name = fields.Char(string='Description', required=True)
    space_id = fields.Many2one('bim.budget.space', string='Space')
    qty = fields.Float(string='Quant (N)')
    length = fields.Float(string='Length (X)')
    width = fields.Float(string='Width (Y)')
    height = fields.Float(string='High (Z)')
    formula = fields.Many2one('bim.formula', string='Formula')
    amount_subtotal = fields.Float(string='Subtotal', store=True, digits='BIM Measuring', compute="_compute_amount")
    stage_id = fields.Many2one('bim.budget.stage', "Stage")
    concept_id = fields.Many2one('bim.concepts', "Budget Item")
    budget_id = fields.Many2one('bim.budget', related="concept_id.budget_id", string='Budget')
    to_certify = fields.Boolean(related="concept_id.to_certify", string='Certifiable')
    type_certify = fields.Selection(related="concept_id.type_cert", string='Type')
    stage_state = fields.Selection(related='stage_id.state', store=True, readonly=True)
    characteristic = fields.Selection([('agreed', 'Agreed'),
                                       ('null', 'Null'),
                                       ('modified_approved', 'Modified Approved'),
                                       ('modified_pending', 'Modified Pending')], string='Characteristic', default='agreed', required=True)

    def _loader_params_bim_concept_measuring(self):
        result = super()._loader_params_bim_concept_measuring()
        result['search_params']['fields'].extend(['space_id', 'qty', 'length', 'width', 'height', 'formula', 'amount_subtotal', 'stage_id', 'concept_id', 'budget_id', 'to_certify', 'type_certify', 'stage_state', 'characteristic'])
        return result

    @api.onchange('space_id')
    def onchange_group(self):
        if self.space_id:
            self.name = self.space_id.name
            self.characteristic = 'agreed'


class BimCertificationStage(models.Model):
    _name = 'bim.certification.stage'
    _description = "Certification by Stages"

    @api.depends('stage_id', 'stage_id.state', 'budget_qty', 'certif_qty', 'concept_id.amount_compute_cert')
    def _compute_amount(self):
        for record in self:
            #record.amount_budget = record.budget_qty * record.concept_id.amount_compute
            record.amount_certif = record.certif_qty * record.concept_id.amount_compute_cert

    name = fields.Date(string='Date', related='stage_id.date_stop', required=True)
    budget_qty = fields.Float(string='Budget Qty (N)', default=0, digits='BIM qty')
    certif_qty = fields.Float(string='Cert Qty (N)', default=0, digits='BIM qty')
    certif_percent = fields.Float(string='(%) Cert', default=0)
    stage_id = fields.Many2one('bim.budget.stage', "Stage", ondelete='cascade')
    concept_id = fields.Many2one('bim.concepts', "Budget Item")
    budget_id = fields.Many2one('bim.budget', related="concept_id.budget_id", string='Budget')
    amount_budget = fields.Float(string='Total Budget', digits='BIM price')
    amount_certif = fields.Float(string='Total Cert', digits='BIM price', compute="_compute_amount", store=True)
    stage_state = fields.Selection(related='stage_id.state', store=True, readonly=True)

    @api.onchange('certif_qty')
    def onchange_qty(self):
        for record in self:
            if record.concept_id.quantity <= 0:
                record.certif_percent = (record.certif_qty / 1) * 100
            else:
                record.certif_percent = (record.certif_qty / record.concept_id.quantity) * 100


    # Error de Redondeo
    """
    @api.onchange('certif_percent')
    def onchange_percent(self):
        for record in self:
            record.certif_qty = (record.concept_id.quantity * record.certif_percent) / 100"""

    def action_next(self):
        if self.stage_state == 'draft':
            self.stage_id.state = 'process'
        elif self.stage_state == 'process':
            self.stage_id.state = 'approved'

    def action_cancel(self):
        return self.stage_id.write({'state': 'cancel'})


class BimPredecessorConcept(models.Model):
    _name = 'bim.predecessor.concept'
    _description = "Predecessor Tasks"

    name = fields.Many2one('bim.concepts', 'Predecessor', required=True)
    concept_id = fields.Many2one('bim.concepts', "Budget Item")
    difference = fields.Integer('Days of Difference', help='Supports negative values')
    pred_type = fields.Selection([('ff', 'End to end'),
                                  ('fs', 'End to start'),
                                  ('sf', 'Start to end'),
                                  ('ss', 'Start to start')], 'Type', required=True, default='fs')

    _sql_constraints = [
        ('unique_concept_predecessor', 'unique(name,concept_id)', 'The same predecessor can not be repeated')
    ]

    @api.constrains('name')
    def _check_loops(self):
        def in_loop(concept, predecessors, verified):
            for pred in predecessors:
                if pred.name in verified:
                    continue
                verified += pred.name
                if concept == pred.name:
                    return [pred.name]
                res = in_loop(concept, pred.name.bim_predecessor_concept_ids, verified)
                if res:
                    return res + [pred.name]
            for child in concept.child_ids:
                if child in verified:
                    continue
                verified += child
                res = in_loop(concept, child.bim_predecessor_concept_ids, verified)
                if res:
                    return res + [child]
            return []

        def get_parents(concept):
            if not concept.parent_id:
                return self.name.browse()
            return concept.parent_id + get_parents(concept.parent_id)

        def get_childs(concept):
            if not concept.child_ids:
                return self.name.browse()
            grand_childs = self.name.browse()
            for child in concept.child_ids:
                grand_childs += get_childs(child)
            return concept.child_ids + grand_childs

        for record in self:
            loops = in_loop(record.name, record.name.bim_predecessor_concept_ids, self.name.browse())
            if loops:
                loops.append(record.name)
                raise ValidationError('A cycle is forming.\n%s' % ' > '.join(l.display_name for l in loops))

            if record.name in get_parents(record.concept_id):
                raise ValidationError(_('A concept cant not be chosen as parent'))
            if record.name in get_childs(record.concept_id):
                raise ValidationError(_('A concept cant not be chosen as child'))


class BimConceptParent(models.Model):
    _name = 'bim.concept.parent'
    _description = "Bim Concept Parent"

    name = fields.Many2one('bim.concepts', "Concepts")
    concept_id = fields.Many2one('bim.concepts', "Concept")
