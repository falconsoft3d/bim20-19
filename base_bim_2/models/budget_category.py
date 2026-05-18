import logging

from odoo import _, api, fields, models, exceptions
from odoo.tools import format_datetime
_logger = logging.getLogger(__name__)


class BudgetCategory(models.Model):
    _name = 'budget.category'
    _description = 'Budget Category'

    name = fields.Char('Name', required=True)