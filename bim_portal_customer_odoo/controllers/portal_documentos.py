# -*- coding: utf-8 -*-
"""
Endpoints REST para Documentos del Portal BIM (área Cliente).

    GET  /bim_portal/cliente/documentos   → Documentos compartidos de los proyectos del cliente
"""
import logging
from odoo import http
from odoo.http import request
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)


def _authenticated_customer():
    token = _get_token_from_request()
    if not token:
        return None
    partner = request.env['bim.portal.token'].sudo().validate_token(token)
    if not partner or not partner.portal_is_customer:
        return None
    return partner


def _documento_payload(doc):
    download_url = doc.url_file or (
        '/web/content/bim.documentation/%d/file_01/%s' % (doc.id, doc.file_name or 'documento')
        if doc.file_01 else ''
    )
    return {
        'id':             doc.id,
        'name':           doc.name or '',
        'desc':           doc.desc or '',
        'date':           doc.date.isoformat() if doc.date else '',
        'project_id':     doc.project_id.id if doc.project_id else False,
        'project_name':   doc.project_id.name if doc.project_id else '',
        'categoria_id':   doc.portal_categoria_id.id if doc.portal_categoria_id else False,
        'categoria_name': doc.portal_categoria_id.name if doc.portal_categoria_id else 'Sin categoría',
        'file_name':      doc.file_name or '',
        'download_url':   download_url,
        'has_file':       bool(doc.file_01 or doc.url_file),
        'share_url':      doc.share_url or '',
        'type':           doc.type or '',
    }


class BimPortalDocumentosController(http.Controller):

    @http.route('/bim_portal/cliente/documentos', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_documentos(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_customer()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        try:
            projects = request.env['bim.project'].sudo().search([
                '|',
                ('customer_id', '=', partner.id),
                ('customer_ids', 'in', [partner.id]),
            ])
            docs = request.env['bim.documentation'].sudo().search([
                ('project_id', 'in', projects.ids),
                ('share', '=', True),
            ], order='date desc, id desc')

            return _json_response({
                'success': True,
                'documentos': [_documento_payload(d) for d in docs],
            })
        except Exception as e:
            _logger.exception('Error al listar documentos del portal')
            return _json_response({'success': False, 'error': str(e)}, status=500)
