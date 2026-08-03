# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BimPaymentSchedule(models.Model):
    _name = 'bim.payment.schedule'
    _description = 'Programación de Pagos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_prevista, id'

    name = fields.Char('Secuencia', default='New', copy=False)
    purchase_id = fields.Many2one(
        'purchase.order', 'Orden de Compra',
        required=True, ondelete='cascade', index=True)
    fecha_prevista = fields.Date(
        'Fecha Prevista', default=fields.Date.context_today, tracking=True)
    fecha_real = fields.Date('Fecha Real', tracking=True)
    importe_a_pagar = fields.Monetary('Importe a Pagar', currency_field='currency_id', tracking=True)
    como_se_paga = fields.Selection([
        ('transferencia', 'Transferencia'),
        ('efectivo', 'Efectivo'),
    ], string='Cómo se Paga', tracking=True)
    notas = fields.Text('Notas')
    aprobado_tecnico = fields.Boolean('Aprobado Técnicamente', tracking=True, groups='base_bim_2.group_purchase_technical_approver')
    aprobado_finanzas = fields.Boolean('Aprobado para Pagos', tracking=True, groups='base_bim_2.group_purchase_finance_approver')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('planned', 'Planificada'),
        ('approved', 'Aprobada'),
        ('done', 'Hecho'),
    ], string='Estado', default='draft', tracking=True, copy=False)
    company_id = fields.Many2one(
        'res.company', 'Empresa', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='purchase_id.currency_id', store=True)
    partner_id = fields.Many2one(
        'res.partner', related='purchase_id.partner_id', store=True, string='Proveedor')
    project_id = fields.Many2one(
        'bim.project', related='purchase_id.project_id', store=True, string='Proyecto')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        purchase_id = values.get('purchase_id') or self.env.context.get('default_purchase_id')
        if purchase_id and 'importe_a_pagar' in fields_list:
            purchase = self.env['purchase.order'].browse(purchase_id)
            values['importe_a_pagar'] = purchase.amount_pending
        return values

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.payment.schedule') or 'New'
        return super().create(vals_list)

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_planned(self):
        self.write({'state': 'planned'})

    def action_approve(self):
        for rec in self:
            if not rec.aprobado_tecnico or not rec.aprobado_finanzas:
                raise ValidationError(
                    _('Debe marcar Aprobado Técnicamente y Aprobado para Pagos para poder aprobar.'))
        self.write({'state': 'approved'})

    def action_done(self):
        self.write({'state': 'done'})
