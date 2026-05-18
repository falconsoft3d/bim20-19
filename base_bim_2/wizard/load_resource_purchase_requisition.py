# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError


class ResourceRequisitionwizard(models.TransientModel):
    _name = 'resource.requisition.wzd'
    _description = 'Load Project Resources'

    def _get_default_project_id(self):
        active_id = self._context.get('active_id')
        req = self.env['bim.purchase.requisition'].browse(active_id)
        return req.project_id and req.project_id.id or False

    project_id = fields.Many2one("bim.project", string="Project", default=_get_default_project_id)
    budget_ids = fields.Many2many("bim.budget", string="Budgets")
    type = fields.Selection([
        ('wo_stock', 'Compra Descontando el Stock en Almacenes'),
        ('wi_stock', 'Compra sin tener en cuenta el Stock Actual')],
        'Type', default='wo_stock')
    location_type = fields.Selection([
        ('project','Project Location'),
        ('main_location','Main Locations'),
        ('combination','Project/ Main All')],
        default='project')

    type_recourse = fields.Selection([
        ('material', 'Material'),
        ('equip', 'Equipment'),
        ('material_equip', 'Material and Equipment')],
        'Tipo de Recurso', default='material')

    categ_id = fields.Many2one('product.category', string='Category')

    by_date = fields.Boolean('By Date', default=False)
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')

    tools = fields.Boolean('Tools', default=False)

    concept_ids = fields.Many2many('bim.concepts', string='Concepts')

    all_rec = fields.Boolean('All Types')


    # Oncchange by_date
    @api.onchange('by_date')
    def onchange_by_date(self):
        if self.budget_ids:
            budget_id = self.budget_ids[0]
            if budget_id and self.by_date:
                self.date_from = budget_id.date_start
                self.date_to = budget_id.date_end



    def find_locations(self):
        locations = []
        if self.location_type == 'project':
            locations += self.project_id.stock_location_id
        elif self.location_type == 'main_location':
            locations += self.env['stock.location'].search([('bim_main_location','=',True),('usage','=','internal'),
                                                            ('company_id','=',self.project_id.company_id.id)]) or []
        else:
            locations += self.project_id.stock_location_id
            locations += self.env['stock.location'].search(
                [('bim_main_location', '=', True), ('usage', '=', 'internal'),
                 ('company_id', '=', self.project_id.company_id.id)]) or []
        return locations

    def get_product_qty(self, Quant, locations, product):
        product_qty = 0
        for location in locations:
            product_qty += Quant._get_available_quantity(product,location)
        return product_qty

    def get_tool_qty(self, product, budget_id):
        bim_concepts = self.env['bim.concepts'].search([
            ('product_id','=',product.id),
            ('budget_id','=',budget_id.id),
        ])
        qty = sum(bim_concepts.mapped('qty'))
        return float(qty)


    def load_resources(self):
        if self.location_type in ('project','combination') and not self.project_id.stock_location_id:
            raise UserError(_("It is necessary to set Project Location before loading resources"))

        if not self.budget_ids:
            raise UserError(_('Please, select at least one Budget.'))

        self.budget_ids.action_calculate_budget_resources()
        requisition_id = self._context.get('active_id')
        ProductList = self.env['product.list']
        requisition = self.env['bim.purchase.requisition'].browse([requisition_id])
        requisition.budget_ids += self.budget_ids
        concept_ids = []

        for budget in self.budget_ids:
            for concept in budget.concept_ids:
                if self.by_date:
                    print("if self.by_date")
                    if concept.parent_id and concept.parent_id.acs_date_start and concept.parent_id.type == 'departure':
                        if concept.parent_id.acs_date_start.date() < self.date_from or concept.parent_id.acs_date_start.date() > self.date_to:
                            continue
                if self.concept_ids:
                    if concept.parent_id and concept.parent_id in self.concept_ids:
                        concept_ids.append(concept.id)
                else:
                    concept_ids.append(concept.id)

        concepts = self.env['bim.concepts'].browse(concept_ids)
        uom_ids = concepts.mapped('uom_id.id')
        uom_ids.append(False)
        resources = self.get_resources(concepts)
        products_to_buy = ProductList
        Quants = self.env['stock.quant']

        for uom in uom_ids:
            uom_resources = concepts.filtered_domain([('uom_id','=',uom)])
            for resource in resources:
                if resource.resource_type == 'M' or (self.tools and resource.resource_type == 'Q' and resource.type == 'product') or self.all_rec:
                    if self.tools and resource.resource_type == 'M':
                        continue

                    quantity = self.get_quantity(uom_resources,resource,uom)
                    if self.tools:
                        cost = resource.list_price
                    else:
                        cost = resource.seller_ids[0].price if resource.seller_ids else resource.standard_price

                    buy = False
                    if self.type == 'wi_stock':
                        buy = True

                    if self.type == 'wo_stock':
                        locations = self.find_locations()
                        product_quant = self.get_product_qty(Quants,locations,resource)
                        if product_quant == 0 or (product_quant > 0 and product_quant < quantity):
                            buy = True
                            quantity = quantity - product_quant
                        else:
                            buy = False
                    if buy and quantity > 0:
                        if not self.categ_id:
                            val = {
                                    'requisition_id': requisition_id,
                                    'product_id': resource.id,
                                    'budget_id': budget.id,
                                    'partner_ids': [(4,resource.seller_ids[0].partner_id.id)] if resource.seller_ids else False,
                                    'um_id': uom if uom else resource.uom_id.id,
                                    'quant': quantity,
                                    'cost': cost,
                                    'analytic_id': self.project_id.analytic_id.id or False}
                            products_to_buy += ProductList.create(val)

                        if self.categ_id:
                            if resource.categ_id == self.categ_id:
                                val = {
                                    'requisition_id': requisition_id,
                                    'product_id': resource.id,
                                    'partner_ids': [
                                        (4, resource.seller_ids[0].partner_id.id)] if resource.seller_ids else False,
                                    'um_id': uom if uom else resource.uom_id.id,
                                    'quant': quantity,
                                    'cost': resource.seller_ids[
                                        0].price if resource.seller_ids else resource.standard_price,
                                    'analytic_id': self.project_id.analytic_id.id or False}
                                products_to_buy += ProductList.create(val)


        if not products_to_buy:
            raise UserError(_("The are not materials to request in the selected budgets"))

    def get_resources(self,concepts):
        domain = ['material','equip','labor','subcon']
        active_id = self._context.get('active_id')
        current_products = self.env['bim.purchase.requisition'].browse(active_id).product_ids.mapped('product_id.id') or []
        resources = concepts.filtered(lambda c: c.type in domain).mapped('product_id').filtered_domain([('id','not in',current_products)])
        return resources

    def get_quantity(self,concepts,resource,uom):
        if uom:
            records = concepts.filtered(lambda c: c.product_id.id == resource.id and c.uom_id.id == uom)
        else:
            records = concepts.filtered(lambda c: c.product_id.id == resource.id and c.uom_id.id == False)
        total_qty = 0
        for rec in records:
            if uom:
                if rec.quantity > 0 and rec.parent_id.quantity > 0 and rec.uom_id.id == uom and rec.product_id == resource:
                    total_qty += self.recursive_quantity(rec, rec.parent_id, None)
            else:
                if rec.quantity > 0 and rec.parent_id.quantity > 0 and not rec.uom_id and rec.product_id == resource:
                    total_qty += self.recursive_quantity(rec,rec.parent_id,None)

        for budget in self.budget_ids:
            budget_resource = budget.resource_ids.filtered_domain([('product_id', '=', resource.id),('uom_id','=',uom)])
            if budget_resource:
                budget_resource = budget_resource[0]
                total_qty -= budget_resource.requested_qty
        return total_qty

    def recursive_quantity(self, resource, parent, qty=None):
        if resource.product_id.tool_ok:
            if parent.performance > 0:
                qty = qty is None and resource.available / parent.performance or qty
            else:
                qty = qty is None and resource.available or qty
        else:
            if resource.type == 'equip'or resource.type == 'labor':
                if parent.performance > 0:
                    qty = resource.quantity / parent.performance
                else:
                    qty = qty is None and resource.available or qty
            else:
                qty = qty is None and resource.quantity or qty

        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource,parent.parent_id,qty_partial)
        else:
            result = qty * parent.quantity
            return result

