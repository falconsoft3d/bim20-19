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
    @http.route('/bim/docs/budgets/<key>', methods=['GET'],  cors='*', auth='public')
    def get_document(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        budget_id = http.request.env['bim.budget'].sudo().search([
            ('key', '=', kwargs.get('key')),
            ('share', '=', True),
        ], limit=1)

        if budget_id:
           budget_id.sudo().write({
               'number_open': budget_id.number_open + 1,
               'open_date': fields.Datetime.now(),
           })


        return env.get_template('share_budget.html').render({
                'csrf_token': http.request.csrf_token(),
                'budget_id': budget_id,
            })