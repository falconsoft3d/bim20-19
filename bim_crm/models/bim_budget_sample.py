# -*- coding: utf-8 -*-
from odoo import fields, models, api,_
from odoo.exceptions import UserError


class BimBudgetSample(models.Model):
    _name = "bim.budget.sample"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "BIM Budget Sample"

    name = fields.Char(string="Name", readonly=1, default=_('New'))
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id.id)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, domain="[('company_id', 'in', [company_id,False])]")
    city = fields.Char(string="City")
    line_ids = fields.One2many('bim.budget.sample.line', 'budget_id', string='Budget Sample Lines')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('done', 'Done'),('cancel','Cancelled')], string='Status', default='draft', tracking=True)
    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', domain="[('partner_id', '=', partner_id)]")
    amount_total = fields.Float(string='Total', store=True, readonly=True, compute='_compute_amount')
    order_ids = fields.One2many('sale.order', 'budget_sample_id', string='Orders')
    orders_count = fields.Integer(string='Orders', compute='_compute_orders_count', store=True)

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('bim.budget.sample') or "New"
        return super(BimBudgetSample, self).create(vals)

    def name_get(self):
        res = []
        for record in self:
            name = record.name + ' - ' + record.partner_id.name
            if record.city:
                name += record.city
            res.append((record.id, name))
        return res
    def action_confirm(self):
        self.state = 'confirm'
    def action_done(self):
        order_lines = self.prepare_sale_order()
        self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'budget_sample_id': self.id,
            'order_line': order_lines,
        })
        self.state = 'done'

    def prepare_sale_order(self):
        order_lines = []
        for line in self.line_ids:
            order_lines.append((0,0,{
                'product_id': line.unit_id.product_id.id,
                'name': "%s %s m² " %(line.unit_id.name,line.surface),
                'product_uom_qty': 1,
                'product_uom': line.unit_id.product_id.uom_id.id,
                'price_unit': line.amount,
                'tax_id': [(6, 0, line.unit_id.product_id.taxes_id.ids)],
            }))
        return order_lines
    def action_cancel(self):
        self.state = 'cancel'
    def action_back_to_draft(self):
        self.state = 'draft'

    # COMPUTE METHODS
    @api.depends('line_ids', 'line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount_total = sum(line.amount for line in record.line_ids)
    @api.depends('order_ids')
    def _compute_orders_count(self):
        for record in self:
            record.orders_count = len(record.order_ids)

    # ACTION VIEW METHODS
    def action_view_sale_order(self):
        action = self.env.ref('sale.action_orders').sudo().read()[0]
        action['domain'] = [('budget_sample_id', '=', self.id)]
        return action

class BimBudgetSampleLine(models.Model):
    _name = "bim.budget.sample.line"
    _description = "BIM Budget Sample Line"

    budget_id = fields.Many2one('bim.budget.sample', string='Budget Sample')
    unit_id = fields.Many2one('bim.project.unit', string='Unit', required=True)
    allow_typologies = fields.Many2many(string="Allow Typology", related='unit_id.typology_ids')
    typology_id = fields.Many2one('bim.typology', string='Typology', domain="[('id', 'in', allow_typologies)]")
    extra_ids = fields.Many2many('bim.budget.extra', string='Extras')
    surface = fields.Float(string='Surface m²')
    price = fields.Float(string="Price m²", required=True, readonly=1)
    amount = fields.Float(string="Amount", compute='_compute_amount', store=True)
    allow_typologies_count = fields.Integer(string="Allow Typology Count", compute='_compute_allow_typologies_count')
    @api.onchange('typology_id','unit_id','surface')
    def _onchange_unit_and_typology(self):
        self.ensure_one()
        if self.unit_id and self.surface:
            price_obj = self.env['bim.project.unit.typology.price']
            domain = [('unit_id', '=', self.unit_id.id), ('surface', '>=', self.surface)]
            if self.typology_id:
                domain.append(('typology_id', '=', self.typology_id.id))
            related_price = price_obj.search(domain, limit=1, order='surface asc')
            if not related_price:
                domain = [('unit_id', '=', self.unit_id.id)]
                if self.typology_id:
                    domain.append(('typology_id', '=', self.typology_id.id))
                related_price = price_obj.search(domain, limit=1, order='surface desc')
            if related_price:
                price = related_price.price
            else:
                price = 0
            self.price = price
    @api.depends('price','surface','extra_ids')
    def _compute_amount(self):
        for record in self:
            record.amount = record.price * record.surface + sum(record.extra_ids.mapped('price'))
    @api.depends('allow_typologies')
    def _compute_allow_typologies_count(self):
        for line in self:
            line.allow_typologies_count = len(line.allow_typologies)
    @api.constrains('unit_id')
    def _check_typology_required(self):
        for line in self:
            if line.unit_id and line.allow_typologies_count > 0 and not line.typology_id:
                raise UserError(_('Typology is required for unit %s!')%line.unit_id.name)



