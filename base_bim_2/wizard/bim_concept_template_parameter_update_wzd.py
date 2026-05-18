# coding: utf-8
from odoo import api, fields, models, _

CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux'}


class BimConceptTemplateParameterUpdateWizard(models.TransientModel):
    _name = 'bim.concept.template.parameter.update.wizard'
    _description = 'Bim Concept Template Parameter Update Wizard'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['concept_id'] = self._context.get('active_id', False)
        return res

    concept_id = fields.Many2one('bim.concepts', required=True, readonly=True)
    attribute_line_ids = fields.Many2many('bim.concepts.parameter.attribute','update_concepts_params_rel')

    @api.onchange('concept_id')
    def onchange_concept_id(self):
        self.attribute_line_ids = self.concept_id.param_attribute_ids.ids or []

    def action_apply_changes(self):
        for line in self.attribute_line_ids:
            price_factor, qty_factor = self._find_product_factor()
            for child in self.concept_id.child_ids.filtered_domain([('product_id','in',line.parameter_id.product_ids.ids)]):
                child.write({
                    'available': child.concept_template_line_id.available * qty_factor,
                    'amount_fixed': child.concept_template_line_id.price * price_factor,
                })
                child.update_amount()

    def _find_product_factor(self):
        price_factor = 1
        qty_factor = 1
        for line in self.attribute_line_ids:
            for value in line.parameter_id.value_ids.filtered_domain([('attribute_value_id','=',line.parameter_value_id.attribute_value_id.id)]):
                price_factor *= value.price_factor
                qty_factor *= value.qty_factor
        return [price_factor,qty_factor]


