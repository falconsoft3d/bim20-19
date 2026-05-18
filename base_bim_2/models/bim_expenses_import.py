from odoo import api, fields, models,_

import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError

class BimExpensesImport(models.Model):
    _name = "bim.expenses.import"
    _description = "Bim Expenses Import"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = "cost"

    name = fields.Char("Name", required=True)
    type = fields.Selection([
                            ('purchase_invoice','purchase_invoice'),
                            ('hr_attendance','hr_attendance'),
                            ('purchase_order','purchase_order'),
                            ], required=True)


    project = fields.Char("Project", required=True)
    partner = fields.Char("Partner")
    reference = fields.Char("Reference")
    product = fields.Char("Product")
    cost = fields.Float("Cost", digits='BIM price')
    qty = fields.Float("Quantity", digits='BIM quantity')
    company = fields.Char("company")
    migrated = fields.Boolean("Migrated", default=False)
    date = fields.Date("Date", default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    def action_migrate_expenses(self):
        for record in self:
            if not record.migrated:
                record.migrate_expenses()

    def migrate_expenses(self):
        _logger.info('begin migrate_expenses')

        # Buscamos el producto

        for record in self:
            # Product
            if record.product:
                product_id = record.env['product.product'].search([('name','=',record.product)], limit=1)

                if not product_id:
                    product_id = record.env['product.product'].search([('default_code','=',record.product)], limit=1)

                if not product_id:
                    product_id = record.env['product.product'].create({'name':record.product})



            _logger.info('[1] product_id: %s', product_id.name)

            # Project
            if record.project:
                project_id = record.env['bim.project'].search([('name','=',record.project)], limit=1)

                if not project_id:
                    project_id = record.env['bim.project'].search([('nombre','=',record.project)], limit=1)

            if not project_id:
                raise UserError('Project not found')

            _logger.info('[2] project_id: %s', project_id.nombre)


            # Company
            if record.company:
                company_id = record.env['res.company'].search([('name','=',record.company)], limit=1)

            if not company_id:
                company_id = record.env['res.company'].search([], limit=1)

            if not company_id:
                raise Exception('Company not found')


            _logger.info('[3] company_id: %s', company_id.name)

            # Partner
            if record.partner:
                partner_id = record.env['res.partner'].search([('name','=',record.partner)], limit=1)

                if not partner_id:
                    partner_id = record.env['res.partner'].search([], limit=1)

                if not partner_id:
                    partner_id = record.env['res.partner'].create({'name':record.partner})

            _logger.info('[4] partner_id: %s', partner_id.name)


            if record.type == 'purchase_invoice':
                _logger.info('Migrating purchase invoice')

                if record.cost * record.qty <= 0:
                    t = "in_refund"
                else:
                    t = "in_invoice"

                vals = {
                        "name": record.name,
                        "create_date": record.date,
                        "partner_id": partner_id.id,
                        "invoice_date": record.date if record.date else datetime.datetime.now().strftime("%Y-%m-%d"),
                        "move_type" : t,
                        "state" : "draft",
                        "ref" : record.id,
                        "include_for_bim" : True,
                        "project_id": project_id.id,
                       }

                new_account_purchase_id = record.env["account.move"].create(vals)
                analytic_id = project_id.analytic_id.id and project_id.analytic_id.id or False


                vals = {
                        "name": product_id.name,
                        "product_id": product_id.id,
                        "quantity": record.qty,
                        "price_unit": record.cost,
                        "account_id": product_id.property_account_expense_id.id,
                        "move_id": new_account_purchase_id.id,
                        "tax_ids": [(6, 0, product_id.supplier_taxes_id.ids)],
                        "project_id": project_id.id,
                    }


                lines = [(0, 0, vals)]

                vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })



                new_account_purchase_id.write({"invoice_line_ids": lines})
                new_account_purchase_id.action_post()


                record.write({'migrated':True})




        _logger.info('end migrate_expenses')