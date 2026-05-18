from odoo import api, fields, models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    budget_ids = fields.One2many('bim.budget', 'pricelist_id', string='Budgets')
    budget_count = fields.Integer(compute='_compute_budget_count', string='Budget Count', store=True)

    @api.depends('budget_ids')
    def _compute_budget_count(self):
        for pricelist in self:
            pricelist.budget_count = len(pricelist.budget_ids)


    def action_view_budgets(self):
        budgets = self.mapped('budget_ids')
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        action['domain'] = [('id', 'in', budgets.ids)]
        action['context'] = {'default_pricelist_id': self.id, 'default_currency_id': self.currency_id.id, 'create': 0}
        return action

