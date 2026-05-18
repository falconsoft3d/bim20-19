# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class BimBudgetHistory(models.Model):
    _name = 'bim.budget.history'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = "id desc"
    _description = "Budget History"

    def _default_description(self):
        return _("Version %s") % datetime.strftime(datetime.now(), '%d/%m/%Y')

    date = fields.Date('Date', required=True, default=lambda self: fields.Date.context_today(self), readonly=True)
    history_line_ids = fields.One2many('bim.budget.history.line','history_id')
    budget_id = fields.Many2one('bim.budget', readonly=True)
    user_id = fields.Many2one('res.users', string='User', readonly=True, default=lambda self: self.env.user)
    active = fields.Boolean(default=True)
    name = fields.Char('Reference', copy=False, readonly=True, default=lambda x: _('New'))
    description = fields.Char('Description', copy=False, required=True, default=_default_description)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id')
    balance = fields.Float(readonly=True, digits='BIM price')
    line_count = fields.Integer(compute='_compute_line_count')
    amount_total_labor = fields.Float(string='Total Labor', readonly=True, digits='BIM price')
    amount_total_equip = fields.Float(string='Total Equipment', readonly=True, digits='BIM price')
    amount_total_material = fields.Float(string='Total Material', readonly=True, digits='BIM price')
    amount_total_other = fields.Float(string='Total Other', readonly=True, digits='BIM price')
    amount_certified = fields.Float(string='Certified', readonly=True, digits='BIM price')
    total_assets = fields.Float(string='Total Assets', readonly=True, digits='BIM price')
    history_base = fields.Boolean(default=False)

    @api.depends('history_line_ids')
    def _compute_line_count(self):
        for history in self:
            history.line_count = len(history.history_line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.budget.history') or 'New'

        records = super().create(vals_list)

        for history in records:
            if history.budget_id.history_count == 1:
                history.history_base = True

            history.balance = history.budget_id.balance
            history.amount_total_labor = history.budget_id.amount_total_labor
            history.amount_total_equip = history.budget_id.amount_total_equip
            history.amount_total_material = history.budget_id.amount_total_material
            history.amount_total_other = history.budget_id.amount_total_other
            history.amount_certified = history.budget_id.certified
            history.total_assets = history.budget_id.total_main_asset

            for chapter in history.budget_id.concept_ids.filtered_domain([
                ('type', '=', 'chapter'),
                ('parent_id', '=', False)
            ]):
                self._helper_create_history_line(chapter, history)
                for child in chapter.child_ids:
                    self._create_recursive_history(child, history)

        return records

    def _helper_create_history_line(self,concept, history):
        history.history_line_ids.create({
            'history_id': history.id,
            'sequence': concept.sequence,
            'name': concept.display_name,
            'concept_id': concept.id,
            'quantity': concept.quantity,
            'price': concept.amount_fixed if concept.amount_type == 'fixed' else concept.amount_compute
        })

    def _create_recursive_history(self, concept, history):
        self._helper_create_history_line(concept, history)
        if concept.child_ids:
            for child in concept.child_ids:
                self._create_recursive_history(child,history)

    def action_load_budget_history(self):
        if not self.history_line_ids:
            raise UserError(_("There is not Concept History to be applied to Budget"))
        for history_line in self.history_line_ids.filtered_domain([('concept_id','!=',False)]):
            history_line.concept_id.quantity = history_line.quantity
            if history_line.concept_id.type not in ('chapter','departure'):
                history_line.concept_id.amount_fixed = history_line.price

        self.budget_id.history_description = self.description
        self.budget_id.update_amount()
        self.message_post(body="History Applied to it's Budget")
        self.budget_id.message_post(
            body=_("History %(desc)s Applied", desc=self.description or '')
        )


class BimBudgetHistoryLine(models.Model):
    _name = 'bim.budget.history.line'
    _description = "Budget History Line"
    # _order = "concept_parent, concept, sequence asc"

    history_id = fields.Many2one('bim.budget.history', ondelete='cascade')
    concept_id = fields.Many2one('bim.concepts')
    name = fields.Char()
    quantity = fields.Float('Quantity', digits='BIM qty')
    price = fields.Float('Price', digits='BIM price')
    currency_id = fields.Many2one('res.currency', related='history_id.currency_id')
    sequence = fields.Integer()




