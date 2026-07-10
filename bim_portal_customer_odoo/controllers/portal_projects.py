# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
"""
Controlador REST para proyectos BIM del Portal de clientes.

Endpoints:
    GET /bim_portal/projects          → Lista obras donde el partner es Supervisor
    GET /bim_portal/projects/<int:id> → Detalle de una obra
"""
import json
import logging
from odoo import http
from odoo.http import request, Response
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)


def _authenticated_partner():
    token = _get_token_from_request()
    if not token:
        return None
    return request.env['bim.portal.token'].sudo().validate_token(token)


def _project_payload(project):
    return {
        'id': project.id,
        'name': project.name,
        'nombre': project.nombre or '',
        'state': project.project_state or '',
        'balance': project.balance,
        'sale_total': project.sale_total_project_cost,
        'cost_total': project.total_project_cost,
        'profit': project.project_profit,
        'margin': project.project_margin,
        'budgeted_hours': project.budgeted_hours,
        'real_hours': project.real_hours,
        'currency': project.currency_id.symbol if project.currency_id else '€',
    }


class BimPortalProjectsController(http.Controller):

    @http.route('/bim_portal/projects', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_projects(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        projects = request.env['bim.project'].sudo().search(
            [('a_user_id', '=', partner.id)],
            order='id desc',
        )

        return _json_response({
            'success': True,
            'projects': [_project_payload(p) for p in projects],
        })

    @http.route('/bim_portal/projects/<int:project_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_project(self, project_id, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        project = request.env['bim.project'].sudo().search(
            [('id', '=', project_id), ('a_user_id', '=', partner.id)], limit=1
        )
        if not project:
            return _json_response({'success': False, 'error': 'Obra no encontrada.'}, status=404)

        return _json_response({'success': True, 'project': _project_payload(project)})
