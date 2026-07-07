# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _generate_secure_password(length: int = 16) -> str:
    """Genera una contraseña segura con mayúsculas, minúsculas, dígitos y símbolos."""
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*()-_=+'
    # Garantiza al menos un carácter de cada tipo
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*()-_=+'),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


class BimPortalPasswordWizard(models.TransientModel):
    _name = 'bim.portal.password.wizard'
    _description = 'Wizard - Establecer Contraseña Portal BIM'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        required=True,
        readonly=True,
    )
    partner_login = fields.Char(
        string='Login',
        readonly=True,
    )
    new_password = fields.Char(
        string='Nueva contraseña',
        required=True,
    )
    confirm_password = fields.Char(
        string='Confirmar contraseña',
        required=True,
    )
    password_strength = fields.Selection(
        selection=[
            ('weak', 'Débil'),
            ('medium', 'Media'),
            ('strong', 'Fuerte'),
        ],
        string='Seguridad',
        compute='_compute_password_strength',
    )

    # ── Computes ───────────────────────────────────────────────────────────

    @api.depends('new_password')
    def _compute_password_strength(self):
        for wizard in self:
            pwd = wizard.new_password or ''
            score = 0
            if len(pwd) >= 8:
                score += 1
            if len(pwd) >= 12:
                score += 1
            if any(c.isupper() for c in pwd):
                score += 1
            if any(c.islower() for c in pwd):
                score += 1
            if any(c.isdigit() for c in pwd):
                score += 1
            if any(c in '!@#$%^&*()-_=+' for c in pwd):
                score += 1
            if score <= 2:
                wizard.password_strength = 'weak'
            elif score <= 4:
                wizard.password_strength = 'medium'
            else:
                wizard.password_strength = 'strong'

    # ── Acciones ───────────────────────────────────────────────────────────

    def action_generate_password(self):
        """Genera una contraseña segura y la coloca en los campos."""
        password = _generate_secure_password(length=16)
        self.new_password = password
        self.confirm_password = password
        self.show_password = True
        # Retorna el mismo wizard para que el usuario vea la nueva contraseña
        return {
            'type': 'ir.actions.act_window',
            'name': _('Establecer Contraseña Portal'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_set_password(self):
        """Valida y almacena la contraseña encriptada en el partner."""
        self.ensure_one()
        if not self.new_password:
            raise UserError(_('La contraseña no puede estar vacía.'))
        if self.new_password != self.confirm_password:
            raise ValidationError(_('Las contraseñas no coinciden.'))
        if len(self.new_password) < 8:
            raise ValidationError(_('La contraseña debe tener al menos 8 caracteres.'))
        if self.password_strength == 'weak':
            raise ValidationError(
                _('La contraseña es demasiado débil. Usa mayúsculas, minúsculas, números y símbolos.')
            )

        self.partner_id.portal_set_password(self.new_password)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contraseña actualizada'),
                'message': _('La contraseña del portal ha sido establecida correctamente.'),
                'type': 'success',
                'sticky': False,
            },
        }
