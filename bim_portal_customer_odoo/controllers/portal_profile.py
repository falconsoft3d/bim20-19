# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
"""
Controlador REST para el perfil del usuario autenticado en el Portal BIM.

Endpoints:
    GET  /bim_portal/profile          → Datos del perfil
    POST /bim_portal/profile/update   → Actualizar nombre, email, teléfono
    POST /bim_portal/profile/change_password → Cambiar contraseña
"""
import logging
import json
from odoo import http
from odoo.http import request, Response
from .portal_auth import _json_response, _preflight, _get_token_from_request, _partner_payload

_logger = logging.getLogger(__name__)


def _authenticated_partner():
    """Devuelve el partner si el token Bearer es válido, o None."""
    token = _get_token_from_request()
    if not token:
        return None
    return request.env['bim.portal.token'].sudo().validate_token(token)


class BimPortalProfileController(http.Controller):

    # ── Obtener perfil ─────────────────────────────────────────────────────

    @http.route('/bim_portal/profile', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_profile(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        return _json_response({'success': True, 'partner': _partner_payload(partner)})

    # ── Actualizar datos ───────────────────────────────────────────────────

    @http.route('/bim_portal/profile/update', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False)
    def update_profile(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        try:
            data = json.loads(request.httprequest.data or '{}')
        except (json.JSONDecodeError, Exception):
            return _json_response({'success': False, 'error': 'JSON inválido.'}, status=400)

        vals = {}
        if 'name' in data and data['name'].strip():
            vals['name'] = data['name'].strip()
        if 'email' in data:
            vals['email'] = (data['email'] or '').strip()
        if 'phone' in data:
            vals['phone'] = (data['phone'] or '').strip()

        if vals:
            partner.sudo().write(vals)

        return _json_response({'success': True, 'partner': _partner_payload(partner)})

    # ── Cambiar contraseña ─────────────────────────────────────────────────

    @http.route('/bim_portal/profile/change_password', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False)
    def change_password(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        try:
            data = json.loads(request.httprequest.data or '{}')
        except (json.JSONDecodeError, Exception):
            return _json_response({'success': False, 'error': 'JSON inválido.'}, status=400)

        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not current_password or not new_password or not confirm_password:
            return _json_response(
                {'success': False, 'error': 'Todos los campos de contraseña son obligatorios.'},
                status=400,
            )

        if not partner.portal_verify_password(current_password):
            return _json_response(
                {'success': False, 'error': 'La contraseña actual es incorrecta.'},
                status=400,
            )

        if new_password != confirm_password:
            return _json_response(
                {'success': False, 'error': 'Las contraseñas nuevas no coinciden.'},
                status=400,
            )

        if len(new_password) < 8:
            return _json_response(
                {'success': False, 'error': 'La contraseña debe tener al menos 8 caracteres.'},
                status=400,
            )

        partner.portal_set_password(new_password)
        _logger.info('BIM Portal: contraseña cambiada para partner %s', partner.id)

        return _json_response({'success': True, 'message': 'Contraseña actualizada correctamente.'})
