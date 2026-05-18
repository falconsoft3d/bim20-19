# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

class PickingAnalysis(models.Model):
    _description = "Picking Analysis"
    _name = 'picking.analysis'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True, readonly=True, copy=False, index=True, default=lambda self: self.env['ir.sequence'].next_by_code('picking.analysis'))
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    begin_date = fields.Date('Begin Date', default=fields.Datetime.now, required=True)
    end_date = fields.Date('End Date', default=fields.Datetime.now, required=True)
    lines_ids = fields.One2many('picking.analysis.line', 'picking_analysis_id', string='Picking Analysis Lines', copy=True)
    subtotal = fields.Float(compute='compute_subtotal', store=True)
    type = fields.Selection([
        ('in', 'In'),
        ('out', 'Out'),
        ('internal', 'Internal'),
        ('all', 'All')
        ], string='Type', default='all', required=True, copy=False, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('validated', 'Validated'),
        ('cancel', 'Cancelled'),
        ], string='State', default='draft', copy=False, tracking=True)

    include_for_bim = fields.Boolean('Include for BIM', default=True)


    @api.depends('lines_ids.subtotal')
    def compute_subtotal(self):
        for analysis in self:
            subtotal = 0
            for line in analysis.lines_ids:
                subtotal += line.subtotal
            analysis.subtotal = subtotal


    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.company_id = self.project_id.company_id.id
            self.currency_id = self.project_id.currency_id.id

    def action_validate(self):
        for line in self.lines_ids:
            if line.assets_qty > 0 and line.stock_move_id.assets_qty != line.assets_qty:
                line.stock_move_id.assets_qty = line.assets_qty

            if line.stock_move_id.assets_qty > 0 and line.assets_qty == 0:
                line.stock_move_id.assets_qty = 0


            try:
                line.name.update_picking_total_cost()
            except:
                pass

        self.project_id.action_update_all()
        self.state = 'validated'



    def action_load(self):
        self.ensure_one()
        """
        1. Busca los movimientos de stock que cumplan con las condiciones
        """

        value = 1

        bim_general_config_id = self.env['bim.general.config'].search([
                ('key', '=', 'picking_analysis_day')
        ], limit=1)

        if bim_general_config_id:
            value = bim_general_config_id.value

        _logger.info('value: %s', value)
        _logger.info(bim_general_config_id)

        begin_date = self.end_date.replace(day=1, year=2000)
        bim_general_config_id = self.env['bim.general.config'].search([
                                ('key', '=', 'picking_analysis_day')], limit=1)

        if bim_general_config_id:
            picking_analysis_day = bim_general_config_id.value
            if picking_analysis_day == 0:
                picking_analysis_day = 10
        else:
            picking_analysis_day = 10

        end_date = self.end_date.replace(day=int(picking_analysis_day)) + relativedelta(months=1)

        # Escribo el en chatter el filtro de fecha
        self.message_post(body=_('Fecha de Inicio: %s - Fecha Fin: %s') % (begin_date, end_date))


        if self.type == 'in':
            domain = [('bim_project_id', '=', self.project_id.id),
                      ('picking_type_code', '=', 'incoming'),
                      ('state', '=', 'done'),
                      ('date_done', '>=', begin_date),
                      ('date_done', '<=', end_date),
                      ('include_for_bim', '=', True)]
        elif self.type == 'out':
            domain = [('bim_project_id', '=', self.project_id.id),
                      ('date_done', '>=', begin_date),
                      ('date_done', '<=', end_date),
                      ('picking_type_code', '=', 'outgoing'), ('state', '=', 'done'),('include_for_bim', '=', True)]
        else:
            domain = [('bim_project_id', '=', self.project_id.id),
                      ('state', '=', 'done'),
                      ('date_done', '>=', begin_date),
                      ('date_done', '<=', end_date),
                      ('include_for_bim', '=', True)]

        stock_picking_ids = self.env['stock.picking'].search(domain)

        # Limpia las lineas
        self.lines_ids.unlink()

        for picking in stock_picking_ids:
            for move in picking.move_ids_without_package:
                vals = {
                        'name': picking.id,
                        'purchase_id': move.purchase_id.id,
                        'picking_analysis_id': self.id,
                        'product_cost': move.product_cost * -1 if move.picking_type_code == 'outgoing' else move.product_cost,
                        'assets_qty': move.assets_qty,
                        'subtotal': move.subtotal,
                        'date': picking.scheduled_date,
                        'product_qty': move.quantity,
                        'product_uom_id': move.product_uom.id,
                        'stock_move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_category_id': move.product_id.categ_id.id,
                        'subtotal_picking': move.subtotal * -1 if move.picking_type_code == 'outgoing' else move.subtotal,
                    }

                self.env['picking.analysis.line'].create(vals)

        """
        1. Busca los stock.move con assets_qty > 0 que su stock_picking tenga project_id = self.project_id
        """
        stock_move_ids = self.env['stock.move'].search([('picking_id.bim_project_id', '=', self.project_id.id), ('assets_qty', '>', 0)])
        if stock_move_ids:
            for move in stock_move_ids:
                # revisamos que no este
                if not self.env['picking.analysis.line'].search([('stock_move_id', '=', move.id)]):
                    vals = {
                            'name': move.picking_id.id,
                            'purchase_id': move.purchase_id.id,
                            'picking_analysis_id': self.id,
                            'product_cost': move.product_cost * -1 if move.picking_type_code == 'outgoing' else move.product_cost,
                            'assets_qty': move.assets_qty,
                            'subtotal': move.subtotal,
                            'date': move.picking_id.scheduled_date,
                            'product_qty': move.quantity,
                            'product_uom_id': move.product_uom.id,
                            'stock_move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_category_id': move.product_id.categ_id.id,
                            'subtotal_picking': move.subtotal * -1 if move.picking_type_code == 'outgoing' else move.subtotal,
                        }

                    self.env['picking.analysis.line'].create(vals)


        if not self.lines_ids:
            raise ValidationError(_('No data found'))


    line_count = fields.Integer('Lines', compute='_compute_line_count')

    @api.depends('lines_ids')
    def _compute_line_count(self):
        for analysis in self:
            analysis.line_count = len(analysis.lines_ids)

    def action_view_lines(self):
        action = self.env.ref('base_bim_2.action_picking_analysis_line').sudo().read()[0]
        action['domain'] = [('picking_analysis_id', '=', self.id)]
        action['context'] = {
            'default_picking_analysis_id': self.id,
        }
        return action



class PickingAnalysisLine(models.Model):
    _description = "Picking Analysis Line"
    _name = 'picking.analysis.line'
    _order = 'id desc'


    name = fields.Many2one('stock.picking', 'Stock Picking', ondelete="cascade")
    purchase_id = fields.Many2one('purchase.order')
    stock_move_id = fields.Many2one('stock.move', 'Stock Move', ondelete="cascade")
    product_id = fields.Many2one('product.product', 'Product', ondelete="cascade")
    product_category_id = fields.Many2one('product.category', string='Product Category')
    date = fields.Datetime('Date')
    product_cost = fields.Float()
    product_qty = fields.Float()
    product_uom_id = fields.Many2one('uom.uom', 'UOM')
    subtotal = fields.Float(compute='compute_subtotal', store=True)
    subtotal_picking = fields.Float(string='Subtotal Albarán')
    assets_qty = fields.Float(string='Assets Qty')
    currency_id = fields.Many2one('res.currency', related='picking_analysis_id.currency_id')
    oenc = fields.Boolean('OENC', default=False, help='Obra en ejecución no certificada')
    picking_analysis_id = fields.Many2one('picking.analysis', ondelete='cascade')
    note = fields.Char('Note')


    @api.depends('product_cost','product_qty','assets_qty')
    def compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_cost * line.assets_qty
