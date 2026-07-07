# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from werkzeug.security import generate_password_hash, check_password_hash


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Campos del Portal ──────────────────────────────────────────────────

    portal_login = fields.Char(
        string='Login Portal',
        copy=False,
        help='Nombre de usuario para acceder al Portal de Clientes BIM.',
    )
    portal_active = fields.Boolean(
        string='Acceso Activo',
        default=False,
        help='Activa o desactiva el acceso de este contacto al portal.',
    )
    portal_responsible_id = fields.Many2one(
        comodel_name='res.partner',
        string='Responsable Portal',
        domain=[('is_company', '=', False)],
        help='Persona responsable de gestionar el acceso de este contacto.',
    )
    portal_password_hash = fields.Char(
        string='Contraseña Portal (hash)',
        copy=False,
        groups='base.group_system',
        help='Contraseña almacenada con hash bcrypt. Nunca almacenes texto plano.',
    )
    portal_password_set = fields.Boolean(
        string='Contraseña configurada',
        compute='_compute_portal_password_set',
        store=False,
    )
    portal_is_customer = fields.Boolean(
        string='Es Cliente',
        default=False,
        help='Este usuario puede acceder como cliente en el portal.',
    )
    portal_is_employee = fields.Boolean(
        string='Es Empleado',
        default=False,
        help='Este usuario puede acceder como empleado en el portal.',
    )
    portal_is_admin = fields.Boolean(
        string='Es Administrador',
        default=False,
        help='Este usuario tiene permisos de administrador en el portal.',
    )
    portal_is_tecno_cartas = fields.Boolean(
        string='Tecno Cartas',
        default=False,
        help='Este usuario tiene acceso al módulo Tecno Cartas en el portal.',
    )
    portal_is_proveedor = fields.Boolean(
        string='Es Proveedor',
        default=False,
        help='Este usuario accede al portal como proveedor.',
    )

    # ── Computes ───────────────────────────────────────────────────────────

    @api.depends('portal_password_hash')
    def _compute_portal_password_set(self):
        for partner in self:
            partner.portal_password_set = bool(partner.portal_password_hash)

    # ── Constrains ────────────────────────────────────────────────────────

    @api.constrains('portal_login')
    def _check_portal_login_unique(self):
        for partner in self:
            if not partner.portal_login:
                continue
            domain = [
                ('portal_login', '=', partner.portal_login),
                ('id', '!=', partner.id),
            ]
            if self.search_count(domain):
                raise UserError(
                    _('El login "%s" ya está en uso por otro contacto.') % partner.portal_login
                )

    # ── Métodos públicos ───────────────────────────────────────────────────

    def action_open_portal_password_wizard(self):
        """Abre el wizard para establecer/cambiar la contraseña del portal."""
        self.ensure_one()
        if not self.portal_login:
            raise UserError(_('Debes definir un Login Portal antes de establecer la contraseña.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Establecer Contraseña Portal'),
            'res_model': 'bim.portal.password.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_partner_login': self.portal_login,
            },
        }

    def portal_verify_password(self, raw_password: str) -> bool:
        """Verifica si raw_password coincide con el hash almacenado."""
        self.ensure_one()
        if not self.portal_password_hash or not self.portal_active:
            return False
        return check_password_hash(self.portal_password_hash, raw_password)

    def portal_set_password(self, raw_password: str) -> None:
        """Almacena la contraseña encriptada (bcrypt via werkzeug)."""
        self.ensure_one()
        self.sudo().portal_password_hash = generate_password_hash(
            raw_password, method='pbkdf2:sha256:600000'
        )
