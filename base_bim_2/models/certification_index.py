import logging

from odoo import _, api, fields, models, exceptions
from odoo.tools import format_datetime
_logger = logging.getLogger(__name__)


class CertificationIndex(models.Model):
    _name = 'certification.index'
    _description = 'Certification Index'

    name = fields.Date('Date', required=True, default=fields.Date.today)
    index = fields.Float('Index', required=True, default=1.0)
    budget_id = fields.Many2one('bim.budget', 'Budget', required=True)
    value = fields.Float('Value', compute='_compute_value', store=True)

    @api.depends('name', 'budget_id', 'index')
    def _compute_value(self):
        for record in self:
            certification_index_ids = self.search([('budget_id', '=', record.budget_id.id)], order='name asc')
            this_index = record.index
            if certification_index_ids:
                first_index = certification_index_ids[0].index
                if this_index > 0  and first_index > 0:

                    print('this_index', this_index)
                    print('first_index', first_index)

                    record.value = (1 * this_index) / first_index
                elif this_index == first_index:
                    record.value = 1
                else:
                    record.value = 1
            else:
                record.value = 1


