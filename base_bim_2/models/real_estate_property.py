# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class RealEstateProperty(models.Model):
    _description = "Real Estate Property"
    _name = 'real.estate.property'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Name', copy=False)
    real_estate_development_id = fields.Many2one(comodel_name="real.estate.development", string="Development")
    real_estate_block_id = fields.Many2one(comodel_name="real.estate.block", string="Block")
    real_estate_lot_id = fields.Many2one(comodel_name="real.estate.lot", string="Lot")
    real_estate_prototype_id = fields.Many2one(comodel_name="real.estate.prototype", string="Prototype")

    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
    price = fields.Monetary('Price')
    cost = fields.Monetary('Cost')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    area = fields.Float('Area')
    project_ids = fields.Many2many('bim.project', string="Projects")
    budget_ids = fields.Many2many('bim.budget', string="Budgets")

    image_1920 = fields.Image("Image 1920", max_width=1920, max_height=1920)
    image_128 = fields.Image("Image 128", max_width=128, max_height=128, store=True)

    benefit = fields.Monetary('Benefit')
    state = fields.Selection([
        ('not_available', 'Not Available'),
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('blocked', 'Blocked'),
    ], string='State', default='not_available', required=True, copy=False, tracking=True)

    line_ids = fields.One2many('real.estate.property.line', 'real_estate_property_id', string='Lines', copy=True)


    def action_update(self):
        for record in self:
            record.exe_update()

    def exe_update(self):
        for record in self:
            cost = 0
            _logger.info("begin exe_update %s", record.name)


            """
            PRESUPUESTOS
            """
            bugdet_ids = record.env['bim.budget'].search([('property_ids', 'in', record.id)])
            for budget in bugdet_ids:
                _num = len(budget.property_ids)

                # sumamos las facturas que tenga ese presupuesto
                account_move_line_ids = record.env['account.move.line'].search([
                            ('budget_id', 'in', bugdet_ids.ids),
                            ('move_type', 'not in', ['out_invoice', 'out_refund']),
                        ])

                if account_move_line_ids:
                    cost += sum(account_move_line_ids.mapped('price_subtotal'))/_num

                # sumamos las asistencia que tenga ese presupuesto
                attendance_ids = record.env['hr.attendance'].search([('budget_id', 'in', bugdet_ids.ids)])
                if attendance_ids:
                    cost += sum(attendance_ids.mapped('attendance_cost'))/_num

            """
            CONCEPTOS
            """
            bim_concepts_ids = record.env['bim.concepts'].search([('property_ids', 'in', record.id)])
            for concept in bim_concepts_ids:
                _num = len(concept.property_ids)

                # sumamos las facturas que tenga ese concepto
                account_move_line_ids = record.env['account.move.line'].search([
                            ('concept_id', 'in', bim_concepts_ids.ids),
                            ('move_type', 'not in', ['out_invoice', 'out_refund']),
                        ])

                if account_move_line_ids:
                    cost += sum(account_move_line_ids.mapped('price_subtotal'))/_num

                # sumamos las asistencia que tenga ese presupuesto
                attendance_ids = record.env['hr.attendance'].search([('concept_id', 'in', bim_concepts_ids.ids)])
                if attendance_ids:
                    cost += sum(attendance_ids.mapped('attendance_cost'))/_num

            record.cost = cost
            record.benefit = record.price - record.cost

            if not bugdet_ids:
                record.budget_ids = bugdet_ids

            if not record.project_ids:
                record.project_ids = bugdet_ids.mapped('project_id')



            _logger.info("end exe_update")

class RealEstatePropertyline(models.Model):
    _name = 'real.estate.property.line'
    _description = 'Real Estate Property line'

    real_estate_property_id = fields.Many2one(comodel_name="real.estate.property", string="Real Estate Property")
    real_estate_property_variant_id = fields.Many2one(comodel_name="real.estate.property.variant", string="Real Estate Property Variant")
    quantity = fields.Integer('Quantity')
    note = fields.Char('Note')