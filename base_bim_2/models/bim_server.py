# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class BimServer(models.Model):
    _name = 'bim.server'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Server'
    _order = 'id desc'

    name = fields.Char("Name", required=True, tracking=True)
    url = fields.Char("URL", required=True,
                        default='https://developer.api.autodesk.com/',
                        tracking=True)
    client_id = fields.Char("Client ID", required=True)
    client_secret = fields.Char("Client Secret", required=True)
    token = fields.Char("Token", default="Para conectarse a la nube de Autodesk cree una app en: https://aps.autodesk.com/")
    date_token = fields.Datetime("Date Token")
    date_expiration = fields.Datetime("Date Expiration")
    user_id = fields.Many2one('res.users', "User", default=lambda self: self.env.user.id)
    save_model = fields.Boolean("Save Model", default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    def get_token(self):
        _logger.info("get_token BimServer")
        if not self.token or self.date_expiration < fields.Datetime.now():
            self.create_token()
        return self.token


    def create_token(self):
        _logger.info("create_token BimServer")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': 'bucket:create bucket:read data:write data:read',
        }
        response = requests.post(self.url + "authentication/v2/token", headers=headers, data=data)
        if response.status_code == 200:
            data = json.loads(response.text)
            self.token = data['access_token']
            self.date_token = fields.Datetime.now()
            self.date_expiration = fields.Datetime.now() + timedelta(seconds=data['expires_in'])
        else:
            raise UserError(_("Error al obtener el token: %s") % response.text)