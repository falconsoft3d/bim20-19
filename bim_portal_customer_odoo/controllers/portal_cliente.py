# -*- coding: utf-8 -*-
"""
Controlador REST para el área Cliente del Portal BIM.

Endpoints:
    GET  /bim_portal/cliente/avances                        → Lista avances de obras del cliente
    GET  /bim_portal/cliente/avances/<int:id>               → Detalle de un avance con imágenes
    GET  /bim_portal/cliente/avances/<int:id>/messages      → Comentarios del chatter
    POST /bim_portal/cliente/avances/<int:id>/messages      → Añadir un comentario
"""
import json
import logging
import base64
from markupsafe import Markup
from odoo import http
from odoo.http import request
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)


def _authenticated_partner():
    token = _get_token_from_request()
    if not token:
        return None
    return request.env['bim.portal.token'].sudo().validate_token(token)


def _avance_payload(avance, include_lines=False):
    data = {
        'id': avance.id,
        'name': avance.name,
        'fecha': avance.fecha.isoformat() if avance.fecha else '',
        'user': avance.user_id.name if avance.user_id else '',
        'project_id': avance.project_id.id,
        'project_name': avance.project_id.name if avance.project_id else '',
        'descripcion': avance.descripcion or '',
        'image_count': len(avance.line_ids),
    }
    if include_lines:
        lines = []
        for ln in avance.line_ids.sorted('sequence'):
            img_b64 = ''
            if ln.image:
                img_b64 = ln.image.decode('utf-8') if isinstance(ln.image, bytes) else ln.image
            lines.append({
                'id': ln.id,
                'name': ln.name or '',
                'image': img_b64,
            })
        data['lines'] = lines
    return data


class BimPortalClienteController(http.Controller):

    def _get_partner_projects(self, partner):
        """Devuelve proyectos donde el partner es cliente (customer_id o customer_ids)."""
        return request.env['bim.project'].sudo().search([
            '|',
            ('customer_id', '=', partner.id),
            ('customer_ids', 'in', [partner.id]),
        ])

    # ── Lista de avances ────────────────────────────────────────────────────

    @http.route('/bim_portal/cliente/avances', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_avances(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)
        if not partner.portal_is_customer:
            return _json_response({'success': False, 'error': 'Sin acceso.'}, status=403)

        projects = self._get_partner_projects(partner)
        avances = request.env['bim.avance.obra'].sudo().search(
            [('project_id', 'in', projects.ids)],
            order='fecha desc, id desc',
        )

        return _json_response({
            'success': True,
            'avances': [_avance_payload(a) for a in avances],
        })

    # ── Detalle de un avance ────────────────────────────────────────────────

    @http.route('/bim_portal/cliente/avances/<int:avance_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_avance(self, avance_id, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)
        if not partner.portal_is_customer:
            return _json_response({'success': False, 'error': 'Sin acceso.'}, status=403)

        projects = self._get_partner_projects(partner)
        avance = request.env['bim.avance.obra'].sudo().search(
            [('id', '=', avance_id), ('project_id', 'in', projects.ids)], limit=1
        )
        if not avance:
            return _json_response({'success': False, 'error': 'Avance no encontrado.'}, status=404)

        return _json_response({'success': True, 'avance': _avance_payload(avance, include_lines=True)})

    # ── Mensajes / Chatter ──────────────────────────────────────────────────

    @http.route('/bim_portal/cliente/avances/<int:avance_id>/messages', type='http',
                auth='none', methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def avance_messages(self, avance_id, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)
        if not partner.portal_is_customer:
            return _json_response({'success': False, 'error': 'Sin acceso.'}, status=403)

        projects = self._get_partner_projects(partner)
        avance = request.env['bim.avance.obra'].sudo().search(
            [('id', '=', avance_id), ('project_id', 'in', projects.ids)], limit=1
        )
        if not avance:
            return _json_response({'success': False, 'error': 'Avance no encontrado.'}, status=404)

        # ── GET: lista de mensajes ──
        if request.httprequest.method == 'GET':
            messages = request.env['mail.message'].sudo().search([
                ('model', '=', 'bim.avance.obra'),
                ('res_id', '=', avance.id),
                ('message_type', 'in', ['comment', 'email']),
            ], order='date asc')

            result = []
            for msg in messages:
                result.append({
                    'id': msg.id,
                    'author': msg.author_id.name if msg.author_id else 'Sistema',
                    'date': msg.date.isoformat() if msg.date else '',
                    'body': msg.body or '',
                })
            return _json_response({'success': True, 'messages': result})

        # ── POST: nuevo comentario ──
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except (ValueError, TypeError):
            payload = {}

        body = (payload.get('body') or '').strip()
        if not body:
            return _json_response({'success': False, 'error': 'El comentario no puede estar vacío.'}, status=400)

        msg = avance.sudo().message_post(
            body=Markup(body.replace('\n', '<br/>')),
            author_id=partner.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return _json_response({
            'success': True,
            'message': {
                'id': msg.id,
                'author': partner.name,
                'date': msg.date.isoformat() if msg.date else '',
                'body': msg.body or '',
            },
        })
