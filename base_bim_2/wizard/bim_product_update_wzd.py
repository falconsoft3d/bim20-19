# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests


class BimProductUpdateWzd(models.TransientModel):
    _name = 'bim.product.update.wzd'
    _description = 'Bim Product Update Wzd'

    def _get_default_product_templates(self):
        ids = self.env.context.get('active_ids', [])
        templates = self.env['product.template'].browse(ids).ids or []
        return templates

    template_ids = fields.Many2many('product.template', string='Concept Template', default=_get_default_product_templates)
    region = fields.Char(required=True)

    @api.onchange('template_ids')
    def onchange_template_ids(self):
        Parameters = self.env['ir.config_parameter'].sudo()
        master_region = Parameters.get_param('master_region')
        self.region = master_region

    def action_update_product_from_master(self):
        Parameters = self.env['ir.config_parameter'].sudo()
        master_url = Parameters.get_param('master_url')
        if not master_url:
            raise ValidationError(_("It is necessary to set Master Url"))
        master_token = Parameters.get_param('master_token')
        if not master_url:
            raise ValidationError(_("It is necessary to set Master Token"))
        for template_id in self.template_ids:
            url = "%s/api/get_product/%s/%s/%s"%(master_url,self.region,master_token,template_id.default_code)
            payload = {}
            headers = {}
            response = requests.request("GET", url, headers=headers, data=payload)
            if response and response.status_code == 200:
                json = response.json()
                if json:
                    vals = {}
                    if "name" in json:
                        vals.update({'name': json['name']})
                    if "cost" in json:
                        vals.update({'standard_price': json['cost']})
                    if vals:
                        template_id.write(vals)
                else:
                    raise ValidationError(_("No information was found"))