# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
"""
Modelo para tokens de sesión del portal.
Permite invalidar sesiones activas sin depender de JWT puro.
"""
import secrets
from datetime import datetime, timedelta
from odoo import api, fields, models


class BimPortalToken(models.Model):
    _name = 'bim.portal.token'
    _description = 'BIM Portal Session Token'
    _order = 'create_date desc'
    _rec_name = 'token'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        required=True,
        ondelete='cascade',
        index=True,
    )
    token = fields.Char(
        string='Token',
        required=True,
        copy=False,
        index=True,
        default=lambda self: secrets.token_urlsafe(48),
    )
    expiration = fields.Datetime(
        string='Expira el',
        required=True,
        default=lambda self: datetime.now() + timedelta(hours=8),
    )
    active = fields.Boolean(default=True)

    # ── Métodos ────────────────────────────────────────────────────────────

    @api.model
    def create_token(self, partner_id: int, hours: int = 8) -> str:
        """Crea un nuevo token para el partner e invalida los anteriores."""
        # Invalidar tokens previos del mismo partner
        self.sudo().search([('partner_id', '=', partner_id), ('active', '=', True)]).write(
            {'active': False}
        )
        token_rec = self.sudo().create({
            'partner_id': partner_id,
            'expiration': datetime.now() + timedelta(hours=hours),
        })
        return token_rec.token

    @api.model
    def validate_token(self, token: str):
        """
        Devuelve el partner_id si el token es válido y no ha expirado.
        Retorna None si no es válido.
        """
        rec = self.sudo().search([
            ('token', '=', token),
            ('active', '=', True),
            ('expiration', '>=', fields.Datetime.now()),
        ], limit=1)
        if rec:
            return rec.partner_id
        return None

    @api.model
    def revoke_token(self, token: str) -> bool:
        """Invalida un token (logout)."""
        rec = self.sudo().search([('token', '=', token), ('active', '=', True)], limit=1)
        if rec:
            rec.active = False
            return True
        return False

    @api.model
    def cleanup_expired(self):
        """Cron: elimina tokens expirados."""
        expired = self.sudo().search([
            ('expiration', '<', fields.Datetime.now()),
        ])
        expired.unlink()
