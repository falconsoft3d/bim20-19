from odoo import api, fields, models, tools, _

class VirtualProduct(models.Model):
    _name = 'virtual.product'
    _description = 'Virtual Product'

    name = fields.Char()
    reference = fields.Char()
    barcode = fields.Char()
    sales_price = fields.Float('Sales Price', default=1.0)  # list_price in product.template
    purchase_price = fields.Float('Cost Price', default=1.0)  # standard_price in product.template
    convert_pt = fields.Boolean('Converted to Product template?', default=False, readonly=True)
    convert_pp = fields.Boolean('Converted to Product ?', default=False, readonly=True)
    product_id = fields.Many2one('product.product', "Product", ondelete='restrict')
    product_tmpl_id = fields.Many2one('product.template', "Product Template", ondelete='restrict')
    lines_ids = fields.One2many('virtual.product.line', 'virtual_id', 'Lines')
    origin = fields.Char('Origin')
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now)
    categ_id = fields.Many2one('virtual.product.category', "Category", ondelete='restrict')
    sub_categ_id = fields.Many2one('virtual.product.category', "Sub Category", ondelete='restrict')

    @tools.ormcache()
    def _get_default_uom_id(self):
        return self.env.ref('uom.product_uom_unit')

    uom_id = fields.Many2one(
        'uom.uom', 'Unit of Measure',
        default=_get_default_uom_id, required=True,
        help="Default unit of measure used for all stock operations.")

    def convert_to_product(self,type_converted):
        product = False
        product_convert = self.env['product.template'] if type_converted == 'pt' else self.env['product.product']
        product_data = {
            "name": self.name,
            "default_code": self.reference,
            "barcode": self.barcode,
            "list_price": self.sales_price,
            "standard_price": self.purchase_price,
        }
        if type_converted == "pp":
            self.convert_pp = True
        if type_converted == "pt":
            self.convert_pt = True

        product = product_convert.create(product_data)
        return product


class VirtualProductLine(models.Model):
    _description = "Virtual Product Line"
    _name = 'virtual.product.line'

    name = fields.Many2one('bim.attribute', string='Attribute')
    value_id = fields.Many2one('bim.attribute.value', string='Value')
    virtual_id = fields.Many2one('virtual.product', ondelete='cascade')
    sequence = fields.Integer('Sequence', default=1)
