import jinja2
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo import models, fields, _
import werkzeug
import werkzeug.utils
import json
import base64
from datetime import date
import logging
_logger = logging.getLogger(__name__)

loader = jinja2.PackageLoader('odoo.addons.base_bim_2', 'web')
env = jinja2.Environment(loader=loader, autoescape=True)

class BimWebBudget(http.Controller):
    @http.route('/bim/docs/model/<urn2>', type='http', auth='user', website=True)
    def get_document(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        bim_model_id = http.request.env['bim.model'].sudo().search([
            ('urn2', '=', kwargs.get('urn2')),
        ], limit=1)

        model_name = bim_model_id.name
        token = bim_model_id.bim_bucket_id.bim_server_id.get_token()
        urn = bim_model_id.urn2

        return env.get_template('autodesk_viewer.html').render({
                'csrf_token': http.request.csrf_token(),
                'model_name': model_name,
                'token': token,
                'urn': urn,
            })