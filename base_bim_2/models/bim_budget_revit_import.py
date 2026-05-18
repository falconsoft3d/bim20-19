# -*- coding: utf-8 -*-
# Part of Marlon Falcon Hernandez. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class BimBudgetRevitImport(models.Model):
    _description = "Bim Budget Revit Import"
    _name = 'bim.budget.revit.import'
    _order = "id desc"

    name = fields.Char('Code', default='New')
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    project_id = fields.Many2one(comodel_name="bim.project", string="Project", required=True, domain="[('company_id', '=', company_id)]")
    budget_id = fields.Many2one(comodel_name="bim.budget", string="Budget", required=True, domain="[('project_id', '=', project_id)]", ondelete="cascade")
    file = fields.Binary(string="File", required=True)
    file_name = fields.Char(string="File Name", required=True)
    log = fields.Text(string="Log", readonly=True, default='')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.budget.revit.import') or 'New'
        return super().create(vals_list)

