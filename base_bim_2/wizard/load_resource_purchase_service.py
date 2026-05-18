# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class ResourcePurchaseServiceWizard(models.TransientModel):
    _name = 'resource.purchase.service.wzd'
    _description = 'Load Project Resources Services'

    def _get_default_project_id(self):
        _logger.info('Context: %s', self._context)
        active_id = self._context.get('active_id')
        req = self.env['bim.purchase.services'].browse(active_id)
        return req.project_id and req.project_id.id or False

    project_id = fields.Many2one("bim.project", string="Project", default=_get_default_project_id)
    budget_ids = fields.Many2many("bim.budget", string="Budgets")
    service_type = fields.Selection([('own','Own Services'),('subcontract','Sub-Contract'),('all','All')], required=True)
    concept_ids = fields.Many2many('bim.concepts', string='Concepts')

    def load_resources(self):
        if not self.budget_ids:
            raise UserError(_('Please, select at least one Budget.'))

        service_id = self._context.get('active_id')
        ProductList = self.env['service.list']
        concept_ids = []
        for budget in self.budget_ids:
            for concept in budget.concept_ids:
                if self.concept_ids:
                    if concept.parent_id and concept.parent_id in self.concept_ids:
                        concept_ids.append(concept.id)
                else:
                    concept_ids.append(concept.id)

        concepts = self.env['bim.concepts'].browse(concept_ids)

        req = self.env['bim.purchase.services'].browse(service_id)

        if not req.buy_more:
            req.product_ids.unlink()

        if req.separate:
            for concept in concepts:
                if concept.type == 'departure':
                    continue
                if concept.type in ['material', 'equip', 'labor','subcontract'] and concept.subcon:
                    resource = concept.product_id

                    if concept.available > 0:
                        quantity = concept.available * concept.parent_id.quantity
                        cost = resource.seller_ids[0].price if resource.seller_ids else resource.standard_price
                        if concept.day_price > 0:
                            cost = concept.day_price
                    else:
                        quantity = concept.quantity * concept.parent_id.quantity
                        cost = resource.seller_ids[0].price if resource.seller_ids else resource.standard_price

                    val = {
                            'service_id': service_id,
                            'budget_id': concept.budget_id.id,
                            'product_id': concept.product_id.id,
                            'bim_concepts_id': concept.parent_id.id,
                            'partner_ids': [(4, resource.seller_ids[0].partner_id.id)] if resource.seller_ids else False,
                            'um_id': resource.uom_id.id,
                            'quant': quantity,
                            'cost': cost,
                            'analytic_id': self.project_id.analytic_id.id or False
                        }
                    req.product_ids.create(val)
        else:
            resources = self.get_resources(concepts)

            for resource in resources:
                quantity = self.get_quantity(concepts,resource)

                val = {
                    'service_id': service_id,
                    'product_id': resource.id,
                    'partner_ids': [(4,resource.seller_ids[0].partner_id.id)] if resource.seller_ids else False,
                    'um_id': resource.uom_id.id,
                    'quant': quantity,
                    'cost': resource.seller_ids[0].price if resource.seller_ids else resource.standard_price,
                    'analytic_id': self.project_id.analytic_id.id or False}

                ProductList.create(val)

    def get_service_type(self):
        if self.service_type == 'own':
            service_type = [False]
        elif self.service_type == 'subcontract':
            service_type = [True]
        else:
            service_type = [True, False]
        return service_type

    def get_resources(self,concepts):
        domain = ['material','equip','labor','subcontract']
        service_type = self.get_service_type()
        active_id = self._context.get('active_id')
        current_products = self.env['bim.purchase.services'].browse(active_id).browse(active_id).product_ids.mapped(
            'product_id.id') or []

        if self.service_type == 'subcontract':
            domain = ['subcontract']

        resources = concepts.filtered(lambda c: c.type in domain and c.product_id.type == 'service').mapped('product_id').filtered_domain([('id','not in',current_products)])
        resources2 = resources.filtered_domain([('type','=','service')])
        return resources2

    def get_quantity(self,concepts,resource):
        service_type = self.get_service_type()
        records = concepts.filtered(lambda c: c.product_id.id == resource.id and c.product_id.type == 'service')
        total_qty = 0
        for rec in records:
            if rec.quantity > 0 and rec.parent_id.quantity > 0:
                total_qty += self.recursive_quantity(rec,rec.parent_id,None)
        return total_qty

    def recursive_quantity(self, resource, parent, qty=None):
        if resource.product_id.name == 'ESCALERA TELESCOPICA':
            _logger.info('Recursive Quantity: %s, Parent: %s, Qty: %s', resource.name, parent.name, qty)
        response = 0
        # if si es equipo o mano de obra y el rendimiento es mayor que 0, se multiplica por el rendimiento
        if resource.type in ['equip', 'labor'] and parent.performance > 0:
            response = resource.quantity * parent.quantity / parent.performance
        else:
            response = resource.quantity * parent.quantity
        if resource.product_id.name == 'ESCALERA TELESCOPICA':
            _logger.info('Calculated Response (ESCALERA TELESCOPICA): %s', response)
        return response

