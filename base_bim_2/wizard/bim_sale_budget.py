from odoo import fields, models, _
from odoo.exceptions import UserError

CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux'}


class BimSaleBudget(models.TransientModel):
    _name = 'bim.sale.budget'
    _description = 'Bim Sale Budget'

    sale_id = fields.Many2one('sale.order', 'Order')
    option = fields.Selection([('apu','Apu template'),('budget', 'Budget template'),('none','Without template')], 'Option', default='apu', required=True)
    project_id = fields.Many2one('bim.project', 'Project', domain="[('company_id', '=', company_id)]", required=True)
    company_id = fields.Many2one('res.company', 'Company', related='sale_id.company_id')

    def action_create_budget(self):
        budget_id = self._helper_create_budget()
        return budget_id.action_view_budget()

    def _helper_create_budget(self):
        budget_id = self.sale_id._create_sale_budget(self.project_id)
        if self.option == 'apu':
            self._helper_create_concepts_from_apu(budget_id)
        else:
            chapter = self.sale_id._create_budget_concept(budget_id, 'chapter', False)
            departure = self.sale_id._create_budget_concept(budget_id, 'departure', chapter)
            self.sale_id.order_line._create_order_line_concepts(budget_id, departure)
        return budget_id

    def _helper_create_concepts_from_apu_template(self, budget_id):
        self.template_id.create_chapters(budget_id)
        current_var_n = self.template_id.var_n
        order_lines_n = self.sale_id.order_line.filtered(lambda x: not x.display_type)
        if order_lines_n:
            self.template_id.var_n = order_lines_n[0].product_uom_qty
        for line in self.template_id.line_ids.filtered_domain([('type', '=', 'apu')]):
            quantity = line.qty_calc
            chapters = budget_id.concept_ids.filtered_domain(
                [('code', '=', line.parent_id.code), ('type', '=', 'chapter')])
            if chapters and quantity > 0:
                line.apu_id._helper_create_departure_from_template(budget_id, chapters[0], quantity)
        self.template_id.var_n = current_var_n

    def _helper_create_concepts_from_apu(self, budget_id):
        candidate_lines = self.sale_id.order_line.filtered(lambda x: not x.display_type and x.product_id.default_code)
        not_matched_order_lines = self.env['sale.order.line']
        apu_obj = self.env['bim.concept.template']
        for line in candidate_lines:
            apu = apu_obj.search([('code', '=', line.product_id.default_code)])
            if apu:
                apu._create_departure_from_template(budget_id, line.product_uom_qty)
            else:
                not_matched_order_lines |= line
        if not_matched_order_lines:
            chapter = self.sale_id._create_budget_concept(budget_id, 'chapter', False)
            departure = self.sale_id._create_budget_concept(budget_id, 'departure', chapter)
            not_matched_order_lines._create_order_line_concepts(budget_id, departure)

    def action_create_from_apu_template(self):
        quantity = self.sale_id.order_line.filtered(lambda x: not x.display_type)[0].product_uom_qty or 1
        action = self.env.ref('base_bim_2.bim_wizard_apu_action').sudo().read()[0]
        action['context'] = {'default_project_id': self.project_id.id, 'default_val_n': quantity, 'default_sale_id': self.sale_id.id}
        return action










