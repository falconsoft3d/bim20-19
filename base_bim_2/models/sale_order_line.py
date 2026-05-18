# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
CONCEPT_TYPE = {'H': 'labor', 'Q': 'equip', 'M': 'material', 'A': 'aux'}

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _create_order_line_concepts(self, budget_id, departure_id):
        if not budget_id or not departure_id:
            raise UserError(_('You must select a budget and a departure'))
        for line in self.filtered_domain([('display_type', '=', False)]):
            budget_id.concept_ids.create({
                'name': "%s"%(line.product_id.name),
                'budget_id': budget_id.id,
                'code': line.product_id.default_code,
                'parent_id': departure_id.id,
                'quantity': line.product_uom_qty,
                'amount_fixed': line.price_unit,
                'uom_id': line.product_uom.id,
                'product_id': line.product_id.id,
                'type': CONCEPT_TYPE[line.product_id.resource_type]})



