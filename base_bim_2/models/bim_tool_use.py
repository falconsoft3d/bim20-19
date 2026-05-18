import logging

from odoo import _, api, fields, models, exceptions
from odoo.tools import format_datetime
_logger = logging.getLogger(__name__)


class BimBToolUse(models.Model):
    _name = 'bim.tool.use'
    _description = 'Budgets Use'

    project_id = fields.Many2one('bim.project', 'Project', ondelete="restrict", copy=True,
                                 domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", copy=True,
                                domain="[('project_id','=',project_id),('state_id.include_in_tools','=',True)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict", copy=True,
                                 domain="[('budget_id','=',budget_id),('type','=','departure')]")
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    product_id = fields.Many2one('product.product', domain="[('tool_ok','=',True)]", required=True)
    cost = fields.Float()
    total = fields.Float(compute='_compute_amount', store=True)
    date_start = fields.Datetime('Start', copy=False, default=fields.Datetime.now, required=True)
    date_end = fields.Datetime('End', copy=False)
    hours = fields.Float(compute='_compute_amount', store=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.cost = self.product_id.standard_price

    @api.depends('date_start','date_end','cost')
    def _compute_amount(self):
        for use in self:
            hours = 0
            total = 0
            if use.date_end:
                hours = (use.date_end - use.date_start).total_seconds() / 3600
                total = use.cost * hours
            use.hours = hours
            use.total = total

    @api.constrains('date_start', 'date_end', 'product_id')
    def _check_validity(self):
        for use in self:
            last_use_before_date_start = use.search([
                ('product_id', '=', use.product_id.id),
                ('date_start', '<=', use.date_start),
                ('id', '!=', use.id),
            ], order='date_start desc', limit=1)
            if last_use_before_date_start and last_use_before_date_start.date_end and last_use_before_date_start.date_end > use.date_start:
                raise exceptions.ValidationError(
                    _("Cannot create new tool use record for %(tool_name)s, the tool was already used on %(datetime)s") % {
                        'tool_name': use.product_id.name,
                        'datetime': format_datetime(self.env, use.date_start, dt_format=False),
                    })
            if not use.date_end:
                no_date_end_use = use.search([
                    ('product_id', '=', use.product_id.id),
                    ('date_end', '=', False),
                    ('id', '!=', use.id),
                ], order='date_start desc', limit=1)
                if no_date_end_use:
                    raise exceptions.ValidationError(
                        _("Cannot create new tool use record for %(tool_name)s, the tool hasn't returned since %(datetime)s") % {
                            'tool_name': use.product_id.name,
                            'datetime': format_datetime(self.env, no_date_end_use.date_start, dt_format=False),
                        })
            else:
                last_use_before_date_end = use.search([
                    ('product_id', '=', use.product_id.id),
                    ('date_start', '<', use.date_end),
                    ('id', '!=', use.id),
                ], order='date_start desc', limit=1)
                if last_use_before_date_end and last_use_before_date_start != last_use_before_date_end:
                    raise exceptions.ValidationError(
                        _("Cannot create new tool use record for %(tool_name)s, the tool was already used on %(datetime)s") % {
                            'tool_name': use.product_id.name,
                            'datetime': format_datetime(self.env, last_use_before_date_end.date_start,
                                                        dt_format=False),
                        })



