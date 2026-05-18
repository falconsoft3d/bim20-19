# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
try:
    import qrcode
except ImportError:
    _logger.error('The qrcode python library is not installed. Please install it with "pip install qrcode"')
import base64
from io import BytesIO

class MaintenanceAsset(models.Model):
    _name = 'maintenance.asset'
    _description = 'Maintenance Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Name', copy=False, required=True)
    code = fields.Char('Code', copy=False)
    desc = fields.Text('Description', copy=False)
    serial = fields.Char('Serial', copy=False)
    product_id = fields.Many2one('product.product', 'Product', copy=False)
    maintenance_task_plan_id = fields.Many2one('maintenance.task.plan', 'Maintenance Task Plan', copy=False)
    date_last_services = fields.Datetime('Date Last Service', copy=False)
    date_next_services = fields.Datetime('Date Next Service', copy=False)
    qr_code = fields.Binary(compute='_create_qrcode', string='QR Code')
    maintenance_location_id = fields.Many2one('maintenance.location', 'Location', copy=False)
    cost = fields.Monetary('Cost', copy=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', 'Currency', related='company_id.currency_id', readonly=True)
    url = fields.Char('Url', compute='_compute_url', store=True, tracking=True)
    url_qr_code = fields.Binary(compute='_create_url_qrcode', string='Url QR Code')

    @api.depends('serial')
    def _compute_url(self):
        for rec in self:
            url = ""
            bim_general_config_id = self.env['bim.general.config'].sudo().search([
                ('key', '=', 'maintenance_measure'),
            ], limit=1)
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if bim_general_config_id and param_web_base_url:
                url = param_web_base_url + '/bim/maintenance/measure/' + str(bim_general_config_id.value) + '/' + str(rec.serial)
            rec.url = url

    @api.depends('serial')
    def _create_url_qrcode(self):
        for asset in self:
            if asset.serial:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=15,
                    border=1,
                )
                qr.add_data(asset.url)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                asset.url_qr_code = base64.b64encode(temp.getvalue()).decode('ascii')
            else:
                asset.url_qr_code = False


    @api.depends('serial')
    def _create_qrcode(self):
        for asset in self:
            if asset.serial:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=15,
                    border=1,
                )
                qr.add_data(asset.serial)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                asset.qr_code = base64.b64encode(temp.getvalue()).decode('ascii')
            else:
                asset.qr_code = False


    maintenance_measure_ids = fields.One2many('maintenance.measure', 'maintenance_asset_id', 'Asset')
    count_maintenance_measure = fields.Integer('Quantity Measure', compute="_compute_count_measure")

    def _compute_count_measure(self):
        for rec in self:
            rec.count_maintenance_measure = len(rec.maintenance_measure_ids)


    def action_view_maintenance_measure(self):
        action = self.env.ref('base_bim_2.action_maintenance_measure').sudo().read()[0]
        action['domain'] = [('maintenance_asset_id', '=', self.id)]
        action['context'] = {
            'default_maintenance_asset_id': self.id,
        }
        return action