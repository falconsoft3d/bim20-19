# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class TmsShipment(models.Model):
    _description = "Tms Shipment"
    _name = 'tms.shipment'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),], string='Status',
        tracking=True, default='draft', copy=False, index=True)

    bim_transport_equipment_id = fields.Many2one('fleet.vehicle', string='Equipment')

    bim_project_origin_id = fields.Many2one('bim.project', string='Origin Project')
    bim_project_destination_id = fields.Many2one('bim.project', string='Destination Project')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)


    driver_id = fields.Many2one('res.partner', string='Driver')

    price = fields.Float('Price')
    qty = fields.Float('Quantity')
    total = fields.Float('Total')

    begin_kilometers = fields.Float('Begin kilometers')
    end_kilometers = fields.Float('End kilometers')

    fleet_vehicle_odometer_id = fields.Many2one('fleet.vehicle.odometer', string='Odometer')

    date = fields.Datetime('Fecha', default=fields.Datetime.now)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def action_confirm_tms_shipment(self):
        for record in self:
            if record.state == 'draft':
                record.exe_confirm()


    @api.onchange('bim_transport_equipment_id')
    def _onchange_bim_transport_equipment_id(self):
        if self.bim_transport_equipment_id:
            self.driver_id = self.bim_transport_equipment_id.driver_id.id
            self.price = self.bim_transport_equipment_id.fleet_vehicle_price_id.price
            self.begin_kilometers = self.bim_transport_equipment_id.odometer


    @api.onchange('begin_kilometers', 'end_kilometers')
    def _onchange_end_kilometers(self):
        if self.begin_kilometers and self.end_kilometers:
            self.qty = self.end_kilometers - self.begin_kilometers


    def exe_cancel(self):
        self.write({'state': 'cancelled'})


    def exe_draft(self):
        self.write({'state': 'draft'})


    def exe_confirm(self):
        if not self.bim_transport_equipment_id:
            raise UserError(_('You must select a vehicle'))

        if not self.bim_project_origin_id:
            raise UserError(_('You must select a origin project'))

        if not self.bim_project_destination_id:
            raise UserError(_('You must select a destination project'))


        if self.end_kilometers < self.begin_kilometers:
            raise UserError(_('End kilometers must be greater than begin kilometers'))

        self.price = self.bim_transport_equipment_id.fleet_vehicle_price_id.price
        self.qty = self.end_kilometers - self.begin_kilometers

        bim_general_config_id = self.env['bim.general.config'].search([
            ('key', '=', 'como_imputa_viajes')
        ], limit=1)

        if bim_general_config_id:
            value = float(bim_general_config_id.value)
            if value != 50:
                self.total = self.price * self.qty * value / 100
            else:
                if self.bim_project_origin_id != self.bim_project_destination_id:
                    self.total = ( self.price * self.qty ) / 2
                else:
                    self.total = self.price * self.qty
        else:
            if self.bim_project_origin_id != self.bim_project_destination_id:
                self.total = ( self.price * self.qty ) / 2
            else:
                self.total = self.price * self.qty



        if not self.fleet_vehicle_odometer_id:
            self.fleet_vehicle_odometer_id = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.bim_transport_equipment_id.id,
                'value': self.end_kilometers,
                'date': self.date,
            })
        else:
            self.fleet_vehicle_odometer_id.write({
                'value': self.end_kilometers,
                'date': self.date,
            })

        self.write({'state': 'confirmed'})

    # Calc total onchange
    @api.onchange('price', 'qty')
    def _onchange_total(self):
        self.total = self.price * self.qty

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('tms.shipment') or 'New'
        return super().create(vals_list)