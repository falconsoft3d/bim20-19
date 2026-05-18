# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

CONCEPT_NAME = {
    'departure': 'Departure',
    'chapter': 'Chapter',
}

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    bim_project_id = fields.Many2one('bim.project', 'Project', tracking=True, domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", domain="[('project_id','=',bim_project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict", domain="[('budget_id','=',budget_id),('type','=','departure')]")
    created_budget_ids = fields.Many2many('bim.budget', string='Budgets')
    budget_count = fields.Integer(compute='_compute_budget_count', string='Budgets Count')

    @api.depends('created_budget_ids')
    def _compute_budget_count(self):
        for order in self:
            order.budget_count = len(order.created_budget_ids)

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values.update({
            'project_id': self.bim_project_id.id or False,
            'budget_id': self.budget_id.id or False,
            'concept_id': self.concept_id.id or False,
        })
        return values

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped,final,date)
        for move in moves:
            if move.project_id and move.project_id.analytic_id:
                for line in move.invoice_line_ids:
                    line.analytic_account_id = move.project_id.analytic_id.id
        return moves

    def action_confirm(self):
        confirmation = super().action_confirm()
        for picking in self.picking_ids:
            if not picking.bim_project_id and self.bim_project_id:
                picking.bim_project_id = self.bim_project_id.id
            if not picking.bim_budget_id and self.budget_id:
                picking.bim_budget_id = self.budget_id.id
            if not picking.bim_concept_id and self.concept_id:
                picking.bim_concept_id = self.concept_id.id
        return confirmation

    def _create_budget_concept(self, budget_id, bim_type, parent_id):
        self.ensure_one()
        concept = budget_id.concept_ids.create({
            'name': "%s"%(_(CONCEPT_NAME[bim_type])),
            'budget_id': budget_id.id,
            'code': self.name,
            'parent_id': parent_id.id if parent_id else False,
            'quantity': 1,
            'type': bim_type})
        return concept

    def _create_sale_budget(self, project_id):
        self.ensure_one()
        budget_vals = {
            'name': "%s - %s "%(self.name, self.partner_id.name),
            'project_id': project_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
        }
        budget_id = self.env['bim.budget'].create(budget_vals)
        self._assign_assets_to_budget(budget_id)
        return budget_id

    def _assign_assets_to_budget(self, budget_id):
        self.created_budget_ids = [(4, budget_id.id)]
        if self.amount_tax > 0:
            template = self.env['bim.assets.template'].search([('sale_ok','=',True)], limit=1)
            if template:
                budget_id.write({'template_id': template.id})
                budget_id.onchange_template_id()

    def action_view_budgets(self):
        budgets = self.mapped('created_budget_ids')
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        if len(budgets) > 0:
            action['domain'] = [('id', 'in', budgets.ids)]
            action['context'] = {'create': 0}
            return action
        return False


