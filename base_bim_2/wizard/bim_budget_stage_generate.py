# coding: utf-8
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BimBudgetStageWizard(models.TransientModel):
    _name = 'bim.budget.stage.wizard'
    _description = 'Budget Stages'

    name = fields.Selection([
        ('W', 'Weekly'),
        ('Q', 'Biweekly'),
        ('M', 'Monthly'),
        ('B', 'Bimonthly'),
        ('T', 'Quarterly'),
        ('S', 'Biannual') ], string="Frequency", default='M')



    def _get_default_date_start(self):
        budget = self.env['bim.budget'].browse(self._context.get('active_id'))
        if not budget.stage_ids:
            return budget.date_start
        else:
            last_stage = budget.stage_ids.sorted(lambda r: r.date_stop)[-1]
            return last_stage.date_stop

    def _get_default_date_end(self):
        budget = self.env['bim.budget'].browse(self._context.get('active_id'))
        if not budget.stage_ids:
            return budget.date_end
        else:
            last_stage = budget.stage_ids.sorted(lambda r: r.date_stop)[-1]
            return last_stage.date_stop

    date_start = fields.Date('Start Date', default= _get_default_date_start)
    date_end = fields.Date('End Date', default= _get_default_date_end)

    def do_generate(self):
        values = []
        budget_id = self._context.get('active_id')
        interval = self.name == 'S' and 6 or \
                   self.name == 'T' and 3 or \
                   self.name == 'B' and 2 or \
                   self.name == 'M' and 1 or \
                   self.name == 'Q' and 15 or 7

        budget = self.env['bim.budget'].browse(budget_id)
        budget.create_stage(self.date_start, self.date_end, interval)

        stages = budget.mapped('stage_ids')
        action = self.env.ref('base_bim_2.action_bim_budget_stage').sudo().read()[0]
        if len(stages) > 0:
            action['domain'] = [('id', 'in', stages.ids),('budget_id', '=', budget.id)]
            action['context'] = {'default_budget_id': budget.id}
        return action

