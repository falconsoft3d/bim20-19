# -*- coding: utf-8 -*-
"""
Endpoints REST para Facturas de Proveedor del Portal BIM.
Usa account.move (in_invoice) como modelo nativo de contabilidad.

    GET  /bim_portal/facturas                  -> Lista facturas enviadas por el empleado
    POST /bim_portal/facturas                  -> Crea borrador de factura de proveedor
    GET  /bim_portal/facturas/proveedores      -> Lista proveedores disponibles
    GET  /bim_portal/facturas/proyectos        -> Lista todos los proyectos activos
    POST /bim_portal/facturas/<id>/accion      -> Aprobar / Rechazar
"""
import json
import logging
from odoo import http
from odoo.http import request
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)

_STATE_LABEL = {
    'submitted': 'Enviada',
    'approved':  'Aprobada',
    'rejected':  'Rechazada',
}


def _authenticated_employee():
    token = _get_token_from_request()
    if not token:
        return None
    partner = request.env['bim.portal.token'].sudo().validate_token(token)
    if not partner or not partner.portal_is_employee:
        return None
    return partner


def _factura_payload(move):
    ps = move.bim_portal_state or 'submitted'
    nombre = move.name
    if not nombre or nombre == '/':
        nombre = 'Borrador'
    return {
        'id':           move.id,
        'name':         nombre,
        'proveedor_id': move.partner_id.id if move.partner_id else False,
        'proveedor':    move.partner_id.name if move.partner_id else '',
        'project_id':   move.bim_project_id.id if move.bim_project_id else False,
        'project':      move.bim_project_id.name if move.bim_project_id else '',
        'importe':      move.bim_importe or move.amount_total,
        'fecha':        move.invoice_date.isoformat() if move.invoice_date else '',
        'state':        ps,
        'state_label':  _STATE_LABEL.get(ps, ps),
        'notas':        move.bim_notas or '',
        'adjuntos': [{
            'id':   att.id,
            'name': att.name,
            'url':  '/web/content/%d?download=true' % att.id,
        } for att in request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', move.id),
        ])],
    }


class BimPortalFacturasController(http.Controller):

    # Proveedores

    @http.route('/bim_portal/facturas/proveedores', type='http', auth='public',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_proveedores(self, q='', **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()
        if not _authenticated_employee():
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        domain = [('active', '=', True)]
        if q and len(q.strip()) >= 1:
            domain.append(('name', 'ilike', q.strip()))

        partners = request.env['res.partner'].sudo().search(
            domain, order='name asc', limit=100,
        )
        return _json_response({
            'success': True,
            'proveedores': [{'id': p.id, 'name': p.name} for p in partners],
        })

    # Proyectos

    @http.route('/bim_portal/facturas/proyectos', type='http', auth='public',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_proyectos(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()
        if not _authenticated_employee():
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        projects = request.env['bim.project'].sudo().search(
            [('active', '=', True)], order='name asc', limit=500,
        )
        return _json_response({
            'success': True,
            'proyectos': [{'id': p.id, 'name': p.name} for p in projects],
        })

    # Facturas

    @http.route('/bim_portal/facturas', type='http', auth='public',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def facturas(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_employee()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        if request.httprequest.method == 'GET':
            try:
                moves = request.env['account.move'].sudo().search([
                    ('bim_submitted_by', '=', partner.id),
                    ('move_type', '=', 'in_invoice'),
                ], order='invoice_date desc, id desc')
                return _json_response({
                    'success': True,
                    'facturas': [_factura_payload(m) for m in moves],
                })
            except Exception as e:
                _logger.exception('Error al listar facturas')
                return _json_response({'success': False, 'error': str(e)}, status=500)

        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except (ValueError, TypeError):
            payload = {}

        proveedor_id   = payload.get('proveedor_id')
        project_id     = payload.get('project_id')
        importe        = payload.get('importe')
        fecha          = (payload.get('fecha') or '').strip()
        notas          = (payload.get('notas') or '').strip()
        adjunto_b64    = payload.get('adjunto_b64') or ''
        adjunto_nombre = (payload.get('adjunto_nombre') or 'factura.pdf').strip()

        if not proveedor_id or not project_id:
            return _json_response(
                {'success': False, 'error': 'Proveedor y Proyecto son obligatorios.'}, status=400)
        if not importe or float(importe) <= 0:
            return _json_response(
                {'success': False, 'error': 'El importe debe ser mayor que 0.'}, status=400)
        if not fecha:
            return _json_response(
                {'success': False, 'error': 'La fecha es obligatoria.'}, status=400)

        try:
            company = request.env['res.company'].sudo().search([], limit=1)
            move = request.env['account.move'].sudo().create({
                'move_type':        'in_invoice',
                'company_id':       company.id,
                'partner_id':       int(proveedor_id),
                'invoice_date':     fecha,
                'bim_project_id':   int(project_id),
                'bim_submitted_by': partner.id,
                'bim_importe':      float(importe),
                'bim_notas':        notas,
                'bim_portal_state': 'submitted',
                'narration':        notas,
                'ref':              'Portal BIM - %s' % partner.name,
            })

            if adjunto_b64:
                request.env['ir.attachment'].sudo().create({
                    'name':      adjunto_nombre,
                    'res_model': 'account.move',
                    'res_id':    move.id,
                    'datas':     adjunto_b64,
                    'type':      'binary',
                })

            return _json_response({'success': True, 'factura': _factura_payload(move)})
        except Exception as e:
            _logger.exception('Error al crear factura de proveedor')
            return _json_response({'success': False, 'error': str(e)}, status=500)

    # Aprobar / Rechazar

    @http.route('/bim_portal/facturas/<int:factura_id>/accion', type='http',
                auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def factura_accion(self, factura_id, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_employee()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except (ValueError, TypeError):
            payload = {}

        accion = (payload.get('accion') or '').strip()
        if accion not in ('approve', 'reject'):
            return _json_response({'success': False, 'error': 'Accion invalida.'}, status=400)

        try:
            move = request.env['account.move'].sudo().search([
                ('id', '=', factura_id),
                ('bim_submitted_by', '=', partner.id),
                ('move_type', '=', 'in_invoice'),
            ], limit=1)
            if not move:
                return _json_response({'success': False, 'error': 'Factura no encontrada.'}, status=404)

            if accion == 'approve':
                move.bim_action_approve()
            else:
                move.bim_action_reject()

            return _json_response({'success': True, 'factura': _factura_payload(move)})
        except Exception as e:
            _logger.exception('Error en accion factura')
            return _json_response({'success': False, 'error': str(e)}, status=500)
