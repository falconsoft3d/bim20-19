# -*- coding: utf-8 -*-
"""
Controlador REST para Solicitudes de Ausencia del Portal BIM.

Endpoints:
    GET  /bim_portal/ausencias          → Lista las ausencias del empleado autenticado
    POST /bim_portal/ausencias          → Crea una nueva solicitud de ausencia
"""
import json
import logging
from odoo import http
from odoo.http import request
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)

_ESTADO_LABEL = {
    'draft': 'Borrador',
    'submitted': 'Enviada',
    'approved': 'Aprobada',
    'rejected': 'Rechazada',
}
_TIPO_LABEL = {
    'vacaciones': 'Vacaciones',
    'permiso': 'Permiso',
    'otros': 'Otros',
}


def _authenticated_employee():
    token = _get_token_from_request()
    if not token:
        return None
    partner = request.env['bim.portal.token'].sudo().validate_token(token)
    if not partner or not partner.portal_is_employee:
        return None
    return partner


def _ausencia_payload(aus):
    return {
        'id': aus.id,
        'name': aus.name,
        'tipo': aus.tipo,
        'tipo_label': _TIPO_LABEL.get(aus.tipo, aus.tipo),
        'state': aus.state,
        'state_label': _ESTADO_LABEL.get(aus.state, aus.state),
        'date_create': aus.date_create.isoformat() if aus.date_create else '',
        'date_from': aus.date_from.isoformat() if aus.date_from else '',
        'date_to': aus.date_to.isoformat() if aus.date_to else '',
        'descripcion': aus.descripcion or '',
    }


class BimPortalAusenciasController(http.Controller):

    @http.route('/bim_portal/ausencias', type='http', auth='none',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def ausencias(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_employee()
        if not partner:
            return _json_response(
                {'success': False, 'error': 'No autenticado o sin acceso de empleado.'}, status=401)

        # ── GET: lista ──────────────────────────────────────────────────────
        if request.httprequest.method == 'GET':
            ausencias = request.env['bim.solicitud.ausencia'].sudo().search(
                [('partner_id', '=', partner.id)],
                order='date_create desc',
            )
            return _json_response({
                'success': True,
                'ausencias': [_ausencia_payload(a) for a in ausencias],
            })

        # ── POST: crear ─────────────────────────────────────────────────────
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except (ValueError, TypeError):
            payload = {}

        tipo = (payload.get('tipo') or '').strip()
        date_from = (payload.get('date_from') or '').strip()
        date_to = (payload.get('date_to') or '').strip()
        descripcion = (payload.get('descripcion') or '').strip()

        if tipo not in ('vacaciones', 'permiso', 'otros'):
            return _json_response(
                {'success': False, 'error': 'Tipo de ausencia inválido.'}, status=400)
        if not date_from or not date_to:
            return _json_response(
                {'success': False, 'error': 'Las fechas son obligatorias.'}, status=400)
        if date_from > date_to:
            return _json_response(
                {'success': False, 'error': 'La fecha desde no puede ser posterior a la fecha hasta.'}, status=400)

        aus = request.env['bim.solicitud.ausencia'].sudo().create({
            'partner_id': partner.id,
            'tipo': tipo,
            'date_from': date_from,
            'date_to': date_to,
            'descripcion': descripcion,
        })
        return _json_response({'success': True, 'ausencia': _ausencia_payload(aus)})
