# coding: utf-8
from odoo import api, fields, models, _

CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux','S': 'subcontract'}


class BimConceptTemplateWizard(models.TransientModel):
    _name = 'bim.concept.template.wizard'
    _description = 'Bim Concept Template Wizard'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['concept_id'] = self._context.get('active_id', False)
        return res

    code = fields.Char()
    name = fields.Char()
    concept_template_id = fields.Many2one('bim.concept.template', required=True, domain="[('id','in',available_template_ids)]")
    concept_id = fields.Many2one('bim.concepts', required=True, readonly=True)
    available_template_ids = fields.Many2many('bim.concept.template')
    group_id = fields.Many2one('bim.concept.template.group', ondelete='restrict', string='Group',
                               domain="[('parent_id','=',False)]")
    sub_group_id = fields.Many2one('bim.concept.template.group', ondelete='restrict', string='Sub Group',
                                   domain="[('parent_id','=',group_id)]")
    attribute_line_ids = fields.One2many('bim.concept.template.attribute','wizard_id')
    parameter_ids = fields.Many2many('bim.parameter', string="Parameters")
    exchange_rate = fields.Float(string="Tasa Cambio")

    @api.onchange('concept_template_id')
    def onchange_template_id(self):
        if self.concept_template_id:
            self.exchange_rate = self.concept_id.budget_id.exchange_rate
            self.parameter_ids = self.concept_template_id.parameter_ids.ids or []
            self.attribute_line_ids = False
            attr_lines = []
            for parameter in self.concept_template_id.parameter_ids:
                attr_lines.append((0,0,{
                    'parameter_id': parameter.id,
                    'parameter_value_id': parameter.value_ids[0].id if parameter.value_ids else False,
                }))
            self.attribute_line_ids = attr_lines
        else:
            self.parameter_ids = False

    @api.onchange('code','name','group_id','sub_group_id')
    def _compute_available_template_ids(self):
        domain = []
        template = False
        if self.code:
            domain.append(('code', 'ilike', self.code))
        if self.name:
            domain.append(('name', 'ilike', self.name))
        if self.group_id:
            domain.append(('group_id', '=', self.group_id.id))
        if self.sub_group_id:
            domain.append(('sub_group_id', '=', self.sub_group_id.id))
        templates = self.env['bim.concept.template'].search(domain, order='id desc')
        if templates:
            templates = templates.ids
            template = templates[0]
        self.concept_template_id = template
        self.available_template_ids = templates

    def action_apply_template(self):
        attachments = []
        for attachment in self.concept_template_id.attachment_ids:
            attachments.append(attachment.copy().id)
        departure = self.concept_id.child_ids.create({
                'budget_id': self.concept_id.budget_id.id,
                'parent_id': self.concept_id.id,
                'name': self.concept_template_id.name,
                'code': self.concept_template_id.code,
                'type': 'departure',
                'quantity': self.concept_template_id.quantity,
                'uom_id': self.concept_template_id.uom_id.id if self.concept_template_id.uom_id else False,
                'performance_type': self.concept_template_id.performance_type,
                'hours_day': self.concept_template_id.hours_day,
                'performance': self.concept_template_id.performance,
                'note': self.concept_template_id.notes,
                'attachment_ids': attachments,
                'concept_phase_id' : self.concept_template_id.concept_phase_id.id,
                'sub_phase_id' : self.concept_template_id.sub_phase_id.id,
                'concept_specialty_id' : self.concept_template_id.concept_specialty_id.id,
                'concept_template_id': self.concept_template_id.id,
        })
        for line in self.concept_template_id.template_line_ids:
            price_factor, qty_factor, para_attributes = self._find_product_factor(line.product_id)
            vals = {
                'budget_id': departure.budget_id.id,
                'parent_id': departure.id,
                'name': line.name,
                'code': line.code,
                'quantity': line.quantity,
                'amount_fixed': line.price * price_factor * self.exchange_rate,
                'available': line.available * qty_factor,
                'product_id': line.product_id.id if line.product_id else False,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'type': CONCEPT_TYPE[line.type],
                'concept_template_line_id': line.id,
            }
            rec_ = departure.child_ids.create(vals)
            if rec_.type == 'material':
                rec_.waste = line.dep
            elif rec_.type == 'equip':
                rec_.depreciation = line.dep


            departure.write({'param_attribute_ids': para_attributes})
        departure.budget_id.update_amount()
        return self.concept_id.action_view_concept()

    def _find_product_factor(self, product_id):
        price_factor = 1
        qty_factor = 1
        parameters = []
        if product_id:
            for line in self.attribute_line_ids:
                if product_id.id in line.parameter_id.product_ids.ids:
                    for value in line.parameter_id.value_ids.filtered_domain([('attribute_value_id','=',line.parameter_value_id.attribute_value_id.id)]):
                        price_factor *= value.price_factor
                        qty_factor *= value.qty_factor
                        parameters.append((0,0,{
                            'parameter_id': line.parameter_id.id,
                            'parameter_value_id': line.parameter_value_id.id,
                        }))

        return [price_factor,qty_factor,parameters]


class BimConceptTemplateAttribute(models.TransientModel):
    _name = 'bim.concept.template.attribute'
    _description = 'Bim Concept Template Attribute'

    wizard_id = fields.Many2one('bim.concept.template.wizard')
    parameter_ids = fields.Many2many('bim.parameter', related='wizard_id.parameter_ids')
    parameter_id = fields.Many2one('bim.parameter', domain="[('id','in',parameter_ids)]", required=True)
    parameter_value_id = fields.Many2one('bim.parameter.value', required=True, domain="[('parameter_id','=',parameter_id)]")

    @api.onchange('parameter_id')
    def onchange_parameter_id(self):
        self.parameter_value_id = False
