# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class PurchasePaymentScheduleWizard(models.TransientModel):
    _name = 'purchase.payment.schedule.wizard'
    _description = 'Propuesta de programación de pagos de compra'

    purchase_id = fields.Many2one(
        'purchase.order', string='Orden de compra', required=True, readonly=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Condición de pago', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='purchase_id.currency_id', readonly=True)
    line_ids = fields.One2many(
        'purchase.payment.schedule.wizard.line', 'wizard_id', string='Pagos propuestos')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        purchase = self.env['purchase.order'].browse(
            self.env.context.get('active_id'))
        if not purchase or purchase.state != 'purchase':
            raise UserError(_('La orden de compra debe estar confirmada.'))
        payment_term = purchase.partner_id.property_supplier_payment_term_id or purchase.payment_term_id
        if not payment_term:
            raise UserError(_('El proveedor no tiene una condición de pago configurada.'))
        if purchase.payment_schedule_ids:
            raise UserError(_(
                'La orden ya tiene una programación de pagos. Edítela desde el botón "Prog. Pagos".'))

        reference_date = fields.Date.to_date(purchase.date_order) or fields.Date.context_today(purchase)
        terms = payment_term._compute_terms(
            date_ref=reference_date,
            currency=purchase.currency_id,
            company=purchase.company_id,
            tax_amount=purchase.amount_tax,
            tax_amount_currency=purchase.amount_tax,
            untaxed_amount=purchase.amount_untaxed,
            untaxed_amount_currency=purchase.amount_untaxed,
            sign=1,
        )
        line_ids = []
        for term in terms['line_ids']:
            amount = term['foreign_amount']
            percentage = (amount / purchase.amount_total * 100.0) if purchase.amount_total else 0.0
            line_ids.append((0, 0, {
                'fecha_prevista': term['date'],
                'percentage': percentage,
                'amount': amount,
            }))
        values.update({
            'purchase_id': purchase.id,
            'payment_term_id': payment_term.id,
            'line_ids': line_ids,
        })
        return values

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError(_('Debe indicar al menos un pago.'))
        total_percentage = sum(self.line_ids.mapped('percentage'))
        if float_compare(total_percentage, 100.0, precision_digits=2) != 0:
            raise ValidationError(_('El total de los porcentajes debe ser 100%.'))
        if any(line.percentage <= 0 for line in self.line_ids):
            raise ValidationError(_('Cada porcentaje debe ser mayor que cero.'))

        payment_schedules = self.env['bim.payment.schedule']
        pending_amount = self.purchase_id.amount_total
        for index, line in enumerate(self.line_ids):
            amount = pending_amount if index == len(self.line_ids) - 1 else self.purchase_id.currency_id.round(
                self.purchase_id.amount_total * line.percentage / 100.0)
            payment_schedules |= payment_schedules.create({
                'purchase_id': self.purchase_id.id,
                'fecha_prevista': line.fecha_prevista,
                'importe_a_pagar': amount,
            })
            pending_amount -= amount
        return self.purchase_id.action_view_payment_schedule()


class PurchasePaymentScheduleWizardLine(models.TransientModel):
    _name = 'purchase.payment.schedule.wizard.line'
    _description = 'Línea de propuesta de programación de pagos de compra'

    wizard_id = fields.Many2one(
        'purchase.payment.schedule.wizard', required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', related='wizard_id.currency_id', readonly=True)
    fecha_prevista = fields.Date('Fecha prevista', required=True)
    percentage = fields.Float('Porcentaje', required=True, digits=(16, 2))
    amount = fields.Monetary('Importe', currency_field='currency_id', readonly=True)

    @api.onchange('percentage')
    def _onchange_percentage(self):
        for line in self:
            line.amount = line.wizard_id.purchase_id.amount_total * line.percentage / 100.0