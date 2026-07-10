# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BimAvanceObra(models.Model):
    _name = 'bim.avance.obra'
    _description = 'Avance de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha desc, id desc'

    name = fields.Char(
        string='Secuencia', required=True, copy=False, readonly=True,
        default=lambda self: _('Nuevo'))
    fecha = fields.Date(string='Fecha', required=True, default=fields.Date.today)
    user_id = fields.Many2one('res.users', string='Usuario',
                              default=lambda self: self.env.user, required=True)
    project_id = fields.Many2one('bim.project', string='Proyecto',
                                 ondelete='cascade', required=True, index=True)
    descripcion = fields.Text(string='Descripción')
    line_ids = fields.One2many('bim.avance.obra.linea', 'avance_id', string='Imágenes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.avance.obra') or _('Nuevo')
        return super().create(vals_list)


class BimAvanceObraLinea(models.Model):
    _name = 'bim.avance.obra.linea'
    _description = 'Línea de Avance de Obra'
    _order = 'sequence, id'

    avance_id = fields.Many2one('bim.avance.obra', string='Avance',
                                ondelete='cascade', required=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Descripción')
    image = fields.Image(string='Imagen', max_width=1920, max_height=1920)
