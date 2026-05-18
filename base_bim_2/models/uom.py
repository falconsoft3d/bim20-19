from odoo import fields, models, _


class UomUom(models.Model):
    _inherit = 'uom.uom'

    alt_names = fields.Char('Alternative names', help='Possible names by which this unit of measure can be searched.')
    default_bim_unit = fields.Boolean('Default BIM unit', help='If checked, this unit will be used as default unit for BIM quantities.')
