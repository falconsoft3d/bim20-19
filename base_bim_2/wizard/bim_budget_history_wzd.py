# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class BimAjustBudgetWzd(models.TransientModel):
    _name = 'bim.budget.history.wzd'
    _description = 'Budget History WZD'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['history_id'] = self._context.get('active_id')
        if res['history_id']:
            history = self.env['bim.budget.history'].browse(res['history_id'])
            deleted_concepts = history.history_line_ids.filtered_domain([('concept_id', '=', False)])
            if deleted_concepts:
                message = _("Some Concepts were deleted:")
                for history_line in deleted_concepts:
                    message += "\n"+_('%s - Quantity: %s - Price: %s %s') % (history_line.name,history_line.quantity,history_line.price,history.currency_id.symbol)
                res['deleted_concepts_message'] = message
        return res

    history_id = fields.Many2one(comodel_name="bim.budget.history", string="Budget History")
    save_current = fields.Boolean(default=True)
    deleted_concepts_message = fields.Text(readonly=True, default="")

    def action_set_budget_history(self):
        if self.save_current:
            self.history_id.budget_id.update_amount()
            self.history_id.create({'budget_id': self.history_id.budget_id.id})
        self.history_id.action_load_budget_history()
