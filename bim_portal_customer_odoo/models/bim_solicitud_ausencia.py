# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BimSolicitudAusencia(models.Model):
    _name = 'bim.solicitud.ausencia'
    _description = 'Solicitud de Ausencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_create desc, id desc'

    name = fields.Char(
        string='Referencia', required=True, copy=False, readonly=True,
        default=lambda self: _('Nuevo'))
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Enviada'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ], string='Estado', default='draft', required=True, tracking=True)
    date_create = fields.Datetime(
        string='Fecha de Creación', default=fields.Datetime.now, readonly=True)
    date_from = fields.Date(string='Fecha Desde', required=True)
    date_to = fields.Date(string='Fecha Hasta', required=True)
    tipo = fields.Selection([
        ('vacaciones', 'Vacaciones'),
        ('permiso', 'Permiso'),
        ('otros', 'Otros'),
    ], string='Tipo', required=True, default='vacaciones', tracking=True)
    descripcion = fields.Text(string='Descripción / Aclaración')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.solicitud.ausencia') or _('Nuevo')
        return super().create(vals_list)

    def action_submit(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'submitted'})

    def action_approve(self):
        self.filtered(lambda r: r.state in ('draft', 'submitted')).write({'state': 'approved'})

    def action_reject(self):
        self.filtered(lambda r: r.state in ('draft', 'submitted')).write({'state': 'rejected'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state in ('rejected',)).write({'state': 'draft'})
