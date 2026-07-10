# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveBimPortal(models.Model):
    """Extiende account.move para añadir campos del portal BIM."""
    _inherit = 'account.move'

    bim_project_id = fields.Many2one(
        'bim.project', string='Proyecto BIM',
        ondelete='restrict', tracking=True)
    bim_submitted_by = fields.Many2one(
        'res.partner', string='Enviado por (Portal)',
        readonly=True, tracking=True)
    bim_importe = fields.Float(
        'Importe referencia', digits=(16, 2),
        help='Importe indicado por el empleado al subir la factura')
    bim_notas = fields.Text('Notas portal')
    bim_portal_state = fields.Selection([
        ('submitted', 'Enviada'),
        ('approved',  'Aprobada'),
        ('rejected',  'Rechazada'),
    ], string='Estado Portal', tracking=True)

    def bim_action_approve(self):
        self.write({'bim_portal_state': 'approved'})
        for move in self.filtered(lambda m: m.state == 'draft'):
            try:
                move.action_post()
            except Exception:
                pass

    def bim_action_reject(self):
        self.write({'bim_portal_state': 'rejected'})
        for move in self.filtered(lambda m: m.state == 'draft'):
            try:
                move.button_cancel()
            except Exception:
                pass
