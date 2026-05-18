# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class BimProject(models.Model):
    _inherit = 'bim.project'

    project_limit_ids = fields.One2many('bim.project.limit','project_id')
    product_percent_limit = fields.Float(string='Percent Limit', tracking=1, default=100, digits=(10, 2))
    project_product_limited = fields.Boolean(default=lambda r: r.env.company.project_product_limited,
                                             string='Purchase limit', tracking=1)
    project_uom_ids = fields.One2many('bim.project.uom','project_id')

    def get_project_material_total(self):
        total_material = 0
        for limit in self.project_limit_ids:
            limit.unlink()
        for budget in self.budget_ids:
            values = budget.concept_ids
            resources = values.filtered(lambda c: c.type in ['material']  ).mapped('product_id')
            for mat in resources:
                material = 0
                material += self.get_total(mat.id,budget)
                total_material += material
            for concept in values:
                concept._check_concepts()
        for requisition in self.requisition_ids:
            for list in requisition.product_ids:
                list._check_product_list()
        for service in self.service_ids:
            for list in service.product_ids:
                list._check_product_list()

        # Get lines of UOM
        for product_limit_line in self.project_limit_ids:
            if product_limit_line.product_id and product_limit_line.product_id.bim_check_uom:
                # Crate UOM line if not exist
                uom = self.project_uom_ids.search([('project_id', '=', self.id),
                                                    ('name', '=', product_limit_line.product_id.uom_id.id)])
                if not uom:
                    self.env['bim.project.uom'].create({
                        'project_id': self.id,
                        'name': product_limit_line.product_id.uom_id.id,
                        'qty': product_limit_line.budget_qty,
                    })
                else:
                    # Update UOM line if exist
                    uom.qty += product_limit_line.budget_qty

    def recursive_amount(self, resource, parent, amount=None):
        amount = amount is None and resource.balance or amount
        if parent.type == 'departure':
            amount_partial = amount * parent.quantity
            return self.recursive_amount(resource,parent.parent_id,amount_partial)
        else:
            return amount * parent.quantity

    @api.model
    def get_total(self,resource_id,budget):
        records = budget.concept_ids.filtered(lambda c: c.product_id.id == resource_id)
        total = 0
        for rec in records:
            if rec.balance > 0:
                total += self.recursive_amount(rec,rec.parent_id,None)
        return total


class ProductList(models.Model):
    _inherit = 'product.list'

    project_limit_id = fields.Many2one('bim.project.limit')
    project_product_ids = fields.Many2many('product.product', compute='_compute_project_product_ids', store=True)

    @api.depends('project_id', 'project_id.project_product_limited','project_id.project_limit_ids')
    def _compute_project_product_ids(self):
        ProObj = self.env['product.product']
        for line in self:
            product_list = []
            if line.project_id and line.project_id.project_product_limited:
                limits = line.project_id.project_limit_ids
                if limits:
                    product_list = limits.product_id.ids
            else:
                products = ProObj.search([('company_id','in',[False,line.company_id.id])])
                if products:
                    product_list = products.ids
            line.project_product_ids = product_list

    @api.constrains('product_id', 'uom_id')
    def _check_product_list(self):
        LimitObj = self.env['bim.project.limit']
        for list in self:
            if list.product_id and list.project_id:
                if list.um_id:
                    possible_limit = LimitObj.search(
                        [('project_id', '=', list.project_id.id), ('product_id', '=', list.product_id.id),
                         ('uom_id', '=', list.um_id.id)],limit=1)
                else:
                    possible_limit = LimitObj.search(
                        [('project_id', '=', list.project_id.id), ('product_id', '=', list.product_id.id)],limit=1)
                if possible_limit:
                    list.project_limit_id = possible_limit.id


class ServiceList(models.Model):
    _inherit = 'service.list'

    project_limit_id = fields.Many2one('bim.project.limit')
    project_product_ids = fields.Many2many('product.product', compute='_compute_project_product_ids', store=True)

    @api.depends('project_id', 'project_id.project_product_limited','project_id.project_limit_ids')
    def _compute_project_product_ids(self):
        ProObj = self.env['product.product']
        for line in self:
            product_list = []
            if line.project_id and line.project_id.project_product_limited:
                limits = line.project_id.project_limit_ids
                if limits:
                    product_list = limits.product_id.ids
            else:
                products = ProObj.search([('company_id','in',[False,line.company_id.id])])
                if products:
                    product_list = products.ids
            line.project_product_ids = product_list

    @api.constrains('product_id', 'uom_id')
    def _check_product_list(self):
        LimitObj = self.env['bim.project.limit']
        for list in self:
            if list.product_id and list.project_id:
                if list.um_id:
                    possible_limit = LimitObj.search(
                        [('project_id', '=', list.project_id.id), ('product_id', '=', list.product_id.id),
                         ('uom_id', '=', list.um_id.id)],limit=1)
                else:
                    possible_limit = LimitObj.search(
                        [('project_id', '=', list.project_id.id), ('product_id', '=', list.product_id.id)],limit=1)
                if possible_limit:
                    list.project_limit_id = possible_limit.id


class BimConcepts(models.Model):
    _inherit = 'bim.concepts'

    project_limit_id = fields.Many2one('bim.project.limit')

    @api.constrains('product_id','uom_id')
    def _check_concepts(self):
        LimitObj = self.env['bim.project.limit']
        for concept in self.filtered_domain([('type','in',['material','aux','labor','equip'])]):
            if concept.product_id:
                if concept.uom_id:
                    possible_limit = LimitObj.search([('project_id','=',concept.project_id.id),('product_id','=',concept.product_id.id),
                                                      ('uom_id','=',concept.uom_id.id)],limit=1)
                else:
                    possible_limit = LimitObj.search(
                        [('project_id', '=', concept.project_id.id), ('product_id', '=', concept.product_id.id)],limit=1)
                if possible_limit:
                    concept.project_limit_id = possible_limit.id
                else:
                    new_limit = LimitObj.create({
                        'project_id': concept.project_id.id,
                        'product_id': concept.product_id.id,
                        'uom_id': concept.uom_id.id or False,
                    })
                    concept.project_limit_id = new_limit.id

class BimProjectUOM(models.Model):
    _name = 'bim.project.uom'
    _description = 'Bim Project UOM'
    _order = 'id asc'
    name = fields.Many2one('uom.uom', string='UOM', required=True)
    qty = fields.Float(string='Budgeted amount', required=True)
    project_id = fields.Many2one('bim.project', string='Project', required=True)



class BimProjectLimit(models.Model):
    _name = 'bim.project.limit'
    _description = 'Bim Project Limit'
    _order = 'name asc'

    name = fields.Char(related='product_id.display_name', store=True, string='Name')
    product_id = fields.Many2one('product.product')
    budget_qty = fields.Float(compute='_compute_budget_qty', store=True, digits="BIM qty")
    requested_qty = fields.Float(compute='_compute_requested_qty', store=True, digits="BIM qty")
    limit_qty = fields.Float(compute='_compute_limit_qty', store=True, digits="BIM qty")
    uom_id = fields.Many2one('uom.uom')
    concept_ids = fields.One2many('bim.concepts','project_limit_id')
    material_ids = fields.One2many('product.list','project_limit_id')
    service_ids = fields.One2many('service.list','project_limit_id')
    project_id = fields.Many2one('bim.project')
    product_percent_limit = fields.Float(related='project_id.product_percent_limit', store=True, digits=(10, 2))

    @api.depends('concept_ids','concept_ids.quantity','concept_ids.available')
    def _compute_budget_qty(self):
        _logger.info("Computing budget qty for project limits")
        for limit in self:
            budget_qty = 0
            for budget in self.project_id.budget_ids:
                budget_qty += self.get_quantity(budget,limit.product_id)
            limit.budget_qty = budget_qty

    def get_quantity(self,budget,product):
        _logger.info("X1 Getting quantity for product %s in budget %s", product.display_name, budget.name)
        records = budget.concept_ids.filtered(lambda c: c.product_id.id == product.id)
        total_qty = 0
        for rec in records:
            if rec.quantity > 0:
                total_qty += self.recursive_quantity(rec,rec.parent_id,None)
        return total_qty

    def recursive_quantity(self, resource, parent, qty=None):
        if resource.product_id.tool_ok:
            qty = qty is None and resource.available or qty
        else:
            qty = qty is None and resource.quantity or qty
        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource,parent.parent_id,qty_partial)
        else:
            return qty * parent.quantity

    @api.depends('material_ids', 'material_ids.quant','material_ids.requisition_id.state','service_ids', 'service_ids.quant','service_ids.service_id.state')
    def _compute_requested_qty(self):
        for limit in self:
            requested_qty = sum(material.quant for material in limit.material_ids.filtered_domain([('requisition_id.state','in',['aprobado','finalizado'])]))
            requested_qty += sum(service.quant for service in limit.service_ids.filtered_domain([('service_id.state','in',['aprobado','finalizado'])]))
            limit.requested_qty = requested_qty

    @api.depends('product_percent_limit', 'budget_qty')
    def _compute_limit_qty(self):
        for limit in self:
            limit.limit_qty = limit.budget_qty * limit.product_percent_limit / 100


class BimPurchaseRequisition(models.Model):
    _inherit = 'bim.purchase.requisition'

    def action_approve(self):
        if self.project_id and self.project_id.project_product_limited:
            for element in self.product_ids:
                if element.um_id:
                    limit = self.project_id.project_limit_ids.filtered_domain([('product_id','=',element.product_id.id),('uom_id','=',element.um_id.id)])
                else:
                    limit = self.project_id.project_limit_ids.filtered_domain([('product_id', '=', element.product_id.id)])
                if limit and limit[0].limit_qty - limit[0].requested_qty < element.quant:
                    raise UserError(_("Product {} surpasses its limit in Project {}").format(element.product_id.display_name,self.project_id.display_name))
        return super().action_approve()


class BimPurchaseService(models.Model):
    _inherit = 'bim.purchase.services'

    def action_approve(self):
        if self.project_id and self.project_id.project_product_limited:
            for element in self.product_ids:
                if element.um_id:
                    limit = self.project_id.project_limit_ids.filtered_domain([('product_id','=',element.product_id.id),('uom_id','=',element.um_id.id)])
                else:
                    limit = self.project_id.project_limit_ids.filtered_domain([('product_id', '=', element.product_id.id)])
                if limit and limit[0].limit_qty - limit[0].requested_qty < element.quant:
                    raise UserError(_("Product {} surpasses its limit in Project {}").format(element.product_id.display_name,self.project_id.display_name))
        return super().action_approve()







