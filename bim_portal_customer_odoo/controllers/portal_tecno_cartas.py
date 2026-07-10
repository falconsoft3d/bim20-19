# -*- coding: utf-8 -*-
"""
Controlador REST para Tecno Cartas del Portal BIM.

Endpoints:
    GET /bim_portal/tecno_cartas  → Árbol de categorías con cartas anidadas
"""
import logging
import re
from odoo import http
from odoo.http import request
from .portal_auth import _json_response, _preflight, _get_token_from_request

_logger = logging.getLogger(__name__)

# Patrón para src/href relativos que apuntan a recursos Odoo
_RELATIVE_URL_RE = re.compile(r'(src|href)="(/[^"]+)"', re.IGNORECASE)


def _fix_odoo_urls(html: str) -> str:
    """Convierte URLs relativas de Odoo a absolutas para que el portal pueda cargarlas."""
    if not html:
        return html
    base = request.httprequest.host_url.rstrip('/')
    return _RELATIVE_URL_RE.sub(lambda m: f'{m.group(1)}="{base}{m.group(2)}"', html)


def _authenticated_partner():
    token = _get_token_from_request()
    if not token:
        return None
    return request.env['bim.portal.token'].sudo().validate_token(token)


def _build_category_tree(categories, parent_id=False):
    """Construye el árbol recursivamente."""
    nodes = []
    for cat in categories.filtered(lambda c: c.parent_id.id == parent_id):
        cartas = request.env['bim.tecno.carta'].sudo().search(
            [('categoria_id', '=', cat.id), ('active', '=', True)],
            order='titulo',
        )
        nodes.append({
            'id': cat.id,
            'name': cat.name,
            'children': _build_category_tree(categories, parent_id=cat.id),
            'cartas': [
                {'id': c.id, 'titulo': c.titulo, 'texto': _fix_odoo_urls(c.texto or '')}
                for c in cartas
            ],
        })
    return nodes


class BimPortalTecnoCartasController(http.Controller):

    @http.route('/bim_portal/tecno_cartas', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False)
    def get_tecno_cartas(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _preflight()

        partner = _authenticated_partner()
        if not partner:
            return _json_response({'success': False, 'error': 'No autenticado.'}, status=401)

        if not partner.portal_is_tecno_cartas:
            return _json_response({'success': False, 'error': 'Sin acceso a Tecno Cartas.'}, status=403)

        all_categories = request.env['bim.tecno.carta.categoria'].sudo().search([], order='name')
        tree = _build_category_tree(all_categories)

        return _json_response({'success': True, 'categories': tree})
