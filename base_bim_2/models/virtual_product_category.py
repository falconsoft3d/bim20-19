from odoo import api, fields, models, tools, _

class VirtualProductCategory(models.Model):
    _name = 'virtual.product.category'
    _description = 'Virtual Product'

    name = fields.Char()
    parent_id = fields.Many2one('virtual.product.category', string='Parent Category', index=True, ondelete='cascade')