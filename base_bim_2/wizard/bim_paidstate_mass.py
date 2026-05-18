# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests


class BimPaidstateMass(models.TransientModel):
    _name = 'bim.paidstate.mass'
    _description = 'Bim Paidstate Mass'

    def _get_default_bim_paidstate(self):
        ids = self.env.context.get('active_ids', [])
        paidstates = self.env['bim.paidstate'].browse(ids).ids or []
        return paidstates

    paidstates_ids = fields.Many2many('bim.paidstate', string='Paidstate',
                                    default=_get_default_bim_paidstate)

    def action_done(self):
        if len(self.paidstates_ids) < 2:
            raise ValidationError(_('You must select at least two records'))

        for paidstate in self.paidstates_ids:
            if paidstate.state != 'validated':
                raise ValidationError(_('You can only select records in validated state'))

        record = self.paidstates_ids[0]

        analytic_id = record.object_id.analytic_id.id if record.object_id.analytic_id else record.project_id.analytic_id.id and record.project_id.analytic_id.id or False

        if record.project_id.paidstate_product:
            product = record.project_id.paidstate_product
        else:
            product = self.env.user.company_id.paidstate_product

        if record.project_id.retention_product:
            retention_product = record.project_id.retention_product
        else:
            retention_product = self.env.user.company_id.retention_product

        journal = self.env.user.company_id.journal_id.id
        if not journal:
            raise ValidationError(_('You have not set up a Sales Journal'))

        income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        retention_account = retention_product.property_account_income_id or retention_product.categ_id.property_account_income_categ_id
        if not retention_account:
            raise ValidationError(_('There is no income account in the withholding product or in its category.'))
        if not income_account:
            raise ValidationError(_('There is no income account in the product or in its category'))

        company_id = self.env.user.company_id

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': record.project_id.invoice_address_id.id if record.project_id.invoice_address_id else record.project_id.customer_id.id,
            'partner_shipping_id': record.project_id.customer_id.id,
            'journal_id': journal,
            'currency_id': company_id.currency_id.id,
            'invoice_date': record.date,
            'invoice_user_id': self.env.user.id,
            'invoice_line_ids': [],
            'narration': record.paidstate_notes,
            'include_for_bim': company_id.bim_include_invoice_sale,
        }

        for paidstate in self.paidstates_ids:
            vals = {
                'name': '%s - %s' % (record.name, paidstate.project_id.nombre[0:40]),
                'sequence': 1,
                'account_id': income_account.id,
                'price_unit': paidstate.amount,
                'quantity': 1,
                'product_uom_id': product.uom_id.id,
                'product_id': product.id,
                'tax_ids': [(6, 0, product.taxes_id.ids)],
            }
            analytic_id = paidstate.project_id.analytic_id.id
            if analytic_id:
                vals.update({
                    'analytic_distribution': {'%s' % (analytic_id): 100}
                })
            invoice_vals['invoice_line_ids'].append(
                (0, 0, vals))

        invoice_obj = self.env['account.move']
        invoice = invoice_obj.create(invoice_vals)
        record.invoice_id = invoice.id

        for paidstate in self.paidstates_ids:
            paidstate.invoice_id = invoice.id
            paidstate.state = 'invoiced'

        # Open invoice
        action = self.env.ref('account.action_move_out_invoice_type')
        result = action.read()[0]
        result['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
        result['res_id'] = invoice.id
        return result
