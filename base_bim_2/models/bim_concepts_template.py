# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux'}


class BimConceptTemplate(models.Model):
    _name = 'bim.concept.template'
    _order = "id desc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = "Concept Template"


    name = fields.Text("Name", required=True, index=True)
    code = fields.Char("Code", required=True, index=True)
    type_calc = fields.Selection([
        ('standard', 'Standard'),
        ('apu', 'Apu'),
        ('apu-hh', 'Apu HH'),
        ],
        string="type of calculation", default=lambda self: self.env.company.type_calc, required=True)

    bim_uom = fields.Selection([
        ('Count', 'Count'),
        ('Area', 'Area'),
        ('Volume', 'Volume'),
        ('Length', 'Length'),
        ],
        string="BIM UOM", default='Volume')

    uom_id = fields.Many2one('uom.uom', string='UoM', domain="[]")
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id')
    quantity = fields.Float("Quantity", default=1, digits='BIM qty')
    balance = fields.Monetary(string='Balance', compute="_compute_amount", store=True)  # Importe
    performance_calculation = fields.Boolean(related='company_id.performance_calculation')
    performance_type = fields.Selection([('hours','Hours'),('days','Days')], default='days', required=True)
    hours_day = fields.Integer(default=lambda self: self.env.company.working_hours)
    performance = fields.Float(string='Performance', digits="BIM Performance")
    user_id = fields.Many2one('res.users', string='User', readonly=True, default=lambda self: self.env.user)
    template_line_ids = fields.One2many('bim.concept.template.line','template_id', copy=True)
    resource_count = fields.Integer(
        string='Recursos',
        compute='_compute_resource_count',
        store=True,
    )

    @api.depends('template_line_ids')
    def _compute_resource_count(self):
        for rec in self:
            rec.resource_count = len(rec.template_line_ids)

    apu_total_hh = fields.Float("Total APU HH", compute='_compute_apu_total_hh', store=True, digits='BIM price')
    apu_duration = fields.Float("Duration", digits='BIM price', compute='_compute_apu_duration', store=True)

    sub_total_labor = fields.Float("Sub Total Labor", digits='BIM price', compute='_compute_apu', store=True)
    apu_labor = fields.Float("Labor APU", digits='BIM price', compute='_compute_apu', store=True)

    sub_total_equip = fields.Float("Sub Total Equip", digits='BIM price', compute='_compute_apu', store=True)
    apu_equip = fields.Float("Equip APU", digits='BIM price', compute='_compute_apu', store=True)

    sub_total_mat = fields.Float("Sub Total Material", digits='BIM price', compute='_compute_apu', store=True)
    apu_mat = fields.Float("Material APU", digits='BIM price', compute='_compute_apu', store=True)

    sub_total_subcontract = fields.Float("Sub Total Subcontract", digits='BIM price', compute='_compute_apu', store=True)
    apu_subcontract = fields.Float("Subcontract APU", digits='BIM price', compute='_compute_apu', store=True)
    active = fields.Boolean(default=True)

    @api.depends('name','code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = "[%s] %s" % (record.code, record.name)


    @api.depends('template_line_ids','template_line_ids.amount')
    def _compute_apu_total_hh(self):
        apu_total_hh = 0
        sub_total_labor = 0
        for line in self.template_line_ids:
            if line.type == 'H':
                apu_total_hh += line.quantity
                sub_total_labor += line.amount

        if apu_total_hh > 0:
            self.apu_total_hh = apu_total_hh
        else:
            self.apu_total_hh = 1
        self.sub_total_labor = sub_total_labor

    @api.depends('apu_total_hh','hours_day')
    def _compute_apu_duration(self):
        for template in self:
            template.apu_duration = template.performance / template.apu_total_hh

    @api.depends('template_line_ids','template_line_ids.amount')
    def _compute_apu(self):
        for record in self:
            if record.apu_total_hh > 0:
                if record.performance > 0:
                    apu_duration = record.performance / record.apu_total_hh
                else:
                    apu_duration = 1
            else:
                apu_duration = 1

            record.apu_labor = record.sub_total_labor * apu_duration
            record.sub_total_equip = sum(line.amount for line in record.template_line_ids.filtered_domain([('type','=','Q')]))
            record.apu_equip = record.sub_total_equip * apu_duration
            record.sub_total_mat = sum(line.amount for line in record.template_line_ids.filtered_domain([('type','=','M')]))
            record.apu_mat = record.sub_total_mat
            record.sub_total_subcontract = sum(line.amount for line in record.template_line_ids.filtered_domain([('type','=','S')]))
            record.apu_subcontract = record.sub_total_subcontract


    def update_all(self):
        for rec in self:
            rec._compute_apu_total_hh()
            rec._compute_apu_duration()
            rec._compute_apu()
            rec._compute_amount_total()




    amount_total = fields.Float(compute='_compute_amount_total', store=True, digits="BIM price")
    compute_performance = fields.Float(compute='_compute_performance_method', store=True, default=False, digits=(10, 2))
    group_id = fields.Many2one('bim.concept.template.group', ondelete='restrict', string='Group', domain="[('parent_id','=',False)]")
    sub_group_id = fields.Many2one('bim.concept.template.group', ondelete='restrict', string='Sub Group', domain="[('parent_id','=',group_id)]")
    attachment_ids = fields.Many2many('ir.attachment', string='Images')
    notes = fields.Text(string='Notes', default="")


    parameter_ids = fields.One2many('bim.parameter','template_id')
    parameter_count = fields.Integer(compute='_compute_parameter_count', store=True)


    bim_id = fields.Char(string='BIM ID')

    concept_phase_id = fields.Many2one('concept.phase', string='Phase')
    sub_phase_id = fields.Many2one('concept.phase', string='Sub Phase')
    concept_specialty_id = fields.Many2one('concept.specialty', string='Specialty')

    bc3_importer_id = fields.Many2one('bim.bc3.apu.importer', string='BC3 Import', ondelete='set null', index=True)

    bim_concepts_ids = fields.One2many('bim.concepts', 'concept_template_id', string='Concepts')
    bim_concepts_count = fields.Integer(compute='_compute_bim_concepts_count', string='Concepts Count')

    @api.depends('bim_concepts_ids')
    def _compute_bim_concepts_count(self):
        for template in self:
            template.bim_concepts_count = len(template.bim_concepts_ids)

    def action_view_concepts(self):
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('concept_template_id', '=', self.id)]
        action['context'] = {'default_concept_template_id': self.id}
        return action

    @api.depends('parameter_ids')
    def _compute_parameter_count(self):
        for template in self:
            template.parameter_count = len(template.parameter_ids)

    @api.constrains('group_id')
    def check_subgroup_parent(self):
        for template in self:
            if template.group_id and template.sub_group_id and \
               template.sub_group_id.parent_id.id != template.group_id.id:
                template.sub_group_id = False

    @api.onchange('group_id','sub_group_id')
    def onchange_groups(self):
        group = self.group_id.code or ''
        sub_group = self.sub_group_id.code or ''
        self.code = sub_group if sub_group else group

    @api.onchange('hours_day')
    def onchange_hours_day(self):
        if self.hours_day <= 0 and self.performance_type == 'days':
            raise UserError(_("Day hours can not be zero or less!"))

    @api.onchange('performance_type')
    def onchange_performance_type(self):
        if self.company_id:
            self.hours_day = self.company_id.working_hours

    @api.depends('template_line_ids','template_line_ids.amount','template_line_ids.price')
    def _compute_amount_total(self):
        for template in self:
            if template.type_calc == 'standard':
                total = 0
                for line in template.template_line_ids:
                    total += line.amount
                template.amount_total = total
            else:
                template.amount_total = template.apu_labor + template.apu_equip + template.apu_mat + template.apu_subcontract

    def action_view_parameters(self):
        action = self.env.ref('base_bim_2.action_bim_parameter').sudo().read()[0]
        action['domain'] = [('template_id', '=', self.id)]
        action['context'] = {'default_template_id': self.id}
        return action

    def _create_chapter_from_template(self, budget):
        if not self.group_id:
            raise UserError(_("You must select a group for concept template %s to create the chapter!")%self.name)
        chapter_obj = self.env['bim.concepts']
        chapter = chapter_obj.search([('budget_id','=',budget.id),('code','=',self.group_id.code)])
        if not chapter:
            chapter = self.env['bim.concepts'].create({
                'name': self.group_id.name,
                'code': self.group_id.code,
                'budget_id': budget.id,
                'type': 'chapter',
            })
        return chapter

    def _create_departure_from_template(self, budget_id, quantity=1):
        self.ensure_one()
        if not budget_id:
            return

        chapter = self._create_chapter_from_template(budget_id)
        self._helper_create_departure_from_template(budget_id, chapter, quantity)

    def _helper_create_departure_from_template(self, budget_id, chapter, quantity):
        departure = budget_id.concept_ids.create({
            'budget_id': budget_id.id,
            'parent_id': chapter[0].id,
            'name': self.name,
            'code': self.code,
            'type': 'departure',
            'quantity': quantity,
            'uom_id': self.uom_id.id if self.uom_id else False,
            'performance_type': self.performance_type,
            'hours_day': self.hours_day,
            'performance': self.performance,
            'note': self.notes,
            'concept_template_id': self.id,
        })
        for line in self.template_line_ids:
            vals = {
                'budget_id': departure.budget_id.id,
                'parent_id': departure.id,
                'name': line.product_id.name if line.product_id else line.name,
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
        return departure

    def _create_departure_with_parameters(self, chapter):
        attachments = []
        for attachment in self.attachment_ids:
            attachments.append(attachment.copy().id)
        departure = chapter.child_ids.create({
            'budget_id': chapter.budget_id.id,
            'parent_id': chapter.id,
            'name': self.name,
            'code': self.code,
            'type': 'departure',
            'quantity': self.quantity,
            'uom_id': self.uom_id.id if self.uom_id else False,
            'performance_type': self.performance_type,
            'hours_day': self.hours_day,
            'performance': self.performance,
            'note': self.notes,
            'attachment_ids': attachments,
        })
        for line in self.template_line_ids:
            price_factor, qty_factor, para_attributes = self._find_product_factor(line.product_id)
            vals = {
                'budget_id': departure.budget_id.id,
                'parent_id': departure.id,
                'name': line.name,
                'code': line.code,
                'quantity': line.quantity,
                'amount_fixed': line.price * price_factor,
                'available': line.available * qty_factor,
                'product_id': line.product_id.id if line.product_id else False,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'type': CONCEPT_TYPE[line.type],
                'concept_template_line_id': line.id,
            }
            departure.child_ids.create(vals)
            departure.write({'param_attribute_ids': para_attributes})
        departure.budget_id.update_amount()
        return departure.action_view_concept()

    def _find_product_factor(self, product_id):
        price_factor = 1
        qty_factor = 1
        parameters = []
        if product_id:
            for parameter_id in self.parameter_ids:
                if product_id.id in parameter_id.product_ids.ids:
                    for value in parameter_id.value_ids:
                        price_factor *= value.price_factor
                        qty_factor *= value.qty_factor
                        parameters.append((0,0,{
                            'parameter_id': parameter_id.id,
                            'parameter_value_id': value.attribute_value_id.id,
                        }))
                        break
        return [price_factor, qty_factor, parameters]

    def action_search_bc3_resources(self):
        """Busca y carga los recursos del importador BC3 asociado al APU."""
        import json
        self.ensure_one()
        if not self.bc3_importer_id:
            raise UserError(_("Este APU no está vinculado a ningún importador BC3."))

        importer = self.bc3_importer_id
        # Buscar la línea de staging correspondiente a este APU
        apu_staging = importer.line_ids.filtered(
            lambda l: l.code == self.code and l.ctype == 0 and '#' not in (l.code or '')
        )
        if not apu_staging:
            raise UserError(
                _("No se encontró la línea de staging para el código '%s' en el importador BC3 '%s'.")
                % (self.code, importer.name)
            )
        apu_staging = apu_staging[0]

        try:
            children = json.loads(apu_staging.decomp_json or '[]')
        except Exception:
            children = []

        if not children:
            raise UserError(
                _("El importador BC3 no tiene datos de descomposición para el APU '%s'.")
                % self.code
            )

        uom_obj = self.env['uom.uom']
        product_obj = self.env['product.product']
        line_model = self.env['bim.concept.template.line']
        bc3_to_line_type = {1: 'H', 2: 'Q', 3: 'M'}

        # Índice de todas las líneas staging por código
        all_lines_by_code = {l.code: l for l in importer.line_ids}

        # Pre-cargar precios del archivo BC3 para hijos sin staging line
        missing_codes = {
            code for code, _qty in children
            if code not in all_lines_by_code
        }
        bc3_prices = {}
        if missing_codes:
            bc3_prices = importer.get_resource_prices(missing_codes)

        # Eliminar las líneas existentes antes de recrearlas
        self.template_line_ids.unlink()

        tpl_seq = 10
        created = 0
        skipped = 0
        for child_code, qty in children:
            try:
                child_staging = all_lines_by_code.get(child_code)

                # --- Porcentajes sin staging line ---
                if not child_staging and child_code.startswith('%'):
                    bc3_data = bc3_prices.get(child_code, {})
                    pct_price = bc3_data.get('price') or round(qty * 100, 4)
                    line_model.create({
                        'template_id': self.id,
                        'type': 'A',
                        'code': child_code,
                        'name': bc3_data.get('name') or child_code,
                        'price': pct_price,
                        'quantity': 0.0,
                        'sequence': tpl_seq,
                    })
                    tpl_seq += 10
                    created += 1
                    continue

                # --- Fallback: buscar producto existente o buscarlo en otros importers ---
                if not child_staging:
                    bc3_data = bc3_prices.get(child_code, {})
                    bc3_ctype = bc3_data.get('ctype', 3)
                    bc3_to_line_fb = {1: 'H', 2: 'Q', 3: 'M'}
                    default_type = bc3_to_line_fb.get(bc3_ctype, 'M')
                    # Buscar en staging lines de TODOS los importers
                    other_staging = self.env['bim.bc3.apu.importer.line'].search(
                        [('code', '=', child_code)], limit=1)
                    if other_staging:
                        child_staging = other_staging
                    else:
                        # Sin staging en ningún importador: buscar producto o crear con precio BC3
                        product = product_obj.search(
                            [('default_code', '=', child_code)], limit=1)
                        if not product:
                            create_vals = {
                                'default_code': child_code,
                                'name': bc3_data.get('name') or child_code,
                                'resource_type': default_type,
                                'type': 'service',
                            }
                            child_uom_str = bc3_data.get('uom', '')
                            if child_uom_str:
                                uom_bc3 = uom_obj.search(
                                    ['|', ('name', '=ilike', child_uom_str),
                                     ('alt_names', '=ilike', child_uom_str)], limit=1)
                                if uom_bc3:
                                    create_vals['uom_id'] = uom_bc3.id
                            product = product_obj.create(create_vals)
                        rt_map = {'H': 'H', 'Q': 'Q', 'M': 'M', 'S': 'S', 'A': 'A'}
                        line_type = rt_map.get(product.resource_type, default_type)
                        bc3_price = bc3_data.get('price', 0.0)
                        if bc3_price:
                            importer._write_product_price(bc3_price, product)
                        line_model.create({
                            'template_id': self.id,
                            'type': line_type,
                            'product_id': product.id,
                            'code': child_code,
                            'name': bc3_data.get('name') or product.name or child_code,
                            'uom_id': product.uom_id.id if product.uom_id else False,
                            'price': bc3_price or product.standard_price or product.lst_price,
                            'quantity': qty,
                            'sequence': tpl_seq,
                        })
                        tpl_seq += 10
                        created += 1
                        continue

                ctype = child_staging.ctype
                line_type = bc3_to_line_type.get(ctype)
                if not line_type:
                    if child_code.startswith('%'):
                        line_type = 'A'
                    else:
                        skipped += 1
                        continue

                # Conceptos de porcentaje (tipo A)
                if line_type == 'A' and child_code.startswith('%'):
                    pct_name = child_staging.name or child_code
                    line_model.create({
                        'template_id': self.id,
                        'type': 'A',
                        'code': child_code,
                        'name': pct_name,
                        'price': child_staging.price,
                        'quantity': qty,
                        'sequence': tpl_seq,
                    })
                    tpl_seq += 10
                    created += 1
                    continue

                # Buscar o crear el producto
                child_uom = child_staging.uom or ''
                uom_rec = uom_obj.search(
                    ['|', ('name', '=ilike', child_uom),
                     ('alt_names', '=ilike', child_uom)],
                    limit=1) if child_uom else uom_obj.browse()

                product = product_obj.search(
                    [('default_code', '=', child_code)], limit=1)

                if not product:
                    create_vals = {
                        'default_code': child_code,
                        'name': child_staging.name,
                        'resource_type': line_type,
                        'type': 'service',
                        'bc3_importer_id': importer.id,
                    }
                    if uom_rec:
                        create_vals['uom_id'] = uom_rec.id
                    product = product_obj.create(create_vals)
                    importer._write_product_price(child_staging.price, product)
                else:
                    if importer.action_type == 'add_update':
                        write_vals = {'name': child_staging.name, 'resource_type': line_type}
                        if uom_rec:
                            write_vals['uom_id'] = uom_rec.id
                        product.write(write_vals)
                        importer._write_product_price(child_staging.price, product)

                line_model.create({
                    'template_id': self.id,
                    'type': line_type,
                    'product_id': product.id,
                    'code': child_code,
                    'name': child_staging.name,
                    'uom_id': uom_rec.id if uom_rec else (product.uom_id.id if product else False),
                    'price': child_staging.price,
                    'quantity': qty,
                    'sequence': tpl_seq,
                })
                tpl_seq += 10
                created += 1

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "BC3 search resources: error en recurso %s para APU %s: %s",
                    child_code, self.code, e)
                skipped += 1

        if created == 0:
            raise UserError(
                _("No se pudieron cargar recursos para el APU '%s'. "
                  "Verifique que los datos del importador BC3 estén completos.") % self.code
            )

        msg = _("Se cargaron %d recursos desde el importador BC3 '%s'.") % (created, importer.name)
        if skipped:
            msg += _(" (%d omitidos).") % skipped
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recursos cargados'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }


class BimConceptTemplateLine(models.Model):
    _name = 'bim.concept.template.line'
    _description = "Concept Template Line"
    _order = "sequence"

    template_id = fields.Many2one('bim.concept.template', ondelete='cascade')
    type = fields.Selection([
        ('H', 'LABOR'),
        ('Q', 'EQUIPMENT'),
        ('M', 'MATERIAL'),
        ('S', 'SUBCONTRACT'),
        ('A', 'FUNCTION / ADMINISTRATIVE')], string="Type", required=True)
    available = fields.Float('Availability', default=1, digits="BIM price")
    product_id = fields.Many2one('product.product', "Product", ondelete='restrict', domain="[('resource_type','=',type)]")
    uom_id = fields.Many2one('uom.uom', string='UoM', domain="[]")
    currency_id = fields.Many2one('res.currency', related='template_id.currency_id')
    name = fields.Text(string='Description',required=True)
    code = fields.Char(required=True)
    price = fields.Float(digits='BIM price')
    day_price = fields.Monetary("Day Price")
    quantity = fields.Float(digits='BIM qty')
    amount = fields.Float(compute='_compute_amount', store=True, digits="BIM price")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', related='template_id.company_id')
    dep =  fields.Float(digits="BIM Performance", string='Dep/Desp/Bono')




    @api.onchange('day_price')
    def onchange_day_price(self):
        self.price = self.day_price / self.template_id.hours_day

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            if self.product_id.default_code:
                self.code = self.product_id.default_code
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id.id
            if self.company_id.type_work in ('costlist','cost'):
                self.price = self.product_id.standard_price
            else:
                self.price = self.product_id.lst_price
        else:
            self.code = False
            self.name = False
            self.uom_id = False

    @api.depends('price','quantity','type','code','sequence','template_id.performance')
    def _compute_amount(self):
        for line in self:
            if line.type == 'A':
                line.onchange_function()
            line.amount = line.price * line.quantity

    def onchange_function(self):
        if self.type == 'A':
            if self.code and '%' in self.code:
                pos = self.code.find('%')
                before_lines = self.template_id.template_line_ids.filtered_domain([('sequence','<',self.sequence)])
                concept_type = False
                if "*" in self.code:
                    pos = self.code.find('*')
                    concept_type = self.code[pos + 1:pos + 2]
                    if concept_type in CONCEPT_TYPE.keys():
                        before_lines = before_lines.filtered_domain(
                            [('type', '=', concept_type)])
                if pos == 0 or concept_type:
                    afecto = sum(child.amount for child in before_lines)
                else:
                    pre = self.code[:pos]
                    afecto = sum(child.amount for child in before_lines if child.code.find(pre) == 0)
                self.quantity = afecto * 0.01


