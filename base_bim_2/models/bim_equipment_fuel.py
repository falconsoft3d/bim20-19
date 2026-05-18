# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class BimEquipmentFuel(models.Model):
    _description = "Bim Equipment Fuel"
    _name = 'bim.equipment.fuel'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code', default="New", copy=False)
    note = fields.Text('Notes', default="")
    project_id = fields.Many2one('bim.project', 'Project', ondelete="restrict", copy=True, domain="[('company_id','=',company_id)]", tracking=1)
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", copy=True, domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict", copy=True, domain="[('budget_id','=',budget_id),('type','=','departure')]")
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, copy=False)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    file_name = fields.Char("File Name", copy=False)
    file = fields.Binary(string='File', copy=False)
    product_id = fields.Many2one('product.product', domain="[('resource_type','=','Q')]", required=True, ondelete="restrict",)
    liters = fields.Float(tracking=1, digits='BIM qty')
    cost = fields.Float(tracking=1, digits='BIM price')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    invoice_id = fields.Many2one('account.move', domain="[('company_id','=',company_id)]")
    date = fields.Datetime('Date', copy=False, default=fields.Datetime.now, tracking=True)
    amount_total = fields.Float(compute='_compute_amount_total', store=True, digits='BIM price')
    type = fields.Selection([('gas', 'Gas'), ('diesel', 'Diesel')], required=True, tracking=True)
    km = fields.Float(tracking=True, digits='BIM qty')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.equipment.fuel') or 'New'
        return super().create(vals_list)

    @api.depends('liters','cost')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = record.liters * record.cost

    @api.onchange('type')
    def onchange_type(self):
        cost = 0
        if self.type:
            fuel_rec = self.env['bim.fuel.cost'].search([('type','=',self.type)],limit=1)
            cost = fuel_rec.cost if fuel_rec else 0
        self.cost = cost

    @api.onchange('project_id')
    def onchange_project_id(self):
        self.budget_id = False
        self.concept_id = False

    @api.onchange('budget_id')
    def onchange_budget_id(self):
        self.concept_id = False



