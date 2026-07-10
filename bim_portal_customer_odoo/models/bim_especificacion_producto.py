# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BimEspecificacionProducto(models.Model):
    _name = 'bim.especificacion.producto'
    _description = 'Especificación de Producto'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha desc, id desc'

    name = fields.Char(
        string='Referencia', required=True, copy=False, readonly=True,
        default=lambda self: _('Nuevo'), tracking=True)
    project_id = fields.Many2one(
        'bim.project', string='Proyecto', required=True,
        ondelete='restrict', tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario',
        default=lambda self: self.env.user, tracking=True)
    fecha = fields.Date(
        string='Fecha', required=True,
        default=fields.Date.today, tracking=True)
    state = fields.Selection([
        ('borrador',   'Borrador'),
        ('en_tramite', 'En Trámite'),
        ('cerrada',    'Cerrada'),
    ], string='Estado', default='borrador', required=True, tracking=True)
    product_id = fields.Many2one(
        'product.template', string='Producto', tracking=True)

    # Proveedores
    proveedor1_id = fields.Many2one(
        'res.partner', string='Proveedor 1', tracking=True)
    proveedor2_id = fields.Many2one(
        'res.partner', string='Proveedor 2', tracking=True)
    proveedor3_id = fields.Many2one(
        'res.partner', string='Proveedor 3', tracking=True)
    proveedor_adjudicado_id = fields.Many2one(
        'res.partner', string='Proveedor Adjudicado', tracking=True)

    notas = fields.Text(string='Notas')
    line_ids = fields.One2many(
        'bim.especificacion.producto.linea', 'especificacion_id',
        string='Características')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.especificacion.producto') or _('Nuevo')
        return super().create(vals_list)

    def action_en_tramite(self):
        self.filtered(lambda r: r.state == 'borrador').write({'state': 'en_tramite'})

    def action_cerrar(self):
        self.filtered(lambda r: r.state == 'en_tramite').write({'state': 'cerrada'})

    def action_borrador(self):
        self.filtered(lambda r: r.state in ('en_tramite', 'cerrada')).write({'state': 'borrador'})

    def action_print_report(self):
        return self.env.ref(
            'bim_portal_customer_odoo.action_report_bim_especificacion_producto'
        ).report_action(self)


class BimEspecificacionProductoLinea(models.Model):
    _name = 'bim.especificacion.producto.linea'
    _description = 'Línea de Especificación de Producto'
    _order = 'sequence, id'

    especificacion_id = fields.Many2one(
        'bim.especificacion.producto', string='Especificación',
        required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    caracteristica = fields.Char(string='Característica')
    propuesta1 = fields.Char(string='Propuesta 1')
    propuesta2 = fields.Char(string='Propuesta 2')
    propuesta3 = fields.Char(string='Propuesta 3')
