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

class BimWeb(http.Controller):
    @http.route('/bim/document/<key>', methods=['GET'],  cors='*', auth='public')
    def get_document(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        doc_id = http.request.env['bim.documentation'].sudo().search([
            ('key', '=', kwargs.get('key')),
            ('share', '=', True),
        ], limit=1)

        if doc_id:
           doc_id.sudo().write({
               'number_open': doc_id.number_open + 1,
               'open_date': fields.Datetime.now(),
           })

        return env.get_template('document.html').render({
                'csrf_token': http.request.csrf_token(),
                'doc_id': doc_id,
            })


    @http.route('/bim/document/download/<key>', methods=['GET'], cors='*', auth='public')
    def download_document(self, key, **kwargs):
        # Buscar el documento
        doc_id = request.env['bim.documentation'].sudo().search([
            ('key', '=', key),
            ('share', '=', True),
        ], limit=1)

        if not doc_id:
            return werkzeug.wrappers.Response("Documento no encontrado o no compartido.", status=404)

        # Incrementar el contador de apertura del documento
        doc_id.sudo().write({
            'number_open': doc_id.number_open + 1,
            'open_date': fields.Datetime.now(),
        })

        # Obtener el archivo
        file_content = doc_id.file_01
        if not file_content:
            return werkzeug.wrappers.Response("El documento no tiene un archivo adjunto.", status=404)

        # Decodificar base64 si es necesario
        file_binary = base64.b64decode(file_content)

        # Obtener el nombre del archivo
        filename = doc_id.file_name or "documento.pdf"

        # Crear la respuesta HTTP para la descarga
        response = werkzeug.wrappers.Response(file_binary, content_type='application/octet-stream')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response