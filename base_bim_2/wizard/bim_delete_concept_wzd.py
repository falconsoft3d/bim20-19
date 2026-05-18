# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class BimDeleteConceptWzd(models.TransientModel):
    _name = 'bim.delete.concept.wzd'
    _description = 'Bim Delete Concept Wzd'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['budget_id'] = self._context.get('active_id')
        return res

    budget_id = fields.Many2one('bim.budget', string='Budget', readonly=True)
    product_id = fields.Many2one('product.product', string='Product')

    def action_delete_concept(self):
        if not self.budget_id and not self.product_id:
            raise ValidationError(_("The product and budget are required!"))

        concept_to_delete_ids = self.env['bim.concepts'].search([
            ('budget_id', '=', self.budget_id.id),
            ('product_id', '=', self.product_id.id)
        ])

        if concept_to_delete_ids:
            concept_to_delete_ids.unlink()
        else:
            raise ValidationError(_("The concept does not exist!"))