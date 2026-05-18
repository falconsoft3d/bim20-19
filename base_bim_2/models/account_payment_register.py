# -*- coding: utf-8 -*-
from odoo import api, fields, models

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    project_id = fields.Many2one('bim.project', 'Project',
                                  domain="[('company_id','=',company_id)]")

    budget_id = fields.Many2one('bim.budget', 'Budget')
    concept_id = fields.Many2one('bim.concepts', 'Concept')

    pay_wh_retention = fields.Boolean('Pago sin Retención', default=False)
    _wh_amount = fields.Float('WH Amount')


    @api.onchange('pay_wh_retention')
    def _onchange_pay_wh_retention(self):
        if self.pay_wh_retention:
            self.amount = self._wh_amount


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_ids'):
            move_line = self.env['account.move.line'].browse(self._context.get('active_ids')[0])
            move = move_line.move_id

            # calculo el monto quitando la retencion
            rsum = 0
            move_lines = self.env['account.move.line'].browse(self._context.get('active_ids'))
            array_invoice = []
            for l in move_lines:
                if l.move_id.id in array_invoice:
                    continue
                else:
                    array_invoice.append(l.move_id.id)
                    rsum += l.move_id.total_pay_retention


            if rsum < 0:
                rsum = rsum * -1

            va = {
                'project_id': move.project_id.id,
                '_wh_amount': rsum,
            }
            res.update(va)

        return res


    def _create_payments(self):
        res = super()._create_payments()
        for payment in res:
            payment.project_id = self.project_id.id
            payment.budget_id = self.budget_id.id
            payment.concept_id = self.concept_id.id

            if payment.concept_id:
                bim_cash_flow_id = self.env['bim.cash.flow'].search([('bim_concept_id', '=', payment.concept_id.id)], limit=1)
                if bim_cash_flow_id and payment.id not in bim_cash_flow_id.payments_ids.ids:
                    bim_cash_flow_id.payments_ids = [(4, payment.id)]
                    bim_cash_flow_id._onchange_payments_ids()
                    bim_cash_flow_id._compute_variation()
                    bim_cash_flow_id._compute_variation_signed()
        return res



