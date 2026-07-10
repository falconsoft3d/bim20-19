# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
"""
Controlador REST/JSON para autenticación del Portal BIM desde Next.js.

Endpoints:
    POST /bim_portal/auth/login   → Autenticar y obtener token
    POST /bim_portal/auth/logout  → Revocar token
    GET  /bim_portal/auth/me      → Datos del usuario autenticado
"""
import logging
from odoo import http
from odoo.http import request, Response
import json

_logger = logging.getLogger(__name__)

_CORS_HEADERS = [
    ('Access-Control-Allow-Origin', '*'),
    ('Access-Control-Allow-Methods', 'POST, GET, OPTIONS'),
    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
]


def _json_response(data: dict, status: int = 200) -> Response:
    headers = _CORS_HEADERS + [('Content-Type', 'application/json')]
    return Response(json.dumps(data), status=status, headers=headers)


def _preflight() -> Response:
    """Responde al preflight OPTIONS del navegador."""
    return Response(status=204, headers=_CORS_HEADERS)


def _get_token_from_request():
    auth_header = request.httprequest.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


class BimPortalAuthController(http.Controller):

    # ── Login ──────────────────────────────────────────────────────────────

    @http.route('/bim_portal/auth/login', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False)
    def portal_login(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        try:
            data = json.loads(request.httprequest.data or '{}')
        except (json.JSONDecodeError, Exception):
            return _json_response({'success': False, 'error': 'JSON inválido.'}, status=400)

        login_val = (data.get('login') or '').strip().lower()
        password = data.get('password') or ''

        if not login_val or not password:
            return _json_response(
                {'success': False, 'error': 'Login y contraseña son obligatorios.'}, status=400
            )

        Partner = request.env['res.partner'].sudo()
        partner = Partner.search([
            ('portal_login', '=', login_val),
            ('portal_active', '=', True),
        ], limit=1)

        if not partner or not partner.portal_verify_password(password):
            _logger.warning('BIM Portal: intento de login fallido para "%s"', login_val)
            return _json_response(
                {'success': False, 'error': 'Credenciales incorrectas o acceso desactivado.'},
                status=401,
            )

        token = request.env['bim.portal.token'].sudo().create_token(partner.id, hours=8)
        _logger.info('BIM Portal: login exitoso para partner %s (%s)', partner.id, partner.name)

        return _json_response({
            'success': True,
            'token': token,
            'partner': _partner_payload(partner),
        })

    # ── Logout ─────────────────────────────────────────────────────────────

    @http.route('/bim_portal/auth/logout', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False)
    def portal_logout(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        token = _get_token_from_request()
        if token:
            request.env['bim.portal.token'].sudo().revoke_token(token)
        return _json_response({'success': True, 'message': 'Sesión cerrada.'})

    # ── Me ─────────────────────────────────────────────────────────────────

    @http.route('/bim_portal/auth/me', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def portal_me(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        token = _get_token_from_request()
        if not token:
            return _json_response({'success': False, 'error': 'Token requerido.'}, status=401)

        partner = request.env['bim.portal.token'].sudo().validate_token(token)
        if not partner:
            return _json_response(
                {'success': False, 'error': 'Token inválido o expirado.'}, status=401
            )

        return _json_response({'success': True, 'partner': _partner_payload(partner)})


# ── Helper ─────────────────────────────────────────────────────────────────────

def _partner_payload(partner) -> dict:
    return {
        'id': partner.id,
        'name': partner.name,
        'email': partner.email or '',
        'phone': partner.phone or '',
        'login': partner.portal_login or '',
        'company': partner.parent_id.name if partner.parent_id else '',
        'responsible': partner.portal_responsible_id.name if partner.portal_responsible_id else '',
        'is_customer': partner.portal_is_customer,
        'is_employee': partner.portal_is_employee,
        'is_admin': partner.portal_is_admin,
        'is_tecno_cartas': partner.portal_is_tecno_cartas,
        'is_proveedor': partner.portal_is_proveedor,
    }


    # ── Login ──────────────────────────────────────────────────────────────

    @http.route('/bim_portal/auth/login', type='http', auth='none',
                methods=['POST'], csrf=False)
    def portal_login(self, **kwargs):
        """
        Body JSON esperado:
            { "login": "usuario", "password": "clave" }

        Respuesta exitosa (200):
            { "success": true, "token": "...", "partner": { ... } }

        Respuesta error (401):
            { "success": false, "error": "Credenciales incorrectas" }
        """
        try:
            data = json.loads(request.httprequest.data or '{}')
        except (json.JSONDecodeError, Exception):
            return _json_response({'success': False, 'error': 'JSON inválido.'}, status=400)

        login = (data.get('login') or '').strip().lower()
        password = data.get('password') or ''

        if not login or not password:
            return _json_response(
                {'success': False, 'error': 'Login y contraseña son obligatorios.'}, status=400
            )

        # Buscar partner con ese login
        Partner = request.env['res.partner'].sudo()
        partner = Partner.search([
            ('portal_login', '=', login),
            ('portal_active', '=', True),
        ], limit=1)

        if not partner or not partner.portal_verify_password(password):
            _logger.warning('BIM Portal: intento de login fallido para "%s"', login)
            return _json_response(
                {'success': False, 'error': 'Credenciales incorrectas o acceso desactivado.'},
                status=401,
            )

        # Crear token de sesión
        token = request.env['bim.portal.token'].sudo().create_token(partner.id, hours=8)
        _logger.info('BIM Portal: login exitoso para partner %s (%s)', partner.id, partner.name)

        return _json_response({
            'success': True,
            'token': token,
            'partner': _partner_payload(partner),
        })

    # ── Logout ─────────────────────────────────────────────────────────────

    @http.route('/bim_portal/auth/logout', type='http', auth='none',
                methods=['POST'], csrf=False)
    def portal_logout(self, **kwargs):
        token = _get_token_from_request()
        if token:
            request.env['bim.portal.token'].sudo().revoke_token(token)
        return _json_response({'success': True, 'message': 'Sesión cerrada.'})

    # ── Me (perfil del usuario autenticado) ────────────────────────────────

    @http.route('/bim_portal/auth/me', type='http', auth='none',
                methods=['GET'], csrf=False)
    def portal_me(self, **kwargs):
        token = _get_token_from_request()
        if not token:
            return _json_response({'success': False, 'error': 'Token requerido.'}, status=401)

        partner = request.env['bim.portal.token'].sudo().validate_token(token)
        if not partner:
            return _json_response(
                {'success': False, 'error': 'Token inválido o expirado.'}, status=401
            )

        return _json_response({'success': True, 'partner': _partner_payload(partner)})


# ── Helper ─────────────────────────────────────────────────────────────────────

def _partner_payload(partner) -> dict:
    """Devuelve los datos del partner seguros para exponer al frontend."""
    return {
        'id': partner.id,
        'name': partner.name,
        'email': partner.email or '',
        'phone': partner.phone or '',
        'login': partner.portal_login or '',
        'company': partner.parent_id.name if partner.parent_id else '',
        'responsible': partner.portal_responsible_id.name if partner.portal_responsible_id else '',
        'is_customer': partner.portal_is_customer,
        'is_employee': partner.portal_is_employee,
        'is_admin': partner.portal_is_admin,
        'is_tecno_cartas': partner.portal_is_tecno_cartas,
        'is_proveedor': partner.portal_is_proveedor,
    }
