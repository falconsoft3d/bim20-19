# coding: utf-8
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BimResourceTemplateWizard(models.TransientModel):
    _name = 'bim.resource.template.wizard'
    _description = 'Bim Resource Template Wizard'


    bim_resource_template_id = fields.Many2one('bim.resource.template', "Resource Template", required=True)
    concept_id = fields.Many2one('bim.concepts', "Concept", required=True)

    @api.model
    def default_get(self, fields):
        res = super(BimResourceTemplateWizard, self).default_get(fields)
        res['concept_id'] = self._context.get('active_id', False)
        return res



    def do_action(self):
        resource_template_obj = self.env['bim.resource.template']
        concept_id = self.concept_id

        if not concept_id:
            raise ValidationError(_('No concept found'))

        resource_template_id = self.bim_resource_template_id

        if not resource_template_id:
            raise ValidationError(_('No resource template found'))

        for line in resource_template_id.line_ids:

            if line.resource_type == 'H':
                type = 'labor'
            elif line.resource_type == 'M':
                type = 'material'
            elif line.resource_type == 'Q':
                type = 'equipment'

            bim_concept_new_id = self.env['bim.concepts'].create({
                'name': line.product_id.name,
                'code': line.product_id.default_code if line.product_id.default_code else line.product_id.id,
                'type': type,
                'parent_id': concept_id.id,
                'budget_id': concept_id.budget_id.id,
                'quantity': line.quantity,
                'amount_fixed' : line.product_id.standard_price,
            })
