from odoo import _, fields, models
from odoo.exceptions import ValidationError


class BimCreateTask(models.TransientModel):
    _name = 'bim.create.task'
    _description = 'Bim Create Task'

    budget_id = fields.Many2one('bim.budget', 'Budget', required=True,
                                      default=lambda self: self.env.context.get('active_id')
                                )
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    def create_task(self):
        if not self.budget_id:
            raise ValidationError(_('Please select a budget'))

        all_concepts = self.env['bim.concepts'].search(
            [('budget_id', '=', self.budget_id.id),
             ('type', '=', 'labor')]
        )

        print(all_concepts)

        new_tasks = []

        for concept in all_concepts:
            print(concept)
            if concept.parent_id and concept.parent_id.type == 'departure':
                father = concept.parent_id
                vals = {
                        'desc': father.name,
                        'project_id': father.budget_id.project_id.id,
                        'budget_id':  father.budget_id.id,
                        'concept_id': father.id,
                        'company_id': father.company_id.id,
                        'load_work' : father.quantity,
                     }

                task_check = self.env['bim.task'].search(
                    [('concept_id', '=', father.id),
                     ('budget_id', '=', father.budget_id.id)]
                )

                if not task_check:
                    new_task = self.env['bim.task'].create(vals)
                    new_tasks.append(new_task.id)

        print(new_tasks)
        if new_tasks:
            return {
                    'name': _('Task'),
                            'view_type': 'form',
                            'view_mode': 'tree,form',
                            'res_model': 'bim.task',
                            'type': 'ir.actions.act_window',
                            'domain': [('id', 'in', new_tasks)],
                        }




