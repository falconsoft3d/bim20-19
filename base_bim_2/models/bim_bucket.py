# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class BimBucket(models.Model):
    _name = 'bim.bucket'
    _description = 'Bim Bucket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char("Name", required=True, tracking=True)
    bim_server_id = fields.Many2one('bim.server', "Bim Server", required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    def create_bucket(self):
        for record in self:
            _logger.info("crate_bucket BimBucket")
            access_token = record.bim_server_id.get_token()
            bucket_url = record.bim_server_id.url + "oss/v2/buckets"
            headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            bucket_data = {
                "bucketKey": record.name,
                "policyKey": "transient"
            }
            response = requests.post(bucket_url, json=bucket_data, headers=headers)
            _logger.info(response.text)


            if response.status_code == 409:
                _logger.info("Bucket already exists")
                raise UserError(_("Bucket already exists"))

            record.message_post(body=response.text)
