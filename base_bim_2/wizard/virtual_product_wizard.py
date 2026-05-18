from odoo import fields, models, api
from odoo.exceptions import UserError


class ProductWizard(models.TransientModel):
    _name = 'virtual.product.wizard'
    _description = 'Wizard to convert virtual product'

    selection_type = fields.Selection(
        string='Product Type',
        selection=[('pt', 'Product Template'),
                   ('pp', 'Product Product'), ],
        default='pp',
        required=False, )

    def action_convert_product(self):
        selection_type = self.selection_type
        product_ids = self.env['virtual.product'].browse(self._context.get('active_ids', False))

        product_convert = self.env['product.template']
        type_converted = "pt"

        if selection_type == "pp":
            product_convert = self.env['product.product']
            type_converted = "pp"

        for product in product_ids:
            product_data = {
                "name": product.name,
                "default_code": product.reference,
                "barcode": product.barcode,
                "list_price": product.sales_price,
                "standard_price": product.purchase_price,
            }

            new_product_id = product_convert.create(product_data)


            if type_converted == "pp":
                if product.product_id:
                    raise UserError("This virtual product has already been converted to a product")
                product.convert_pp = True
                product.product_id = new_product_id.id
                product.product_tmpl_id = new_product_id.product_tmpl_id.id
                product.product_tmpl_id.virtual_product_id = product.id


            if type_converted == "pt":
                if product.product_tmpl_id:
                    raise UserError("This virtual product has already been converted to a product")
                product.convert_pt = True
                product.product_tmpl_id = new_product_id.id

            product_convert.create(product_data)
            # TODO ask for unlink the virtual product
