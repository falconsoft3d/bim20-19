
from odoo import _, api, fields, models


class BimBudgetResource(models.Model):
    _name = 'bim.budget.resource'
    _description = 'Bim Budget Resource'
    _order = 'product_id'

    product_id = fields.Many2one('product.product', required=True)
    budget_id = fields.Many2one('bim.budget', ondelete='cascade')
    budget_qty = fields.Float(digits='BIM qty')
    requested_qty = fields.Float(digits='BIM qty')
    uom_id = fields.Many2one('uom.uom')




