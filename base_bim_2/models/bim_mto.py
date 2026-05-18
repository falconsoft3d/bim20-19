# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class BimMto(models.Model):
    _description = "Bim Mto"
    _name = 'bim.mto'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    observation = fields.Text('Observation')
    lines_ids = fields.One2many('bim.mto.line', 'mto_id', string='Lines')
    customer_id = fields.Many2one('res.partner', string='Customer')

    reviewed_by = fields.Many2one('res.users', string='Reviewed by')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('revision', 'Revision'),
        ('released_for_production', 'Released for Production'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft', required=True, copy=False, tracking=True)

    def to_review(self):
        self.write({'state': 'revision'})

    def released_for_production(self):
        self.reviewed_by = self.env.user.id
        self.write({'state': 'released_for_production'})

    def to_done(self):
        self.write({'state': 'done'})

    def to_draft(self):
        self.write({'state': 'draft'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.mto') or 'New'
        return super().create(vals_list)

class BimMtoLine(models.Model):
    _description = "Bim Mto Line"
    _name = 'bim.mto.line'

    mto_id = fields.Many2one('bim.mto', string='Mto', required=True)


    dwg = fields.Char('Dwg')
    revision_number = fields.Char('Revision Number')
    parts = fields.Char('Parts')
    number_of_pieces = fields.Integer('Number of Pieces')


    element_id = fields.Many2one('bim.element', string='Element')
    material_id = fields.Many2one('bim.material', string='Material')

    thickness = fields.Float('Thickness')
    length = fields.Float('Length')
    width = fields.Float('Width')

    unit_weight = fields.Float('Unit Weight')


    budget_id = fields.Many2one('bim.budget', string='Budget', related='mto_id.budget_id')
    bim_concepts_id = fields.Many2one('bim.concepts', string='Concept')
    bim_concept_template_group_id = fields.Many2one('bim.concept.template.group', string='Apu Group')

    name = fields.Char('Description')
    qty = fields.Float('Quantity')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    note = fields.Char('Note')




    @api.onchange('element_id')
    def _onchange_product_id(self):
        self.name = self.element_id.name
        self.uom_id = self.element_id.uom_id.id

class BimMaterial(models.Model):
    _description = "Bim Material"
    _name = 'bim.material'

    name = fields.Char('Name', required=True)