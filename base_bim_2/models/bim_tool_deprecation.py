import logging

from odoo import _, api, fields, models, exceptions
_logger = logging.getLogger(__name__)


class BimToolDeprecation(models.Model):
    _name = 'bim.tool.deprecation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Budgets Use'

    name = fields.Char(required=True)
    description = fields.Text(default="")

