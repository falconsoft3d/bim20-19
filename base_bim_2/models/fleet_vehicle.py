from odoo import api, fields, models, _
from datetime import datetime, date, timedelta

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    fleet_vehicle_price_id = fields.Many2one('fleet.vehicle.price', string='Fleet Vehicle Price')
    product_id = fields.Many2one('product.product', 'Product')
    rent_state = fields.Selection([
        ('available', 'Available'),
        ('rented', 'Rented'),
    ], string='Rent State', default='available', required=True)


class FleetVehiclePrice(models.Model):
    _description = "Fleet Vehicle Price"
    _name = 'fleet.vehicle.price'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char('Name', required=True)
    price = fields.Float('Price')
