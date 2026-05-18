# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class BimBudgetCleanWzd(models.TransientModel):
    _name = 'bim.budget.clean.wzd'
    _description = 'Bim Budget Clean Wzd'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['budget_id'] = self._context.get('active_id')
        return res

    budget_id = fields.Many2one('bim.budget', string='Budget', readonly=True)
    labor = fields.Boolean('Labor')
    material = fields.Boolean('Material')
    equipment = fields.Boolean('Equipment')
    aux = fields.Boolean('Function / Administrative')
    empty_concepts = fields.Boolean('Empty Concepts')

    def action_clean_budget(self):
        if not self.labor and not self.material and not self.equipment and not self.aux and not self.empty_concepts:
            raise ValidationError(_("It is necessary to check options to clean budget!"))
        concept_types = []
        if self.labor:
            concept_types.append('labor')
        if self.equipment:
            concept_types.append('equip')
        if self.material:
            concept_types.append('material')
        if self.aux:
            concept_types.append('aux')
        domain = [('type','in',concept_types)]
        self.budget_id.concept_ids.filtered_domain(domain).unlink()
        if self.empty_concepts:
            domain = [('type','in',('departure','chapter')),('child_ids','=',False),('amount_type','!=','fixed')]
            self.budget_id.concept_ids.filtered_domain(domain).unlink()



