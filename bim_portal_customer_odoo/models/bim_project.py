# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class BimProject(models.Model):
    _inherit = 'bim.project'

    a_user_id = fields.Many2one(
        'res.partner', string='Supervisor (Portal)', tracking=True,
        default=False, ondelete='set null')
    a_project_user_id = fields.Many2one(
        'res.partner', string='Project Manager (Portal)', tracking=True,
        ondelete='set null')

    especificacion_count = fields.Integer(
        string='Especificaciones',
        compute='_compute_especificacion_count')

    def _compute_especificacion_count(self):
        data = self.env['bim.especificacion.producto'].read_group(
            [('project_id', 'in', self.ids)],
            ['project_id'], ['project_id'])
        mapping = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.especificacion_count = mapping.get(rec.id, 0)

    def action_view_especificaciones(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Especificaciones de Producto',
            'res_model': 'bim.especificacion.producto',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
