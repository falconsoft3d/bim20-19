# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import secrets
import string


class ResPartner(models.Model):
    _inherit = 'res.partner'

    portal_bim_active = fields.Boolean(
        string='Portal BIM Activo',
        default=False,
        help='Indica si el contacto tiene acceso al Portal BIM'
    )
    portal_bim_login = fields.Char(
        string='Login Portal BIM',
        help='Login para acceder al Portal BIM',
        copy=False
    )
    portal_bim_password = fields.Char(
        string='Contraseña Portal BIM',
        help='Contraseña generada para el Portal BIM',
        copy=False
    )

    def _generate_password(self):
        """Genera una contraseña aleatoria segura"""
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        password = ''.join(secrets.choice(alphabet) for i in range(12))
        return password

    def action_activate_portal_bim(self):
        """Activa el portal BIM para el contacto"""
        self.ensure_one()
        
        if self.portal_bim_active:
            raise UserError(_('El Portal BIM ya está activo para este contacto.'))
        
        # Determinar el login
        if not self.portal_bim_login:
            if self.vat:
                login = self.vat
            elif self.email:
                login = self.email
            else:
                raise UserError(_('El contacto debe tener un VAT o un correo electrónico para activar el Portal BIM.'))
            self.portal_bim_login = login
        
        # Generar contraseña si no existe
        if not self.portal_bim_password:
            self.portal_bim_password = self._generate_password()
        
        # Activar el portal
        self.portal_bim_active = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal BIM Activado'),
                'message': _('Credenciales generadas - Login: %s | Contraseña: %s') % (self.portal_bim_login, self.portal_bim_password),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_deactivate_portal_bim(self):
        """Desactiva el portal BIM para el contacto"""
        self.ensure_one()
        
        if not self.portal_bim_active:
            raise UserError(_('El Portal BIM no está activo para este contacto.'))
        
        self.portal_bim_active = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal BIM Desactivado'),
                'message': _('El acceso al Portal BIM ha sido desactivado.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_regenerate_password(self):
        """Regenera la contraseña del portal BIM"""
        self.ensure_one()
        
        if not self.portal_bim_active:
            raise UserError(_('Debe activar el Portal BIM primero.'))
        
        new_password = self._generate_password()
        self.portal_bim_password = new_password
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contraseña Regenerada'),
                'message': _('Nueva contraseña: %s') % new_password,
                'type': 'success',
                'sticky': True,
            }
        }


