# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class BudgetRequest(models.Model):
    _description = "Budget Request"
    _name = 'budget.request'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    a_user_id = fields.Many2one('res.users', string='Approver')
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    department_id = fields.Many2one('bim.department', string='Departament', default=lambda self: self.env['bim.department'].search([], limit=1).id)
    project_id = fields.Many2one('bim.project', string='Project')
    obs = fields.Text('Observations')


    type = fields.Selection([
        ('generic', 'Generic'),
        ('apu', 'Apu'),
        ], string='Type', default='generic')


    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'requested'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='State', readonly=True, copy=False, index=True,
        tracking=True, default='draft')
    lines_ids = fields.One2many('budget.request.line', 'request_id', 'Lines', copy=False)
    lines_apu_ids = fields.One2many('budget.request.line.apu', 'request_id', 'Lines APU', copy=False)

    budget_ids = fields.One2many('bim.budget', 'budget_request_id', 'Budgets', copy=False)
    budget_count = fields.Integer('Budget Count', compute='_compute_budget_count')
    obs = fields.Text('Observations')

    @api.depends('budget_ids')
    def _compute_budget_count(self):
        for record in self:
            record.budget_count = len(record.budget_ids)

    # acction
    def action_view_budgets(self):
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        action['domain'] = [('budget_request_id', '=', self.id)]
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('budget.request') or 'New'
        return super().create(vals_list)

    def action_request(self):
        self.state = 'requested'


    def action_approve(self):
        self.a_user_id = self.env.user
        self.state = 'approved'

    def action_done(self):
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'

    def create_budget(self):
        """
        if not self.project_id:
            raise ValidationError(_('Select a project first'))
        """

        date_start = fields.Date.today()
        date_end = date_start + timedelta(days=365)

        budget = self.env['bim.budget'].create({
            'project_id': self.project_id.id if self.project_id else False,
            'name': 'Budget from APU',
            'currency_id': self.project_id.currency_id.id if self.project_id.currency_id else self.env.company.currency_id.id,
            'date_start': date_start,
            'date_end': date_end,
            'budget_request_id' : self.id,
        })

        bim_concept_general = self.env['bim.concepts'].create({
            'budget_id': budget.id,
            'name': 'GENERAL',
            'type': 'chapter',
            'code': '01',
            'quantity': 1,
        })


        for line in self.lines_apu_ids:
            bim_concept_template = line.bim_concept_template_id

            # revisamos si ya existe un concepto la misma plantilla

            bim_concept = self.env['bim.concepts'].search([
                        ('concept_template_id', '=', bim_concept_template.id),
                        ('budget_id', '=', budget.id)
                    ])

            if not bim_concept:
                bim_concept = self.env['bim.concepts'].create({
                    'budget_id': budget.id,
                    'name': bim_concept_template.name,
                    'type': 'departure',
                    'code': bim_concept_template.code,
                    'quantity': line.amount_subtotal,
                    'parent_id': bim_concept_general.id,
                    'performance': bim_concept_template.performance,
                    'concept_template_id': bim_concept_template.id,
                })

                for _rec in bim_concept_template.template_line_ids:
                    if _rec.type == 'H':
                        type = 'labor'
                    elif _rec.type == 'Q':
                        type = 'equip'
                    elif _rec.type == 'S':
                        type = 'subcontract'
                    elif _rec.type == 'A':
                        type = 'aux'
                    elif _rec.type == 'M':
                        type = 'material'
                    else:
                        raise UserError(_("Type not defined"))

                    self.env['bim.concepts'].create({
                        'budget_id': budget.id,
                        'name': _rec.name,
                        'type': type,
                        'code': _rec.code,
                        'quantity': _rec.quantity,
                        'parent_id': bim_concept.id,
                        'product_id': _rec.product_id.id,
                        'amount_fixed': _rec.price,

                    })

            # buscamos el espacio
            bim_budget_space_id = self.env['bim.budget.space'].search([
                ('budget_id', '=', budget.id),
            ], limit=1)

            bim_concept_measuring_id = self.env['bim.concept.measuring'].create({
                'space_id': bim_budget_space_id.id,
                'name': bim_concept_template.name,
                'qty': line.qty,
                'length': line.x,
                'width': line.y,
                'height': line.z,
                'concept_id': bim_concept.id,
            })

            bim_concept_quantity_measuring = self.env['bim.concept.measuring'].search([
                ('concept_id', '=', bim_concept.id),
            ])

            m_quantity = 0
            for m in bim_concept_quantity_measuring:
                m_quantity += m.amount_subtotal
            bim_concept.quantity = m_quantity



class BudgetRequestLine(models.Model):
    _description = "Budget Request Line"
    _name = 'budget.request.line'
    _order = "id"

    name = fields.Char('Departure')
    type = fields.Selection([
        ('ma', 'MAT'),
        ('mo', 'MO'),
        ('eq', 'EQ'),
        ('o', 'OTH'),
        ], string='Type', default='o')

    description = fields.Text('Description')


    qty = fields.Float('Quantity')
    x = fields.Float('X')
    y = fields.Float('Y', default=1)
    z = fields.Float('Z', default=1)
    amount_subtotal = fields.Float('Subtotal', compute='_compute_amount_subtotal', store=True)

    uom_id = fields.Many2one('uom.uom', string='UOM')
    request_id = fields.Many2one('budget.request', ondelete='cascade')

    @api.depends('qty', 'x', 'y', 'z')
    def _compute_amount_subtotal(self):
        for line in self:
            qty = line.qty
            if line.x > 0:
                qty = qty * line.x
            if line.y > 0:
                qty = qty * line.y
            if line.z > 0:
                qty = qty * line.z
            line.amount_subtotal = qty

class BudgetRequestLineApu(models.Model):
    _description = "Budget Request Line Apu"
    _name = 'budget.request.line.apu'
    _order = "id"

    request_id = fields.Many2one('budget.request', ondelete='cascade')
    bim_concept_template_id = fields.Many2one('bim.concept.template', string='APU')

    qty = fields.Float('Quantity')
    x = fields.Float('X')
    y = fields.Float('Y', default=1)
    z = fields.Float('Z', default=1)
    amount_subtotal = fields.Float('Subtotal', compute='_compute_amount_subtotal', store=True)

    @api.depends('qty', 'x', 'y', 'z')
    def _compute_amount_subtotal(self):
        for line in self:
            qty = line.qty
            if line.x > 0:
                qty = qty * line.x
            if line.y > 0:
                qty = qty * line.y
            if line.z > 0:
                qty = qty * line.z
            line.amount_subtotal = qty


    description = fields.Text('Description')


