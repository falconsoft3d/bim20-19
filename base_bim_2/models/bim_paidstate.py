# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class BimPaidstate(models.Model):
    _description = "Payment Status"
    _name = 'bim.paidstate'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    user_id = fields.Many2one('res.users', string='Responsible', tracking=True, default=lambda self: self.env.user)
    name = fields.Char('Name', required=True, copy=False,
        readonly=True, index=True, default=lambda self: 'New')
    project_id = fields.Many2one('bim.project', 'Project',
        required=True, domain="[('company_id','=',company_id)]",
        change_default=True, index=True, ondelete="restrict")
    amount = fields.Monetary('Amount', compute='_amount_compute')
    amount_total = fields.Monetary('Amount Total', compute='_amount_compute_total')
    progress = fields.Float('% Advance', help="Advance percentage", compute='compute_progress', digits=(10, 2))
    date = fields.Date(string='Date', required=True,
        readonly=True, index=True,
        copy=False, default=fields.Datetime.now)
    currency_id = fields.Many2one('res.currency', string='Currency',
        required=True, default=lambda r: r.env.user.company_id.currency_id,
        tracking=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, ondelete='restrict')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    lines_ids = fields.One2many('bim.paidstate.line', 'paidstate_id', string='Lines')
    object_lines_ids = fields.One2many('bim.paidstate.object.line', 'paidstate_id', string='Object Lines')
    state = fields.Selection(
        [('draft', 'Draft'),
         ('validated', 'Validated'),
         ('invoiced', 'Invoiced'),
         ('cancel', 'Canceled')],
        'Status', readonly=True, copy=False,
        index=True, tracking=True, default='draft')
    apply_retention = fields.Boolean(string='Apply retention', default=True)
    paidstate_retention = fields.Float(string='Warranty Retention', compute='compute_retention', store=True)
    paidstate_company_retention = fields.Float(string='% Project Retention', related='project_id.retention')
    paidstate_notes = fields.Text(default="")
    type = fields.Selection([('manual','Manual'),('certification','By Certification')], default='manual', required=True)
    invoice_debit_credit = fields.Boolean(default=lambda self: self.env.company.invoice_debit_credit)
    certification_ids = fields.Many2many('bim.massive.certification.by.line')
    chapter_certification_ids = fields.Many2many('bim.massive.chapter.certification')
    load_certifications = fields.Boolean(default=True)
    budget_ids = fields.Many2many('bim.budget', compute="_compute_budget_ids", store=True)
    object_id = fields.Many2one('bim.object', string='Object', ondelete='restrict', domain="[('project_id','=',project_id)]")

    type_invoice = fields.Selection([
        ('out_invoice', 'Sale'),
        ('in_invoice', 'Purchase')
    ], string="Type Invoice",
        default='out_invoice')

    indicator_a = fields.Float(string='Indicator A', default=1)
    indicator_b = fields.Float(string='Indicator B', default=1)
    bim_certification_index_id = fields.Many2one('certification.index', string='Certification Index')


    def update_certification(self):
        for c in self.certification_ids:
            if not c.paid_state_id:
                c.paid_state_id = self.id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.object_id = self.env['bim.object'].search([('project_id','=',self.project_id.id)], limit=1)

    @api.onchange('bim_certification_index_id')
    def _onchange_certification_index(self):
        if self.bim_certification_index_id:
            self.indicator_a = self.bim_certification_index_id.value

    def action_back_to_draft(self):
        self.write({'state': 'draft'})

    @api.depends('lines_ids','lines_ids.budget_id')
    def _compute_budget_ids(self):
        for paid in self:
            paid.budget_ids = paid.lines_ids.mapped('budget_id.id') or []
            if paid.load_certifications:
                paid.compute_certification_relation()
                paid.compute_chapter_certification_relation()

    def compute_certification_relation(self):
        paid = self
        new_certifications = paid.certification_ids.search([('budget_id','in',paid.budget_ids.ids),('state','=','done'),('paid_state_id','=',False)])
        if new_certifications:
            paid.certification_ids += new_certifications
        for certification in paid.certification_ids:
            if certification.budget_id in paid.budget_ids and not certification.paid_state_id:
                certification.paid_state_id = paid.id
            elif certification.budget_id not in paid.budget_ids:
                certification.paid_state_id = False
                paid.certification_ids = [(3, certification.id)]

    def compute_chapter_certification_relation(self):
        paid = self
        new_certifications = paid.chapter_certification_ids.search([('budget_id','in',paid.budget_ids.ids),('state','=','done'),('paid_state_id','=',False)])
        if new_certifications:
            paid.chapter_certification_ids += new_certifications
        for certification in paid.chapter_certification_ids:
            if certification.budget_id in paid.budget_ids and not certification.paid_state_id:
                certification.paid_state_id = paid.id
            elif certification.budget_id not in paid.budget_ids:
                certification.paid_state_id = False
                paid.chapter_certification_ids = [(3, certification.id)]

    def action_paid_state_cancel(self):
        if self.state != 'invoiced':
            self.state = 'cancel'
            self.unrelated_paid_state_with_certification()
        if self.state == 'invoiced':
            if self.invoice_id.state == 'cancel':
                self.state = 'cancel'
                self.unrelated_paid_state_with_certification()
            else:
                action = self.env.ref('base_bim_2.bim_paidstate_wizard_cancel_action').sudo().read()[0]
                return action

    def unrelated_paid_state_with_certification(self):
        for certification in self.certification_ids:
            certification.paid_state_id = False
        for chapter_cert in self.chapter_certification_ids:
            chapter_cert.paid_state_id = False
        for line in self.lines_ids:
            line.is_loaded = False
            line.budget_id.compute_balance_certified_residual()

    @api.depends('amount')
    def compute_progress(self):
        for record in self:
            if record.type == 'manual':
                record.progress = 0
            else:
                paidstate_ids = self.env['bim.paidstate'].search([('project_id','=',record.project_id.id)])
                amount_total = 0
                for paidstate in paidstate_ids:
                    amount_total += paidstate.amount
                record.progress = amount_total / record.project_id.balance * 100 if record.project_id.balance > 0 else 0

    @api.depends('lines_ids')
    def compute_retention(self):
        for record in self:
            if record.apply_retention:
                record.paidstate_retention = -0.01 * record.amount * record.project_id.retention
            else:
                record.paidstate_retention


    @api.depends('lines_ids','object_lines_ids')
    def _amount_compute(self):
        for record in self:
            record.amount = sum(line.amount for line in record.lines_ids) + sum(line.amount for line in record.object_lines_ids)

    @api.depends('lines_ids','object_lines_ids')
    def _amount_compute_total(self):
        for record in self:
            record.amount_total = sum(line.amount_total for line in record.lines_ids) + sum(line.amount for line in record.object_lines_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.paidstate') or 'New'
        return super().create(vals_list)

    def action_validate(self):
        if self.certification_ids:
            for certification in self.certification_ids:
                certification.paid_state_id = self.id

        if not self.lines_ids and not self.object_lines_ids:
            raise UserError(_("There are not lines to Validate"))
        self.write({'state': 'validated'})

    def unlink(self):
        if self.state == 'invoiced':
            raise UserError(_("It is not possible to delete Invoiced Paid State Record"))
        for record in self:
            for line in record.lines_ids:
                line.is_loaded = False
                # line.budget_idcompute_balance_certified_residual()
        return super().unlink()

    def action_invoice(self):
        record = self
        _logger.info('== Begin action_invoice ==')
        company_id = record.company_id

        invoice_obj = self.env['account.move']
        bim_general_config_obj = self.env['bim.general.config']
        bim_general_config_id = bim_general_config_obj.search([('key', '=', 'retention')], limit=1)

        _logger.info('== A ==')
        if bim_general_config_id:
            retention = bim_general_config_id.value
        else:
            retention = 'invoice_line'

        _logger.info('== B ==')

        analytic_id = record.object_id.analytic_id.id if record.object_id.analytic_id else record.project_id.analytic_id.id and record.project_id.analytic_id.id or False
        #Si el estado de pago proviene de un mantenimiento entonces toma el Product configurado en Ajustes para mantenimiento
        _logger.info('== C ==')


        if not company_id.paidstate_product:
            raise UserError(_('Define a product to invoice the Payment Status directly at the Work. You can also enter BIM / Configuration / Settings and configure a default one'))

        product = company_id.paidstate_product
        _logger.info(">>>> Product >>>>")
        _logger.info(product.name)

        _logger.info('== D ==')
        if record.project_id.retention_product:
            retention_product = record.project_id.retention_product
        else:
            retention_product = company_id.retention_product


        _logger.info('== E ==')
        if not record.project_id.customer_id:
            raise UserError(_('A client must be added to the project before invoicing.'))
        if not product:
            raise UserError(_('Define a product to invoice the Payment Status directly at the Work. You can also enter BIM / Configuration / Settings and configure a default one'))
        if not retention_product:
            raise UserError(_(
                'Define a product to invoice the withholding in the Payment Statements directly in the Work. You can also enter BIM / Configuration / Settings and configure a default one'))



        _logger.info('== F ==')
        _logger.info(self.type_invoice)
        _logger.info(product.property_account_income_id)


        if self.type_invoice == 'in_invoice':
            # Compra
            income_account = product.property_account_expense_id
        else:
            # Venta
            """
            Empresas incompatibles con los registros:
            - '/ EPA00080 - HOTEL EN MARINA D,OR' le pertenece a 'SOLTEC' y 'Cuenta' (account_id: '700000 Ventas de mercaderías en España') pertenece a otra compañía.
            """
            # property_account_income_id para la compañía 'SOLTEC'
            income_account = product.property_account_income_id

        if not income_account:
            raise UserError(_('There is no income account in the product or in its category'))

        _logger.info('===product===')
        _logger.info(product.name)

        _logger.info('b===income_account===')
        _logger.info(income_account.code)
        _logger.info(income_account.name)
        _logger.info('e===income_account===')



        _logger.info('== G ==')
        retention_account = retention_product.property_account_income_id or retention_product.categ_id.property_account_income_categ_id

        _logger.info('== A - income_account ==')
        _logger.info(income_account.name)

        _logger.info('== B - retention_account ==')
        _logger.info(retention_account.name)

        _logger.info('== H ==')
        if not retention_account:
            raise UserError(_('There is no income account in the withholding product or in its category.'))


        _logger.info('== I ==')
        if self.type_invoice == 'out_invoice':
            journal = company_id.journal_id.id
        else:
            journal = self.env['account.journal'].search([
                ('type', '=', 'purchase'),
                ('company_id', '=', company_id.id)
            ], limit=1).id

        if not journal:
            raise UserError(_('You have not set up a Sales Journal'))

        invoice_payment_term_id = record.project_id.customer_payment_mode_id.id if record.project_id.customer_payment_mode_id else False

        if not invoice_payment_term_id:
            invoice_payment_term_id = record.project_id.customer_id.property_payment_term_id.id if record.project_id.customer_id.property_payment_term_id else False


        certification_id = self.env['bim.massive.certification.by.line'].search([
                                    ('paid_state_id','=',record.id)
                                    ], limit=1)

        _logger.info('certification_id')
        _logger.info(certification_id)

        bim_paidstate_ids = self.env['bim.paidstate'].search([
                ('project_id','=',record.project_id.id),
            ])

        _logger.info('bim_paidstate_ids')
        _logger.info(bim_paidstate_ids)

        certification_now_origin = 0
        certification_now_last = 0

        try:
            for paidstate in bim_paidstate_ids:
                first_budget = self.lines_ids[0].budget_id
                _logger.info('first_budget')
                _logger.info(first_budget)

                for line in paidstate.lines_ids:
                    if first_budget == line.budget_id:
                        certification_now_origin += line.amount_total

                        if paidstate.id != record.id:
                            certification_now_last += line.amount_total
        except Exception as e:
            _logger.info('Error : %s' % e)



        invoice_vals = {
            'move_type': self.type_invoice,
            'partner_id': record.project_id.invoice_address_id.id if record.project_id.invoice_address_id else record.project_id.customer_id.id,
            'partner_shipping_id': record.project_id.customer_id.id,
            'journal_id': journal,
            'currency_id': self.company_id.currency_id.id,
            'invoice_date': record.date,
            'invoice_user_id': self.env.user.id,
            'invoice_line_ids': [],
            'narration': record.paidstate_notes,
            'include_for_bim': self.company_id.bim_include_invoice_sale,
            'invoice_payment_term_id': invoice_payment_term_id,
            'bim_massive_certification_by_line_id' : certification_id.id if certification_id else False,
            'certification_now_origin' : certification_now_origin if certification_now_origin else False,
            'certification_now_last' : certification_now_last if certification_now_last else False,
        }

        """
        Revisamos si existe el docuemnto de pago para agregarlo.
        """

        customer_res_payment_document_id = False
        # Reviso si esta instalado payment_document
        if self.env['ir.module.module'].search([('name', '=', 'payment_document'), ('state', '=', 'installed')]):
            if record.project_id.customer_id:
                customer_res_payment_document_id = record.project_id.customer_id.customer_res_payment_document_id.id

            if record.project_id.customer_res_payment_document_id:
                customer_res_payment_document_id = record.project_id.customer_res_payment_document_id.id

            if customer_res_payment_document_id:
                invoice_vals.update({
                    'customer_res_payment_document_id': customer_res_payment_document_id,
                })


        if record.type == 'manual':
            _logger.info('Manual')
            project = record.project_id
            for line in record.object_lines_ids:
                if line.project_id:
                    project = line.project_id
                vals = {
                         'name': '%s - %s' % (record.name, record.project_id.nombre[0:40]),
                         'sequence': 1,
                         'account_id': income_account.id,
                         'price_unit': line.amount,
                         'quantity': 1 * record.indicator_a if record.indicator_a > 0 else 1  * record.indicator_b if record.indicator_b > 0 else 1,
                         'product_uom_id': product.uom_id.id,
                         'product_id': product.id,
                         'tax_ids': [(6, 0, product.taxes_id.ids)],
                         'project_id': project.id,
                         'company_id': company_id.id,
                     }
                if analytic_id:
                    vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })
                invoice_vals['invoice_line_ids'].append(
                    (0, 0,vals))
        else:
            _logger.info('Por certificación')
            project = record.project_id
            for line in record.lines_ids:
                _logger.info('-line-')
                _logger.info(income_account.name)

                if line.project_id:
                    project = line.project_id
                vals = {
                        'name': '%s - %s'%(record.name, record.project_id.nombre[0:40]),
                        'sequence': 1,
                        'account_id': income_account.id,
                        'price_unit': line.amount if not record.invoice_debit_credit else line.amount_total,
                        'quantity': line.quantity * record.indicator_a if record.indicator_a > 0 else 1  * record.indicator_b if record.indicator_b > 0 else 1,
                        'product_uom_id': product.uom_id.id,
                        'product_id': product.id,
                        'tax_ids': [(6, 0, product.taxes_id.ids)],
                        'budget_id': line.budget_id.id,
                        'project_id': project.id,
                        'company_id': company_id.id,
                      }
                if analytic_id:
                    vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })
                invoice_vals['invoice_line_ids'].append(
                    (0, 0,vals))

        # Agregamos la retención a la factura
        if retention == 'invoice':
            invoice_vals.update({
                'retention_percentage': abs(record.paidstate_company_retention),
            })


        if self.apply_retention and self.project_id.retention > 0 and retention == 'invoice_line':
            vals = {
                     'name': '%s - %s - %s' % (record.name, record.project_id.nombre[0:40], str(record.project_id.retention) + '%'),
                     'sequence': 1,
                     'account_id': retention_account.id,
                     'price_unit': record.paidstate_retention,
                     'quantity': 1,
                     'product_uom_id': product.uom_id.id,
                     'product_id': retention_product.id,
                     'tax_ids': [(6, 0, retention_product.taxes_id.ids)],
                     'budget_id': line.budget_id.id if self.type == 'certification' else False,
                     'company_id': company_id.id,
                 }
            if analytic_id:
                vals.update({
                    'analytic_distribution': {'%s' % (analytic_id): 100}
                })
            invoice_vals['invoice_line_ids'].append(
                (0, 0,vals))



        ###################################################
        invoice = invoice_obj.create(invoice_vals)
        record.invoice_id = invoice.id
        record.project_id.write({'invoice_ids': [(4, invoice.id)]})
        record.write({'state': 'invoiced'})

        # usar sudo
        action = self.env.ref('account.action_move_out_invoice_type').sudo()
        result = action.read()[0]
        res = self.env.ref('account.view_move_form', False).sudo()
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = invoice.id

        _logger.info('== End action_invoice ==')
        return result

    @api.onchange('lines_ids')
    def onchange_lines_ids(self):
        for record in self:
            record.amount = sum(x.amount for x in record.lines_ids)


class BimPaidstateLine(models.Model):
    _description = "Bim Paid state Line"
    _name = 'bim.paidstate.line'

    name = fields.Char('Description', required=True)
    quantity = fields.Integer('Quantity', default=1)
    percent = fields.Float('%', help="Percentage given by the real value between the estimated value", store=True)
    price_unit = fields.Float("Price", digits="BIM price")
    certification_factor = fields.Float()
    amount = fields.Float('Balance', compute='_amount_compute', store=True, digits="BIM price")
    amount_total = fields.Float('Balance Total', compute='_amount_compute', store=True, digits="BIM price")
    paidstate_id = fields.Many2one('bim.paidstate', 'Payment State', ondelete="cascade")
    project_id = fields.Many2one('bim.project', 'Project', related='paidstate_id.project_id')
    budget_id = fields.Many2one('bim.budget', 'Budget')
    is_loaded = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', 'Company', related='paidstate_id.company_id')



    @api.onchange('budget_id')
    def onchange_budget_id(self):
        budget_list = []
        if self.paidstate_id:
            budget_list.append(self.paidstate_id.project_id.id)
        return {'domain': {'budget_id': [('project_id','in',budget_list)]}}

    @api.onchange('budget_id')
    def onchange_name(self):
        name_list = []
        if self.budget_id:
            name_list.append(self.budget_id.name)
        self.name = name_list and '-'.join(name_list) or ''

    @api.depends('quantity','price_unit','certification_factor')
    def _amount_compute(self):
        for record in self:
            record.amount = record.quantity * record.price_unit
            record.amount_total = record.amount * record.certification_factor if record.certification_factor > 0 else record.amount

    def unlink(self):
        for record in self:
            record.is_loaded = False
            record.budget_id.compute_balance_certified_residual()
        return super().unlink()


class BimPaidstateObjectLine(models.Model):
    _description = "Bim .Paid state Object Line"
    _name = 'bim.paidstate.object.line'

    paidstate_id = fields.Many2one('bim.paidstate', 'Payment State', ondelete="cascade")
    project_id = fields.Many2one('bim.project', related='paidstate_id.project_id')
    percent = fields.Float('%')
    amount = fields.Float("Amount", required=True, digits="BIM price")
    object_id = fields.Many2one('bim.object', domain="[('project_id','=',project_id)]", required=True)
    is_loaded = fields.Boolean(default=False)








