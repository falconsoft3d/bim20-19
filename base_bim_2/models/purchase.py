# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date
import logging
_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    bim_requisition_id = fields.Many2one('bim.purchase.requisition', 'Requisition', copy=False)
    bim_service_id = fields.Many2one('bim.purchase.services', 'Services', copy=False)
    part_id = fields.Many2one('bim.part', 'Report', copy=False)
    project_id = fields.Many2one('bim.project', 'Project', tracking=True, copy=False,
    domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', copy=False,
    ondelete="restrict", domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', copy=False,
    ondelete="restrict", domain="[('budget_id','=',budget_id),('type','=','departure')]")
    margin = fields.Float('Margin (%)', default=0)
    place_of_delivery_id = fields.Many2one('res.partner', 'Place of Delivery')
    closed_valuation = fields.Boolean('Closed Valuation', default=False)

    purchase_valuation_ids = fields.One2many('purchase.valuation', 'purchase_id', string='Purchase Valuation')
    purchase_valuation_count = fields.Integer(compute='_compute_purchase_valuation_count', string='Purchase Valuation Count')

    @api.depends('purchase_valuation_ids')
    def _compute_purchase_valuation_count(self):
        for purchase in self:
            purchase.purchase_valuation_count = len(purchase.purchase_valuation_ids)

    def action_view_purchase_valuation(self):
        action = self.env.ref('base_bim_2.purchase_valuation_action').sudo().read()[0]
        action['domain'] = [('purchase_id', '=', self.id)]
        action['context'] = {'default_purchase_id': self.id}
        return action


    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.project_id:
            res.update({
                'bim_project_id': self.project_id.id,
                'bim_purchase_id': self.id,
            })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        if self.env.context.get('origin_po_id'):
            origin_po_id = self.env['purchase.order'].browse(self.env.context.get('origin_po_id'))
            if origin_po_id and origin_po_id.project_id:
                orders.project_id = origin_po_id.project_id.id
                orders.budget_id = origin_po_id.budget_id.id
                orders.concept_id = origin_po_id.concept_id.id
        return orders

    def action_margin_budget(self):
        if not self.budget_id:
            raise UserError(_("You must select a budget"))
        if self.budget_id:
            for line in self.order_line:
                product = line.product_id
                concept_ids = self.env['bim.concepts'].search([
                                            ('budget_id','=',self.budget_id.id),
                                            ('product_id','=',product.id)
                                        ])
                if concept_ids:
                    for concept in concept_ids:
                        if self.margin > 0:
                            concept.amount_fixed =  line.price_unit / ( 1 - (self.margin/100))
                        else:
                            concept.amount_fixed = line.price_unit

            # show alert message
            message = "The budget has been updated with the new product prices"
            self.message_post(body=message)
        return True

    def verify_bim_purchase_limit(self):
        for purchase in self:
            if purchase.project_id and purchase.project_id.limit_purchase and (not self.env.user.has_group('base_bim_2.group_manager_bim') or not self.env.user.has_group('base_bim_2.group_bim_purchase_not_limit')):
                for line in purchase.order_line.filtered_domain([('display_type','=',False)]):
                    line.verify_product_purchase_limit()

    def button_confirm(self):
        if self.project_id:
            if not self.project_id.state_id.create_purchase_order:
                raise UserError(_("You can't confirm a purchase order in a project that is not in the state 'Create Purchase Orders'"))

            if self.budget_id:
                if not self.budget_id.state_id.allow_supplier_purchase:
                    raise UserError(_("You can't confirm a purchase order in a budget that is not in the state 'Allow Supplier Purchase'"))

        self.verify_bim_purchase_limit()
        result = super(PurchaseOrder, self).button_confirm()

        for pick in self.picking_ids:
            pick.bim_purchase_id = self.id
            pick.bim_project_id = self.project_id.id
            pick.bim_budget_id = self.budget_id.id
            pick.bim_concept_id = self.concept_id.id

            for line in pick.move_ids:
                if line.purchase_line_id:
                    line.concept_phase_id = line.purchase_line_id.concept_phase_id.id


        for order in self:
            if order.bim_requisition_id:
                project = order.bim_requisition_id.project_id
                for pick in order.picking_ids:
                    pick.bim_project_id = project.id
                    pick.place_of_delivery_id = order.place_of_delivery_id.id
                    if not pick.bim_requisition_id:
                        pick.bim_requisition_id = order.bim_requisition_id.id

        if self.project_id:
            try:
                history_obj = self.env['bim.product.purchase']
                for line in self.order_line:
                    vals = {
                        'template_id': line.product_id.product_tmpl_id.id,
                        'product_id': line.product_id.id,
                        'date': date.today(),
                        'project_id': self.project_id.id,
                        'purchase_price': line.price_unit,
                        'purchase_id': self.id,
                        'supplier_id': self.partner_id.id,
                        'quantity': line.product_qty
                    }
                    history_obj.create(vals)
            except Exception as e:
                _logger.error(e)

        # Vamos a colocarle el proyecto al albaran de entrada
        try:
            if self.project_id and self.picking_ids:
                for picking in self.picking_ids:
                    picking.bim_project_id = self.project_id.id

        except Exception as e:
            _logger.error(e)

        return result

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            used_project_warehouse = self.company_id.use_project_warehouse
            if used_project_warehouse and self.project_id.warehouse_id:
                picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.project_id.warehouse_id.id),('code','=','incoming')],limit=1)
                if picking_type_id:
                    self.picking_type_id = picking_type_id

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.project_id:
            values.update({
                'project_id': self.project_id.id or False,
                'budget_id': self.budget_id.id or False,
                'concept_id': self.concept_id.id or False,
                'include_for_bim': self.company_id.bim_include_invoice_purchase,
                'invoice_date':  date.today(),
            })
        return values


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    bim_req_line_id = fields.Many2one('product.list', 'Requisition Line')
    project_id = fields.Many2one('bim.project', 'Project',
                 related='order_id.project_id', store=True)
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')
    partner_id = fields.Many2one('res.partner', 'Supplier', related='order_id.partner_id', store=True)

    qty_valoration = fields.Float('Qty Valoration', compute='_compute_qty_valoration')
    price_valoration = fields.Float('Price Valoration', compute='_compute_qty_valoration')
    total_oc_valoration = fields.Float('Total Valoration', compute='_compute_qty_valoration')
    qty_saldo = fields.Float('Qty Saldo', compute='_compute_qty_valoration')
    total_saldo = fields.Float('Total Saldo', compute='_compute_qty_valoration')
    percent_val = fields.Float('% Val', compute='_compute_qty_valoration')

    qty_invoice = fields.Float('Qty Invoice', compute='_compute_qty_invoice')
    price_unit_invoice = fields.Float('Price Unit Invoice', compute='_compute_qty_invoice')
    total_invoice = fields.Float('Total Invoice', compute='_compute_qty_invoice')
    state = fields.Selection(related='order_id.state', store=True)


    def _compute_qty_invoice(self):
        for rec in self:
            invoice_line = rec.env['account.move.line'].search([
                        ('purchase_line_id','=',rec.id),
                    ],limit=1)

            if invoice_line:
                rec.qty_invoice = invoice_line.quantity
                rec.price_unit_invoice = invoice_line.price_unit
                rec.total_invoice = invoice_line.price_subtotal
            else:
                rec.qty_invoice = 0
                rec.price_unit_invoice = 0
                rec.total_invoice = 0


    def _compute_qty_valoration(self):
        for rec in self:
            purchase_valuation_line = rec.env['purchase.valuation.line'].search([
                        ('purchase_id','=',rec.order_id.id),
                        ('product_id','=',rec.product_id.id),
                    ],limit=1)

            if purchase_valuation_line:
                rec.qty_valoration = purchase_valuation_line.product_qty
                rec.price_valoration = purchase_valuation_line.price_unit
                rec.total_oc_valoration = purchase_valuation_line.product_qty * purchase_valuation_line.price_unit
                rec.qty_saldo = rec.product_qty - rec.qty_valoration
                rec.total_saldo = rec.price_subtotal - rec.total_oc_valoration
                rec.percent_val = (rec.qty_valoration / rec.product_qty) * 100 if rec.product_qty > 0 else 0
            else:
                rec.qty_valoration = 0
                rec.price_valoration = 0
                rec.total_oc_valoration = 0
                rec.qty_saldo = rec.product_qty
                rec.total_saldo = rec.price_subtotal
                rec.percent_val = 0


    @api.onchange('product_id')
    def _onchange_concepts(self):
        for line in self:
            if line.order_id.project_id and line.order_id.project_id.analytic_id:
                line.analytic_distribution = {str(line.order_id.project_id.analytic_id.id): 100}

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move)
        values.update({
            'project_id': self.order_id.project_id.id or False,
            'budget_id': self.order_id.budget_id.id or False,
            'concept_phase_id' : self.concept_phase_id.id or False,
        })

        if self.order_id.project_id.analytic_id:
            analytic_distribution = {str(self.order_id.project_id.analytic_id.id): 100}
            values.update({
                'analytic_distribution': analytic_distribution or False,
            })
        return values

    def verify_product_purchase_limit(self):
        if not self.product_id or not self.order_id.project_id:
            return
        query = """select max(amount_fixed) from bim_concepts where project_id = {} and 
                    type not in ('chapter','departure') and product_id = {}
                    """.format(str(self.order_id.project_id.id),str(self.product_id.id))
        self.env.cr.execute(query)
        if self.env.cr.rowcount:
            max_price = self.env.cr.dictfetchall()
            price = max_price[0]['max']
            if price and price < self.price_unit:
                raise UserError(_("Max price for product %s is %s %s. Purchase price must be under that price")%(self.product_id.display_name,str(price),self.company_id.currency_id.symbol))

