from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    copied_bim_concept_id = fields.Many2one('bim.concepts', 'Concept to copy')
    cut_bim_concept_id = fields.Many2one('bim.concepts', 'Concept to cut')
    budget_ids = fields.One2many('bim.budget','user_id')
    bim_project_ids = fields.One2many('bim.project','user_id')
    check_bim_default = fields.Boolean('Check Bim Default', default=False)

    concept_template_ids = fields.Many2many('bim.concept.template', string='APUs')
    concept_bim_concept_ids = fields.Many2many('bim.concepts', string='Departures')
    copy_bim_budget_ids = fields.Many2many('bim.budget', string='Budgets')

    @api.model
    def copy_bim_concept(self, user_id, parent_id, budget_id):
        _logger.info('copy_bim_concept')
        if not isinstance(user_id, int):
            user_id = int(user_id)
        if not isinstance(parent_id, int):
            parent_id = int(parent_id)
        user = self.browse(user_id)
        if (user.cut_bim_concept_id.type or user.copied_bim_concept_id.type) != 'chapter' and not parent_id:
            return False
        if user.copied_bim_concept_id:
            new_concept = self.recursive_create(user.copied_bim_concept_id, parent_id, budget_id)
        elif user.cut_bim_concept_id:
            new_concept = user.cut_bim_concept_id

            user.cut_bim_concept_id = False
            new_concept.write({'parent_id': parent_id or False})
            if budget_id:
                self.recursive_budget_edit(new_concept, budget_id)

        try:
            _parent_id = self.env['bim.concepts'].search([('id', '=', parent_id)], limit=1)
            new_concept.budget_id = _parent_id.budget_id.id
            new_concept.project_id = _parent_id.project_id.id
        except:
            pass

        return new_concept.id

    @api.model
    def recursive_budget_edit(self, concepts, budget_id):
        concepts.write({'budget_id': budget_id})
        childs = concepts.mapped('child_ids')
        if childs:
            self.recursive_budget_edit(childs, budget_id)
        return True

    @api.model
    def recursive_create(self, to_copy, parent_id, budget_id):
        copied = to_copy.copy({'parent_id': False})
        for child in to_copy.child_ids:
            self.recursive_create(child, copied.id, budget_id)
        for measure in to_copy.measuring_ids:
            if measure.space_id.budget_id.id != budget_id:
                space = self.env['bim.budget.space'].search([('budget_id', '=', budget_id), ('code', '=', measure.space_id.code)],limit=1).id or False
                if not space and measure.space_id:
                    space = measure.space_id.copy({'budget_id': budget_id}).id
            else:
                space = measure.space_id.id
            measure.copy({'concept_id': copied.id, 'space_id': space, 'stage_id': None})
        if parent_id:
            copied.write({'parent_id': parent_id})
        if budget_id:
            copied.write({'budget_id': budget_id})
        return copied


class BimProjectAllowed(models.Model):
    _name = 'bim.project.allowed'
    _description = 'Bim Project Allowed'

    user_id = fields.Many2one('res.users')
    project_id = fields.Many2one('bim.project')
