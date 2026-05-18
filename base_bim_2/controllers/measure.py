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

class MaintenanceMeasureWeb(http.Controller):


    @http.route('/bim/maintenance/measure/<key>/<serial>', methods=['GET'],  cors='*', auth='public')
    def get_measure(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        web_key =kwargs.get('key')
        serial = kwargs.get('serial')

        config_key = http.request.env['bim.general.config'].sudo().search([
            ('key', '=', 'maintenance_measure'),
        ], limit=1)

        _logger.info('config_key: %s', config_key.value)
        _logger.info('web_key: %s', web_key)

        if str(config_key.value) == str(web_key):
            return env.get_template('maintenance_measure.html').render({
                    'csrf_token': http.request.csrf_token(),
                    'key': config_key.value,
                    'serial': serial,
                })
        else:
            _logger.info('2')

    @http.route('/bim/maintenance/measure/<key>/<serial>', type='json', auth='public', cors='*')
    def save_measure(self, **kwargs):
        ok = False

        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user')
        web_key =kwargs.get('key')
        serial = kwargs.get('serial')
        value = kwargs.get('value')

        config_key = http.request.env['bim.general.config'].sudo().search([
            ('key', '=', 'maintenance_measure'),
        ], limit=1)

        if str(config_key.value) == str(web_key):
            # buscamos el activo
            maintenance_asset_id = http.request.env['maintenance.asset'].sudo().search([
                ('serial', '=', serial),
            ], limit=1)

            # buscar el usuario por el email
            user_id = http.request.env['res.users'].sudo().search([
                ('login', '=', user),
            ], limit=1)

            if maintenance_asset_id and user_id:
                vals = {
                    'maintenance_asset_id': maintenance_asset_id.id,
                    'user_id': user_id.id,
                    'value' : value,
                    'company_id': maintenance_asset_id.company_id.id,
                }
                measure_id = http.request.env['maintenance.measure'].sudo().create(vals)
                if measure_id:
                    ok = True

        if ok:
            return {
                'status': 'ok',
            }
        else:
            return {
                'status': 'error',
            }