from odoo import api, fields, models,_


class BimFuelCost(models.Model):
    _name = "bim.fuel.cost"
    _description = "Bim Fuel Cost"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = "cost"

    cost = fields.Float("Cost", tracking=True, digits='BIM price')
    type = fields.Selection([('gas','Gas'),('diesel','Diesel')], required=True)

    def default_currency_id(self):
        return self.env.company.currency_id.id or False
    currency_id = fields.Many2one('res.currency', default=default_currency_id)

