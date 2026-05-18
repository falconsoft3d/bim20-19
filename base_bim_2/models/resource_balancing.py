# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import base64
import io

class ResourceBalancing(models.Model):
    _description = "Resource Balancing"
    _name = 'resource.balancing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    lines_ids = fields.One2many('resource.balancing.line', 'analysis_id', string='Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('done', 'Done'),
        ('canceled', 'Cancelled'),
    ], string='State', default='draft', copy=False, tracking=True)

    labor = fields.Boolean('Labor', default=True)
    equipment = fields.Boolean('Equipment', default=True)
    material = fields.Boolean('Material', default=False)
    subcontract = fields.Boolean('Subcontrato', default=False)

    type = fields.Selection([
        ('departure', 'Partida'),
        ('resource', 'Recurso'),
    ], string='Type', default='departure', copy=False, tracking=True)

    concepts_ids = fields.Many2many('bim.concepts', string='Chapters')

    def to_draft(self):
        self.write({'state': 'draft'})

    def clear_data(self):
        self.lines_ids.unlink()

    def cancel(self):
        self.write({'state': 'canceled'})

    def load_data(self):
        _logger.info('begin = load_data')
        self.lines_ids.unlink()

        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft analysis can be loaded.'))

        lines = []

        arr_type = []
        if self.labor:
            arr_type.append('labor')
        if self.equipment:
            arr_type.append('equip')
        if self.material:
            arr_type.append('material')
        if self.subcontract:
            arr_type.append('subcontract')


        bim_concepts = self.env['bim.concepts'].search([
                            ('budget_id','=',self.budget_id.id),
                            ('type','in', arr_type),
                        ])

        for l in bim_concepts:
            if self.concepts_ids:
                if l.parent_id.parent_id.id not in self.concepts_ids.ids:
                    continue

            # reviso si el producto ya esta en la lista
            exist_product = self.lines_ids.filtered(lambda x: x.product_id.id == l.product_id.id)

            _logger.info('self.lines_ids = %s', self.lines_ids)
            _logger.info('l.product_id = %s', l.product_id.id)
            _logger.info('len ( self.lines_ids ) = %s', len(self.lines_ids))
            _logger.info('exist_product = %s', exist_product)
            if exist_product:
                _logger.info('1 line = %s', l.product_id.id)
                line = self.lines_ids.filtered(lambda x: x.product_id.id == l.product_id.id)
                line.bim_concepts_ids = [(4,l.id)]

                if l.type == 'labor' or l.type == 'equip':
                    line.qty += l.quantity * l.parent_id.quantity * l.parent_id.apu_duration
                    line.new_qty += l.quantity * l.parent_id.quantity * l.parent_id.apu_duration
                else:
                    line.qty += l.quantity * l.parent_id.quantity
                    line.new_qty += l.quantity * l.parent_id.quantity
            else:
                _logger.info('2 line = %s', l.product_id.id)
                if not l.product_id:
                    raise UserError(_('El concepto %s no tiene producto asociado.') % l.name)

                if l.type == 'labor' or l.type == 'equip':
                    qty += l.quantity * l.parent_id.quantity * l.parent_id.apu_duration
                else:
                    qty += l.quantity * l.parent_id.quantity


                self.lines_ids.create({
                    'product_id': l.product_id.id,
                    'bim_concepts_ids': [(6,0,[l.id])],
                    'qty': qty,
                    'new_qty': qty,
                    'analysis_id': self.id,
                })
        self.write({'state': 'loaded'})
        _logger.info('end = load_data')


    def to_done(self):
        for line in self.lines_ids:
            if line.new_qty != line.qty:
                for concept in line.bim_concepts_ids:
                    concept.quantity = concept.quantity * line.coeficient
        self.write({'state': 'done'})


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('resource.balancing') or 'New'
        return super().create(vals_list)




class ResourceBalancingLine(models.Model):
    _description = "Resource Balancing Line"
    _name = 'resource.balancing.line'

    analysis_id = fields.Many2one('resource.balancing', string='Analysis', required=True, ondelete='cascade')
    bim_concepts_ids = fields.Many2many('bim.concepts', string='Concepts')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    qty = fields.Float('Quantity', required=True)
    new_qty = fields.Float('New Quantity', required=True)
    coeficient = fields.Float('Coeficiente', required=True, default=1)

    @api.onchange('new_qty')
    def _onchange_new_qty(self):
        self.coeficient = self.new_qty / self.qty