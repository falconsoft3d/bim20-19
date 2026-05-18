# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AnaliticAccountControl(models.Model):
    _name = 'analitic.account.control'
    _description = 'Analitic Account Control'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code', default='New')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    create_date = fields.Datetime('Create Date', default=fields.Datetime.now)
    project_id = fields.Many2one('bim.project', string='Project')
    state = fields.Selection([('draft', 'Draft'),
                              ('sent', 'Sent'),
                              ('done', 'Done'),
                              ('canceled', 'Canceled')
                              ], string='State', default='draft')

    account_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    bim_department_id = fields.Many2one('bim.department', string='Department')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    analytic_name = fields.Char('Analytic Name')
    analytic_code = fields.Char('Analytic Code')

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            self.analytic_name = self.project_id.nombre
            self.analytic_code = self.project_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('analitic.account.control') or 'New'
        return super().create(vals_list)

    def action_send(self):
        self.write({'state': 'sent'})


    def action_done(self):
        if not self.project_id:
            raise UserError(_("You must select a project"))

        if not self.analytic_name:
            raise UserError(_("You must enter a analytic name"))

        if not self.analytic_code:
            raise UserError(_("You must enter a analytic code"))

        plan_id = self.env['account.analytic.plan'].search([('company_id', '=', self.env.company.id)],
                                                                            limit=1)

        if not plan_id:
            raise UserError(_("You must configure a analytic plan"))

        # crear una cuenta analitica con el nombre y codigo
        vals = {
            'name': self.analytic_name,
            'code': self.analytic_code,
            'company_id': self.company_id.id,
            'plan_id': plan_id.id,
        }
        account_analytic_account_id = self.env['account.analytic.account'].create(vals)

        if account_analytic_account_id:
            self.project_id.write({'analytic_id': account_analytic_account_id.id})
            self.account_analytic_account_id = account_analytic_account_id.id
            self.write({'state': 'done'})
