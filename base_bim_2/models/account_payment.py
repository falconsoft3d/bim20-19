# -*- coding: utf-8 -*-
from odoo import api, fields, models

class BimAccountPayment(models.Model):
    _inherit = "account.payment"

    project_id = fields.Many2one('bim.project', 'Project', tracking=True, domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict")


    def action_post(self):
        res = super(BimAccountPayment, self).action_post()

        for payment in self:
            # Pago de Proveedores
            if payment.payment_type == 'outbound':
                if payment.project_id and payment.budget_id and payment.concept_id:
                    bim_cash_flow_id = self.env['bim.cash.flow'].search([
                                                                             ('bim_project_id', '=', payment.project_id.id),
                                                                             ('bim_budget_id', '=', payment.budget_id.id),
                                                                             ('bim_concept_id', '=', payment.concept_id.id),
                                                                             ('type', '=', 'expense'),
                                                                             ('currency_id', '=', payment.currency_id.id),
                                                                         ], limit=1)


                    if bim_cash_flow_id:
                        if not payment.id in bim_cash_flow_id.payments_ids.ids:
                            bim_cash_flow_id.payments_ids = [(4, payment.id)]
                            bim_cash_flow_id._onchange_payments_ids()

            else:
                if payment.project_id and payment.partner_id:
                    bim_cash_flow_id = payment.env['bim.cash.flow'].search([
                                                                             ('bim_project_id', '=', payment.project_id.id),
                                                                             ('type', '=', 'income'),
                                                                             ('contact_id', '=', payment.partner_id.id),
                                                                             ('currency_id', '=', payment.currency_id.id),
                                                                         ], limit=1)
                    if bim_cash_flow_id:
                        if not payment.id in bim_cash_flow_id.payments_ids.ids:
                            bim_cash_flow_id.payments_ids = [(4, payment.id)]
                            bim_cash_flow_id._onchange_payments_ids()
        return res
