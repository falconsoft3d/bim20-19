# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError,ValidationError


class BimPurchaseRequisition(models.Model):
    _inherit = ['mail.thread']
    _description = "Material Request"
    _name = 'bim.purchase.requisition'
    _order = "id desc"

    @api.model
    def default_get(self, default_fields):
        values = super(BimPurchaseRequisition, self).default_get(default_fields)
        active_id = self._context.get('active_id')
        project = self.env['bim.project'].browse(active_id)
        values['warehouse_id'] = project.warehouse_id.id
        return values

    @api.model
    def _default_warehouse_id(self):
        active_id = self._context.get('active_id')
        project = self.env['bim.project'].browse(active_id)
        return project.warehouse_id.id

    name = fields.Char('Code', default="New")
    user_id = fields.Many2one('res.users', string='Responsable', tracking=True, default=lambda self: self.env.user)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    date_begin = fields.Date('Start Date', default = lambda self: datetime.today())
    date_prevista = fields.Date('Expected date', default = lambda self: datetime.today())


    def _get_domain_project_id(self):
        domain = [
            '&',  # Para combinar las siguientes dos condiciones con un "AND"
            ('company_id', '=', self.env.company.id),
            '|',  # Para especificar las dos condiciones alternativas
            ('requisition_user_ids', 'in', self.env.user.id),
            ('requisition_user_ids', '=', False)
        ]
        return domain

    project_id = fields.Many2one('bim.project', string='Project',
                                domain= _get_domain_project_id)

    obs = fields.Text('Notes', default="")
    warehouse_id = fields.Many2one('stock.warehouse','Warehouse', default=_default_warehouse_id)
    analytic_id = fields.Many2one('account.analytic.account', 'Analytical Account')
    state = fields.Selection(
        [('nuevo', 'New'),
         ('required_', 'Solicitado'),
         ('aprobado', 'Approved'),
         ('parcial-finalizado', 'Parcialmente Terminado'),
         ('finalizado', 'Done'),
         ('received', 'Received'),
         ('cancelled', 'Cancelled')],
        'Status', default='nuevo', tracking=True)
    product_ids = fields.One2many('product.list', 'requisition_id', string='Product List')

    picking_ids = fields.One2many('stock.picking', 'bim_requisition_id', string='Transfers')
    picking_count = fields.Integer('Quantity Transf', compute="_compute_picking")

    purchase_ids = fields.One2many('purchase.order', 'bim_requisition_id', string='Purchases')
    purchase_requisition_ids = fields.Many2many('purchase.requisition', string='Purchase Agreement')
    purchase_count = fields.Integer('Quantity Purchases', compute="_compute_purchases")

    agree_count = fields.Integer('Agreement Quantity', compute="_compute_purchase_requisitions")
    amount_total = fields.Float('Total', compute="_compute_total", digits="BIM price")
    space_id = fields.Many2one('bim.budget.space', 'Space')
    buy_more = fields.Boolean('Allow to Buy More', default=lambda self: self.env.company.allow_to_buy_more_mat)
    budget_ids = fields.Many2many('bim.budget')
    separate_tools = fields.Boolean('Separate tools', default=False)

    # bim.tool.rent
    bim_tool_rent_ids = fields.One2many('bim.tool.rent', 'bim_purchase_requisition_id', string='Rents')
    bim_tool_rent_count = fields.Integer('Quantity', compute="_compute_bim_tool_rent")


    def action_receive(self):
        self.write({'state': 'received'})

    def action_request(self):
        self.write({'state': 'required_'})


    def _compute_bim_tool_rent(self):
        for req in self:
            req.bim_tool_rent_count = len(req.bim_tool_rent_ids)

    def action_view_bim_tool_rents(self):
        rents = self.mapped('bim_tool_rent_ids')
        action = self.env.ref('base_bim_2.action_bim_tool_rent_orders').sudo().read()[0]
        if len(rents) > 0:
            action['domain'] = [('id', 'in', rents.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_create_tools_rent(self):
        if not self.separate_tools:
            bim_tool_rent_obj = self.env['bim.tool.rent']

            bim_tool_rent_obj_new =  bim_tool_rent_obj.create({
                'project_id': self.project_id.id,
                'partner_id': self.project_id.customer_id.id,
                'bim_purchase_requisition_id': self.id,
                'budget_id': self.budget_ids[0].id if self.budget_ids else False,
            })

            for line in self.product_ids:
                if line.product_id.tool_ok:
                    bim_concepts_id = self.env['bim.concepts'].search([('product_id','=',line.product_id.id)], limit=1)

                    if bim_concepts_id:
                        bim_tool_rent_obj_new.concept_id = bim_concepts_id.id
                        bim_tool_rent_obj_new.date_from = bim_concepts_id.acs_date_start
                        bim_tool_rent_obj_new.date_to = bim_concepts_id.acs_date_end

                    bim_tool_rent_obj_new.rent_line_ids.create({
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id.id,
                        'product_uom_qty': line.quant,
                        'price_unit': line.product_id.list_price,
                        'bim_rent_id': bim_tool_rent_obj_new.id,
                    })
        else:
            bim_tool_rent_obj = self.env['bim.tool.rent']
            for line in self.product_ids:
                if line.product_id.tool_ok:
                    bim_tool_rent_obj_new = bim_tool_rent_obj.create({
                        'project_id': self.project_id.id,
                        'partner_id': self.project_id.customer_id.id,
                        'bim_purchase_requisition_id': self.id,
                        'budget_id': self.budget_ids[0].id if self.budget_ids else False,
                    })

                    bim_concepts_id = self.env['bim.concepts'].search([('product_id', '=', line.product_id.id)],
                                                                      limit=1)
                    if bim_concepts_id:
                        bim_tool_rent_obj_new.concept_id = bim_concepts_id.id
                        bim_tool_rent_obj_new.date_from = bim_concepts_id.acs_date_start
                        bim_tool_rent_obj_new.date_to = bim_concepts_id.acs_date_end

                    bim_tool_rent_obj_new.rent_line_ids.create({
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id.id,
                        'product_uom_qty': line.quant,
                        'price_unit': line.product_id.list_price,
                        'bim_rent_id': bim_tool_rent_obj_new.id,
                    })



    @api.onchange('project_id')
    def onchange_project_id(self):
        self.analytic_id = self.project_id.analytic_id.id
        self.warehouse_id = self.project_id.warehouse_id.id

    def action_approve(self):
        self.register_update_requested_resources_in_budget()
        self.write({'state': 'aprobado'})

    def register_update_requested_resources_in_budget(self):
        for line in self.product_ids:
            requested_qty = line.quant
            uom = line.um_id.id if line.um_id else False
            for budget in self.budget_ids.search([('id','in',self.budget_ids.ids)], order='id'):
                budget_resource = budget.resource_ids.filtered_domain([('product_id','=',line.product_id.id),('uom_id','=',uom)])
                if budget_resource and requested_qty:
                    budget_resource = budget_resource[0]
                    budget_resource_total = budget_resource.budget_qty - budget_resource.requested_qty
                    if requested_qty >= budget_resource_total:
                        budget_resource.requested_qty += budget_resource_total
                        requested_qty -= budget_resource_total
                    else:
                        budget_resource.requested_qty += requested_qty
                        requested_qty = 0

    def cancel_requested_resources_in_budget(self):
        for line in self.product_ids:
            requested_qty = line.quant
            uom = line.um_id.id if line.um_id else False
            for budget in self.budget_ids.search([('id','in',self.budget_ids.ids)], order='id'):
                budget_resource = budget.resource_ids.filtered_domain([('product_id','=',line.product_id.id),('uom_id','=',uom)])
                if budget_resource and requested_qty:
                    budget_resource = budget_resource[0]
                    budget_resource_requested_qty = budget_resource.requested_qty
                    if requested_qty >= budget_resource_requested_qty:
                        budget_resource.requested_qty -= budget_resource_requested_qty
                        requested_qty -= budget_resource_requested_qty
                    else:
                        budget_resource.requested_qty -= requested_qty
                        requested_qty = 0


    def action_clear(self):
        self.product_ids.unlink()


    def action_done(self):
        if self.state == 'aprobado':
            self.state = 'parcial-finalizado'
        else:
            self.state = 'finalizado'

    def action_cancel(self):
        self.cancel_requested_resources_in_budget()
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'nuevo'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.purchase.requisition') or 'New'

        records = super().create(vals_list)

        for res in records:
            if res.project_id and res.project_id.nombre:
                res.name = f"{res.name} - {res.project_id.nombre}"

        return records

    def _compute_picking(self):
        for req in self:
            req.picking_count = len(req.picking_ids)

    def _compute_purchases(self):
        for req in self:
            req.purchase_count = len(req.purchase_ids)

    def _compute_purchase_requisitions(self):
        for req in self:
            req.agree_count = len(req.purchase_requisition_ids)

    def _compute_total(self):
        for record in self:
            record.amount_total = sum(pd.subtotal for pd in record.product_ids)

    def create_picking(self):
        if not self.project_id.stock_location_id:
            raise ValidationError(_('Project %s does not have an inventory location configured'%self.project_id.nombre))
        view_id = self.env.ref('stock.view_picking_form').id
        context = self._context.copy()
        context['default_bim_requisition_id'] = self.id
        picking_type = self.env['stock.picking.type'].search([('code','=','internal'),
                                                              ('warehouse_id','=',self.warehouse_id.id)], limit = 1)
        context['default_picking_type_id'] = picking_type.id
        context['default_bim_project_id'] = self.project_id.id if self.project_id else False
        context['default_picking_type_id'] = picking_type.id
        context['default_location_dest_id'] = self.project_id.stock_location_id.id
        return {
            'name': 'New',
            'view_mode': 'tree',
            'views': [(view_id,'form')],
            'res_model': 'stock.picking',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': context,
        }

    def action_view_pickings(self):
        pickings = self.mapped('picking_ids')
        action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]
        if len(pickings) > 0:
            action['domain'] = [('id', 'in', pickings.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_purchases(self):
        purchases = self.mapped('purchase_ids')
        action = self.env.ref('purchase.purchase_rfq').sudo().read()[0]
        if len(purchases) > 0:
            action['domain'] = [('id', 'in', purchases.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_agreement(self):
        agreements = self.mapped('purchase_requisition_ids')
        action = self.env.ref('purchase_requisition.action_purchase_requisition').sudo().read()[0]
        if len(agreements) > 0:
            action['domain'] = [('id', 'in', agreements.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def unlink(self):
        for record in self:
            if record.state != 'nuevo':
                raise UserError(_("This record can not be deleted in other state than new!"))
        return super().unlink()

class ProductList(models.Model):
    _name = 'product.list'
    _description = 'Product List'
    _rec_name = 'product_id'

    solo_lectura = fields.Boolean('Readonly', default=False, compute='_compute_giveme_state')
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')

    def _compute_giveme_state(self):
        if self.requisition_id.state == 'nuevo':
            self.solo_lectura = False
        else:
            self.solo_lectura = True

    @api.depends('requisition_id.picking_ids')
    def _compute_qty_done(self):
        for record in self:
            moves = record.requisition_id.picking_ids.mapped('move_ids').filtered(lambda m: m.state == 'done' and m.product_id.id == record.product_id.id)
            record.qty_done = sum(x.product_uom_qty for x in moves)

    @api.depends('qty_done','quant')
    def _compute_qty_to_process(self):
        for record in self:
            if record.qty_done > record.quant:
                record.qty_to_process = 0
                record.subtotal = record.qty_done * record.cost
            else:
                record.qty_to_process = record.quant - record.qty_done
                record.subtotal = record.quant * record.cost

    @api.depends('requisition_id.purchase_ids')
    def _compute_qty_purchase(self):
        for record in self:
            purchase_lines = record.requisition_id.purchase_ids.mapped('order_line').filtered(lambda r: r.bim_req_line_id.id == record.id and r.state != 'cancel')
            record.qty_purchase = sum(x.product_qty for x in purchase_lines)

    product_id = fields.Many2one('product.product', 'Product')
    default_code = fields.Char('Default Code', related='product_id.default_code', store=True)
    quant = fields.Float('Quantity', digits="BIM qty")
    cost = fields.Float('Cost', digits="BIM price")
    subtotal = fields.Float('Subtotal', compute="_compute_qty_to_process", digits="BIM price")
    despachado = fields.Float('Dispatched', digits="BIM qty")
    obs = fields.Text('Notes', default="")
    um_id = fields.Many2one('uom.uom', 'U.M')
    done = fields.Boolean('Done')
    qty_to_process = fields.Float('To process', compute="_compute_qty_to_process", digits="BIM qty")
    qty_done = fields.Float('Dispatched Quant.', compute="_compute_qty_done", digits="BIM qty")
    qty_purchase = fields.Float('Purchased', compute="_compute_qty_purchase", digits="BIM qty")
    sent_to_production = fields.Boolean('Sent to production')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    analytic_id = fields.Many2one('account.analytic.account', 'Analytical account')
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytical Tags')
    partner_ids = fields.Many2many('res.partner', string='Supplier')
    #partner_id = fields.Many2one('res.partner','Supplier')
    requisition_id = fields.Many2one('bim.purchase.requisition', 'Requisition', ondelete='cascade')
    project_id = fields.Many2one('bim.project', string="Project", domain="[('company_id','=',company_id)]", related='requisition_id.project_id', store=True)
    budget_id = fields.Many2one('bim.budget', string="Budget")
    stock = fields.Float('Stock', compute='_compute_stock')
    state = fields.Selection(related='requisition_id.state', string='State', store=True)

    @api.depends('product_id')
    def _compute_stock(self):
        for record in self:
            record.stock = record.product_id.qty_available

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.um_id = self.product_id.uom_id.id
        self.analytic_id = self.requisition_id.analytic_id.id
        self.project_id = self.requisition_id.project_id.id
        self.cost = self.product_id.standard_price

    @api.constrains('product_id')
    def _check_product_id(self):
        if not self.requisition_id.state == 'nuevo':
            raise ValidationError(_("You cannot Add Lines in this State"))

    def unlink(self):
        for requisition_list in self:
            if requisition_list.solo_lectura:
                raise UserError(_('You cannot delete a Line in this other than New!'))
        return super(ProductList, self).unlink()

