# -*- coding: utf-8 -*-
# Part of Marlon Falcon Hernandez. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class BimCashFlowGenerator(models.Model):
    _description = "Bim Cash Flow Generator"
    _name = 'bim.cash.flow.generator'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default='New')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    bim_project_id = fields.Many2one('bim.project', string="Project")
    bim_budget_id = fields.Many2one('bim.budget', string="Budget")
    contact_id = fields.Many2one('res.partner', string="Contact")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    bim_cash_flow_category_id = fields.Many2one('bim.cash.flow.category', string="Category")
    type = fields.Selection([
                                ('purchase', 'Purchase'),
                                ('sale', 'Sale'),
                                ('by_departure_and_stage', 'By Departure and Stage'),
                                ('linear_distribution_sales_budget', 'Linear Distribution Sales Budget'),
                                ('gantt_distribution_sales_budget', 'Gantt Distribution Sales Budget'),
                                ('linear_distribution_cost_budget', 'Linear Distribution Costs Budget'),
                             ], string="Type", default='purchase')

    journal_id = fields.Many2one('account.journal', string="Journal")
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id, required=True)

    note = fields.Text(string="Note")


    state = fields.Selection([
                                ('draft', 'Draft'),
                                ('done', 'Done')
                                ], string="State", default='draft')

    bim_cash_flow_ids = fields.One2many('bim.cash.flow','bim_cash_flow_generator_id','Cash Flow')
    bim_cash_flow_count = fields.Integer('Cash Flow Count', compute="_get_bim_cash_flow_count")
    calculation_factor = fields.Float(string="Calculation Factor", default=1.0)
    initial_balance = fields.Monetary(string="Initial Balance")

    @api.onchange('bim_project_id')
    def _onchange_bim_project_id(self):
        if self.bim_project_id:
            self.contact_id = self.bim_project_id.customer_id

    def _get_bim_cash_flow_count(self):
        for generator in self:
            generator.bim_cash_flow_count = len(generator.bim_cash_flow_ids)

    def action_view_bim_cash_flow(self):
        action = self.env.ref('base_bim_2.action_bim_cash_flow').sudo().read()[0]
        action['domain'] = [('bim_cash_flow_generator_id', '=', self.id)]
        action['context'] = {'default_default_bim_cash_flow_generator_id': self.id}
        return action


    def exe_done(self):
        for rec in self:
            if not rec.type:
                raise UserError(_("You must select a type"))

            if not rec.contact_id or not rec.bim_project_id:
                raise UserError(_("You must select a contact or project"))

            """
            COMPRAS
            """
            if rec.type == 'purchase':
                if rec.contact_id:
                    purchase_ids = self.env['purchase.order'].search([('partner_id', '=', rec.contact_id.id), ('state', 'in', ['purchase', 'done'])])

                    if purchase_ids:
                        for purchase in purchase_ids:
                            # revisamos que no tengamos una con esa referencia en note
                            bim_cash_flow_id = self.env['bim.cash.flow'].search([('note', '=', purchase.name)])

                            if not bim_cash_flow_id:
                                bim_cash_flow_id = self.env['bim.cash.flow'].create({
                                    'company_id': rec.company_id.id,
                                    'budgeted': purchase.amount_total * rec.calculation_factor,
                                    'date': purchase.date_order,
                                    'currency_id': rec.currency_id.id,
                                    'bim_project_id': purchase.project_id.id,
                                    'bim_budget_id': purchase.budget_id.id,
                                    'contact_id': rec.contact_id.id,
                                    'journal_id': rec.journal_id.id,
                                    'bim_cash_flow_generator_id': rec.id,
                                    'note': purchase.name,
                                    'type': 'expense',
                                    'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                                })
                    else:
                        raise UserError(_("Not found purchase orders for this contact"))

                if rec.bim_project_id:
                    purchase_ids = self.env['purchase.order'].search([('project_id', '=', rec.bim_project_id.id), ('state', 'in', ['purchase', 'done'])])

                    if purchase_ids:
                        for purchase in purchase_ids:
                            # revisamos que no tengamos una con esa referencia en note
                            bim_cash_flow_id = self.env['bim.cash.flow'].search([('note', '=', purchase.name)])

                            if not bim_cash_flow_id:
                                bim_cash_flow_id = self.env['bim.cash.flow'].create({
                                    'company_id': rec.company_id.id,
                                    'budgeted': purchase.amount_total * rec.calculation_factor,
                                    'date': purchase.date_order,
                                    'currency_id': rec.currency_id.id,
                                    'bim_project_id': purchase.project_id.id,
                                    'bim_budget_id': purchase.budget_id.id,
                                    'contact_id': rec.contact_id.id,
                                    'journal_id': rec.journal_id.id,
                                    'bim_cash_flow_generator_id': rec.id,
                                    'note': purchase.name,
                                    'type': 'expense',
                                    'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                                })
                    else:
                        raise UserError(_("Not found purchase orders for this project"))


            """
            VENTAS
            """
            if rec.type == 'sale':
                if rec.contact_id:
                    sale_ids = self.env['sale.order'].search([('partner_id', '=', rec.contact_id.id), ('state', 'in', ['sale', 'done'])])

                    if sale_ids:
                        for sale in sale_ids:
                            # revisamos que no tengamos una con esa referencia en note
                            bim_cash_flow_id = self.env['bim.cash.flow'].search([('note', '=', sale.name)])

                            if not bim_cash_flow_id:
                                bim_cash_flow_id = self.env['bim.cash.flow'].create({
                                    'company_id': rec.company_id.id,
                                    'budgeted': sale.amount_total * rec.calculation_factor,
                                    'date': sale.date_order,
                                    'currency_id': rec.currency_id.id,
                                    'bim_project_id': rec.bim_project_id.id,
                                    'bim_budget_id': rec.bim_budget_id.id,
                                    'contact_id': rec.contact_id.id,
                                    'journal_id': rec.journal_id.id,
                                    'bim_cash_flow_generator_id': rec.id,
                                    'note': sale.name,
                                    'type': 'income',
                                    'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                                })
                    else:
                        raise UserError(_("Not found sale orders for this contact"))

            if rec.type == 'linear_distribution_sales_budget':
                # reviso que tengamos un presupuesto seleccionado
                if not rec.bim_budget_id:
                    raise UserError(_("You must select a budget"))

                # reviso que ese presupuesto tenga etapas
                if not rec.bim_budget_id.stage_ids:
                    raise UserError(_("The selected budget does not have stages"))


                number_state = len(rec.bim_budget_id.stage_ids)
                # recorro las etapas del presupuesto
                for stage in rec.bim_budget_id.stage_ids:
                    # revisamos que no tengamos una con esa referencia en note
                    bim_cash_flow_id = self.env['bim.cash.flow'].search([
                                    ('note', '=', stage.name),
                                    ('type','=', 'income'),
                                    ('bim_cash_flow_generator_id', '=', rec.id)])

                    if not bim_cash_flow_id:
                        balance = rec.bim_budget_id.sale_import if rec.bim_budget_id.sale_import > 0 else rec.bim_budget_id.balance
                        bim_cash_flow_id = self.env['bim.cash.flow'].create({
                            'company_id': rec.company_id.id,
                            'budgeted': balance/number_state * rec.calculation_factor,
                            'date': stage.date_stop,
                            'currency_id': rec.currency_id.id,
                            'bim_project_id': rec.bim_project_id.id,
                            'bim_budget_id': rec.bim_budget_id.id,
                            'bim_budget_stage_id': stage.id,
                            'contact_id': rec.contact_id.id if rec.contact_id else rec.bim_project_id.customer_id.id,
                            'journal_id': rec.journal_id.id,
                            'bim_cash_flow_generator_id': rec.id,
                            'note': stage.name,
                            'type': 'income',
                            'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                        })

            if rec.type == 'gantt_distribution_sales_budget':
                # reviso que tengamos un presupuesto seleccionado
                if not rec.bim_budget_id:
                    raise UserError(_("You must select a budget"))

                # reviso que ese presupuesto tenga etapas
                if not rec.bim_budget_id.stage_ids:
                    raise UserError(_("The selected budget does not have stages"))


                number_state = len(rec.bim_budget_id.stage_ids)
                budget = rec.bim_budget_id

                # recorro las etapas del presupuesto
                for stage in rec.bim_budget_id.stage_ids:
                    # revisamos que no tengamos una con esa referencia en note
                    amount = 0
                    bim_cash_flow_id = self.env['bim.cash.flow'].search([
                                    ('note', '=', stage.name),
                                    ('type','=', 'income'),
                                    ('bim_cash_flow_generator_id', '=', rec.id)])

                    if not bim_cash_flow_id:
                        departure_ids = self.env['bim.concepts'].search([
                                            ('stage_id', '=', stage.id),
                                            ('budget_id', '=', budget.id),
                                            ('acs_date_end', '>=', stage.date_stop),
                                            ('acs_date_end', '<=', stage.date_stop),
                                        ])

                        qty_resource = 0
                        if departure_ids:
                            for departure in departure_ids:
                                concept_ids = self.env['bim.concepts'].search([
                                    ('parent_id', '=', departure.id),
                                ])
                                for concept in concept_ids:
                                    amount += concept.balance * concept.parent_id.quantity


                        if amount > 0:
                            bim_cash_flow_id = self.env['bim.cash.flow'].create({
                                'company_id': rec.company_id.id,
                                'budgeted': amount * rec.calculation_factor,
                                'date': stage.date_stop,
                                'currency_id': rec.currency_id.id,
                                'bim_project_id': rec.bim_project_id.id,
                                'bim_budget_id': rec.bim_budget_id.id,
                                'bim_budget_stage_id': stage.id,
                                'contact_id': rec.contact_id.id if rec.contact_id else rec.bim_project_id.customer_id.id,
                                'journal_id': rec.journal_id.id,
                                'bim_cash_flow_generator_id': rec.id,
                                'note': stage.name,
                                'type': 'expense',
                                'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                            })


            if rec.type == 'by_departure_and_stage':
                departure_ids = self.env['bim.concepts'].search([
                                                ('budget_id', '=', rec.bim_budget_id.id),
                                                ('type', '=', 'departure'),
                                              ])

                for dep in departure_ids:
                    bim_cash_flow_id = self.env['bim.cash.flow'].create({
                            'company_id': rec.company_id.id,
                            'budgeted': dep.balance * rec.calculation_factor,
                            'date': dep.acs_date_end,
                            'currency_id': self.bim_budget_id.currency_id.id,
                            'bim_project_id': rec.bim_budget_id.project_id.id,
                            'bim_concept_id': dep.id,
                            'bim_budget_id': rec.bim_budget_id.id,
                            'bim_budget_stage_id': dep.stage_id.id,
                            'contact_id': rec.contact_id.id if rec.contact_id else rec.bim_project_id.customer_id.id,
                            'journal_id': rec.journal_id.id,
                            'bim_cash_flow_generator_id': rec.id,
                            'note': rec.note,
                            'type': 'expense',
                            'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                    })


            if rec.type == 'linear_distribution_cost_budget':
                # reviso que tengamos un presupuesto seleccionado
                if not rec.bim_budget_id:
                    raise UserError(_("You must select a budget"))

                # reviso que ese presupuesto tenga etapas
                if not rec.bim_budget_id.stage_ids:
                    raise UserError(_("The selected budget does not have stages"))


                number_state = len(rec.bim_budget_id.stage_ids)
                # recorro las etapas del presupuesto
                for stage in rec.bim_budget_id.stage_ids:
                    # revisamos que no tengamos una con esa referencia en note
                    bim_cash_flow_id = self.env['bim.cash.flow'].search([
                                    ('note', '=', stage.name),
                                    ('type','=', 'expense'),
                                    ('bim_cash_flow_generator_id', '=', rec.id)])

                    if not bim_cash_flow_id:
                        balance = rec.bim_budget_id.amount_total_labor + rec.bim_budget_id.amount_total_equip + rec.bim_budget_id.amount_total_material + rec.bim_budget_id.amount_total_other
                        bim_cash_flow_id = self.env['bim.cash.flow'].create({
                            'company_id': rec.company_id.id,
                            'budgeted': balance/number_state,
                            'date': stage.date_stop,
                            'currency_id': rec.currency_id.id,
                            'bim_project_id': rec.bim_project_id.id,
                            'bim_budget_id': rec.bim_budget_id.id,
                            'bim_budget_stage_id': stage.id,
                            'contact_id': rec.contact_id.id if rec.contact_id else rec.bim_project_id.customer_id.id,
                            'journal_id': rec.journal_id.id,
                            'bim_cash_flow_generator_id': rec.id,
                            'note': stage.name,
                            'type': 'expense',
                            'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                        })



            if rec.initial_balance > 0:
                stage_ids = rec.bim_budget_id.stage_ids
                stage = stage_ids[0]

                bim_cash_flow_id = self.env['bim.cash.flow'].create({
                    'company_id': rec.company_id.id,
                    'budgeted': rec.initial_balance,
                    'date': stage.date_stop,
                    'currency_id': rec.currency_id.id,
                    'bim_project_id': rec.bim_project_id.id,
                    'bim_budget_id': rec.bim_budget_id.id,
                    'bim_budget_stage_id': stage.id,
                    'contact_id': rec.contact_id.id if rec.contact_id else rec.bim_project_id.customer_id.id,
                    'journal_id': rec.journal_id.id,
                    'bim_cash_flow_generator_id': rec.id,
                    'note': rec.journal_id.name + ' ' + _('Initial Balance'),
                    'type': 'income',
                    'bim_cash_flow_category_id' : rec.bim_cash_flow_category_id.id,
                })
            rec.state = 'done'

    def exe_draft(self):
        for rec in self:
            for cash in rec.bim_cash_flow_ids:
                cash.unlink()
            rec.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.cash.flow.generator') or 'New'
        return super().create(vals_list)

