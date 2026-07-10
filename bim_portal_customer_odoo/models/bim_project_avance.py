# -*- coding: utf-8 -*-
from odoo import fields, models


class BimProjectAvance(models.Model):
    _inherit = 'bim.project'

    avance_obra_ids = fields.One2many('bim.avance.obra', 'project_id', string='Avances de Obra')
    avance_obra_count = fields.Integer(
        string='Avances', compute='_compute_avance_obra_count')

    def _compute_avance_obra_count(self):
        for rec in self:
            rec.avance_obra_count = self.env['bim.avance.obra'].search_count(
                [('project_id', '=', rec.id)])

    def action_view_avances_obra(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Avances de Obra',
            'res_model': 'bim.avance.obra',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
