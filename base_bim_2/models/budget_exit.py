# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

class BudgetExit(models.Model):
    _description = "Budget Exit"
    _name = 'budget.exit'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True, readonly=True, copy=False, index=True, default=lambda self: self.env['ir.sequence'].next_by_code('budget.exit'))
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    lines_ids = fields.One2many('budget.exit.line', 'budget_exit_id', string='Budget Exit Lines', copy=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('cancel', 'Cancelled'),
        ], string='State', default='draft', copy=False, tracking=True)


    def action_draft(self):
        self.state = 'draft'
        for line in self.lines_ids:
            if line.stock_picking_id:
                line.stock_picking_id.state = 'cancel'
                line.stock_picking_id.include_for_bim = False


    def action_validate(self):
        if not self.project_id.stock_location_id:
            self.project_id.create_warehouse()
            stock_location_id = self.project_id.stock_location_id
        else:
            stock_location_id = self.project_id.stock_location_id

        customer_location = self.env.ref('stock.stock_location_customers')


        for line in self.lines_ids:
            # creamos un albaran de salida por cada linea del presupuesto

            picking = self.env['stock.picking'].create({
                'origin': self.name,
                'location_id': stock_location_id.id,
                'location_dest_id': customer_location.id,
                'picking_type_id': self.env.ref('stock.picking_type_out').id,
                'company_id': self.company_id.id,
                'date': line.date,
                'scheduled_date': line.date,

                'bim_project_id': line.budget_id.project_id.id,
                'bim_budget_id': line.budget_id.id,
                'bim_concept_id': line.departure_id.id,
                'include_for_bim': True,

                'move_ids': [(0, 0, {
                    'name': line.concept_id.name,
                    'product_id': line.concept_id.product_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.concept_id.uom_id.id,
                    'date': line.date,
                    'product_cost': line.concept_id.amount_fixed,
                })],
            })
            picking.action_confirm()
            picking.action_assign()
            line.stock_picking_id = picking.id
            line.stock_picking_id.include_for_bim = True
            line.stock_picking_id.button_validate()
        self.state = 'validated'

class BudgetExitLine(models.Model):
    _description = "Budget Exit Line"
    _name = 'budget.exit.line'

    budget_id = fields.Many2one('bim.budget', 'Budget', related='budget_exit_id.budget_id', store=True, readonly=True)
    budget_exit_id = fields.Many2one('budget.exit', 'Budget Exit', ondelete="cascade")
    departure_id = fields.Many2one('bim.concepts', 'Departure', ondelete="cascade")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="cascade")
    qty = fields.Float('Quantity', default=0)
    date = fields.Date('Date', default=fields.Date.today)
    stock_picking_id = fields.Many2one('stock.picking', 'Stock Picking', readonly=True)