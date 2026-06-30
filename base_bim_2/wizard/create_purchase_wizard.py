# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta
import logging
_logger = logging.getLogger(__name__)


class CreatePurchaseWizard(models.TransientModel):
    _name = "create.purchase.wizard"
    _description = 'Purchase Order Creation Wizard'

    @api.model
    def default_get(self, fields):
        _logger.info('default_get')
        res = super(CreatePurchaseWizard, self).default_get(fields)
        context = self._context
        _logger.info('1::')

        if self.env.context.get('active_model') == 'bim.purchase.requisition':
            req = self.env['bim.purchase.requisition'].browse(context['active_id'])

        if self.env.context.get('active_model') == 'bim.purchase.services':
            req = self.env['bim.purchase.services'].browse(context['active_id'])
        lines = []

        _logger.info('2::')

        for line in req.product_ids:
            quant = line.quant
            purchased = line.qty_purchase
            to_process = False
            if not line.done and line.qty_to_process > 0 and not req.buy_more:
                if line.quant >= purchased:
                    quant = line.qty_to_process
                    to_process = True

            if not line.done and req.buy_more:
                if line.qty_to_process > 0:
                    quant = line.qty_to_process
                else:
                    quant = 0
                to_process = True


            if to_process:
                if self.env.context.get('active_model') == 'bim.purchase.requisition':
                    _logger.info('2a::')
                    lines.append((0,0,{
                        'bim_req_line_id': line.id,
                        'product_id': line.product_id.id,
                        'quant': quant,
                        'cost': line.cost,
                        'um_id': line.um_id.id,
                        'analytic_id': line.analytic_id.id,
                        'concept_phase_id': line.concept_phase_id.id,
                        'seller_ids': line.partner_ids.ids,
                    }))

                if self.env.context.get('active_model') == 'bim.purchase.services':
                    _logger.info('2b::')

                    _logger.info('line.id %s' % line.id)

                    lines.append((0,0,{
                        'product_id': line.product_id.id,
                        'quant': quant,
                        'cost': line.cost,
                        'um_id': line.um_id.id,
                        'analytic_id': line.analytic_id.id,
                        'seller_ids': line.partner_ids.ids,
                    }))
            else:
                _logger.info('2c::')


        _logger.info('3::')

        """
        if not lines:
            raise UserError(_('There are not new lines to purchase'))
        """

        res['line_ids'] = lines
        _logger.info('4::')
        _logger.info(res)
        return res

    line_ids = fields.One2many('create.purchase.wizard.line','wizard_id','Lines')
    filter_categ = fields.Boolean(string="Group by Category")
    partner_ids = fields.Many2many('res.partner', string='Suppliers')

    @api.onchange('partner_ids')
    def onchange_partner_id(self):
        if self.partner_ids:
            for line in self.line_ids:
                line.seller_ids = self.partner_ids

    def create_purchase(self):
        self.ensure_one()
        if not self.line_ids.mapped('seller_ids'):
            raise UserError(_('There are not lines with Supplier assigned'))
        if any(not line.seller_ids for line in self.line_ids):
            raise UserError('There are lines without Supplier assigned')

        lines_purchase = self.line_ids.filtered(lambda i: len(i.seller_ids) == 1)
        lines_requisition = self.line_ids.filtered(lambda i: len(i.seller_ids) > 1)
        suppliers = lines_purchase.mapped('seller_ids')
        context = self._context
        PurchaseOrd = self.env['purchase.order']
        PurchaseReq = self.env['purchase.requisition']
        if self.env.context.get('active_model') == 'bim.purchase.requisition':
            req = self.env['bim.purchase.requisition'].browse(context['active_id'])
            if req.project_id.warehouse_id:
                picking_type = self.env['stock.picking.type'].search(
                    [('company_id', '=', req.company_id.id),('warehouse_id', '=', req.project_id.warehouse_id.id), ('code', '=', 'incoming')], limit=1).id
            else:
                picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming'),('company_id', '=', req.company_id.id)], limit=1).id
            purchase = self._aux_purchase_req(suppliers,lines_purchase,req,PurchaseOrd,lines_requisition,picking_type,PurchaseReq)
        if self.env.context.get('active_model') == 'bim.purchase.services':
            req = self.env['bim.purchase.services'].browse(context['active_id'])
            purchase = self._aux_purchase_service(suppliers,lines_purchase,req,PurchaseOrd,lines_requisition,PurchaseReq)
        return purchase

    def _aux_purchase_req(self,suppliers,lines_purchase,req,PurchaseOrd,lines_requisition,picking_type,PurchaseReq):
        if self.filter_categ:
            for categ in self.line_ids.mapped('product_id.categ_id'):
                for supplier in suppliers:
                    purchase_lines = []
                    for line in lines_purchase.filtered(lambda l: l.seller_ids.id == supplier.id and l.product_id.categ_id.id == categ.id):
                        line_vals = self._prepare_purchase_line(line,req)
                        purchase_lines.append((0,0,line_vals))
                    if purchase_lines:
                        order = PurchaseOrd.create({
                            'partner_id': supplier.id,
                            'origin': req.name,
                            'project_id': req.project_id.id or False,
                            'date_order': fields.Datetime.now(),
                            'picking_type_id': picking_type if picking_type else False
                        })
                        order.order_line = purchase_lines
                        req.write({'purchase_ids': [(4, order.id, None)]})
        else:
            for supplier in suppliers:
                purchase_lines = []
                order = PurchaseOrd.create({
                        'partner_id': supplier.id,
                        'origin': req.name,
                        'project_id': req.project_id.id or False,
                        'date_order': fields.Datetime.now(),
                        'picking_type_id': picking_type if picking_type else False
                })
                for line in lines_purchase.filtered(lambda l: l.seller_ids.id == supplier.id):
                    line_vals = self._prepare_purchase_line(line,req)
                    purchase_lines.append((0,0,line_vals))
                order.order_line = purchase_lines
                req.write({'purchase_ids': [(4, order.id, None)]})

        # Acuerdo de Compra
        if lines_requisition:
            items = [tuple(i.seller_ids.sorted().ids) for i in lines_requisition if i.seller_ids]
            list_partner = []
            for item in set(items):
                agree_lines = []
                for line in lines_requisition.filtered(lambda l: tuple(l.seller_ids.sorted().ids) == item):
                    vals_agree = self._prepare_agreement_line(line,req)
                    agree_lines.append((0,0,vals_agree))

                agree = PurchaseReq.create({
                        'origin': req.name,
                        'ordering_date': fields.Datetime.now(),
                        'line_ids': agree_lines
                    })
                agree.action_in_progress()
                for seller_id in item:
                    purchase_order = PurchaseOrd.create({
                        'partner_id': seller_id,
                        'project_id': req.project_id.id or False,
                        'origin': agree.name if agree else False,
                        'date_order': fields.Datetime.now(),
                        'requisition_id': agree.id if agree else False
                    })
                    purchase_order._onchange_requisition_id()
                req.write({'purchase_requisition_ids': [(4, agree.id, None)]})
        return True

    def _aux_purchase_service(self,suppliers,lines_purchase,req,PurchaseOrd,lines_requisition,PurchaseReq):
        if self.filter_categ:
            for categ in self.line_ids.mapped('product_id.categ_id'):
                for supplier in suppliers:
                    purchase_lines = []
                    for line in lines_purchase.filtered(lambda l: l.seller_ids.id == supplier.id and l.product_id.categ_id.id == categ.id):
                        line_vals = self._prepare_purchase_line(line,req)
                        purchase_lines.append((0,0,line_vals))
                    if purchase_lines:
                        order = PurchaseOrd.create({
                            'partner_id': supplier.id,
                            'origin': req.name,
                            'project_id': req.project_id.id or False,
                            'date_order': fields.Datetime.now(),
                        })
                        order.order_line = purchase_lines
                        req.write({'purchase_ids': [(4, order.id, None)]})
        else:
            for supplier in suppliers:
                purchase_lines = []
                order = PurchaseOrd.create({
                        'partner_id': supplier.id,
                        'origin': req.name,
                        'project_id': req.project_id.id or False,
                        'date_order': fields.Datetime.now(),
                })
                for line in lines_purchase.filtered(lambda l: l.seller_ids.id == supplier.id):
                    line_vals = self._prepare_purchase_line(line,req)
                    purchase_lines.append((0,0,line_vals))
                order.order_line = purchase_lines
                req.write({'purchase_ids': [(4, order.id, None)]})
        # Acuerdo de Compra
        if lines_requisition:
            items = [tuple(i.seller_ids.sorted().ids) for i in lines_requisition if i.seller_ids]
            for item in set(items):
                agree_lines = []
                for line in lines_requisition.filtered(lambda l: tuple(l.seller_ids.sorted().ids) == item):
                    vals_agree = self._prepare_agreement_line(line, req)
                    agree_lines.append((0, 0, vals_agree))
                agree = PurchaseReq.create({
                    'origin': req.name,
                    'ordering_date': fields.Datetime.now(),
                    'line_ids': agree_lines
                })
                agree.action_in_progress()
                for seller_id in item:
                    purchase_order = PurchaseOrd.create({
                        'partner_id': seller_id,
                        'project_id': req.project_id.id or False,
                        'date_order': fields.Datetime.now(),
                        'origin': agree.name if agree else req.name,
                        'requisition_id': agree.id if agree else False
                    })
                    purchase_order._onchange_requisition_id()
                req.write({'purchase_requisition_ids': [(4, agree.id, None)]})
        return True

    def _prepare_purchase_line(self,line,req):
        return {
            'name': line.product_id.name,
            'product_id': line.product_id.id,
            'product_uom': line.um_id.id or line.product_id.uom_id.id,
            'product_qty': line.quant,
            'concept_phase_id' : line.concept_phase_id.id,
            'price_unit': line.cost if not req.company_id.purchase_cost_zero else 0.0,
            'taxes_id': [(6, 0, line.product_id.supplier_taxes_id.ids)],
            'date_planned': req.date_prevista,
            'bim_req_line_id': line.bim_req_line_id.id,
            'analytic_distribution': {'%s' % (line.analytic_id.id): 100},
        }

    def _prepare_agreement_line(self,line,req):
        return {
            'product_id': line.product_id.id,
            'product_uom_id': line.um_id.id or line.product_id.uom_id.id,
            'product_qty': line.quant,
            'price_unit': line.cost if not req.company_id.purchase_cost_zero else 0.0,
            'schedule_date': req.date_prevista,
            'analytic_distribution': {'%s' % (line.analytic_id.id): 100},
        }


class CreatePurchaseWizardLine(models.TransientModel):
    _name = "create.purchase.wizard.line"
    _description = 'Lines of the Purchase Order Creation wizard'

    wizard_id = fields.Many2one('create.purchase.wizard', 'Wizard')
    bim_req_line_id = fields.Many2one('product.list', 'Requisition Line')
    product_id = fields.Many2one('product.product', 'Product')
    quant = fields.Float('Quantity', digits="BIM qty")
    cost = fields.Float('Cost', digits="BIM price")
    um_id = fields.Many2one('uom.uom', 'U.M')
    analytic_id = fields.Many2one('account.analytic.account', 'Analytical account')
    seller_ids = fields.Many2many('res.partner', string='Suppliers')
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')

