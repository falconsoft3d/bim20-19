# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CustomerSurvey(models.Model):
    _description = "Customer Survey"
    _name = 'customer.survey'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    lines_ids = fields.One2many('customer.survey.line', 'survey_id', 'Lines', copy=False)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    customer_question_template_id = fields.Many2one('customer.question.template', string='Question Template')

    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    bim_concepts = fields.Many2one('bim.concepts', string='Concepts')
    department_id = fields.Many2one('bim.department', string='Departament', default=lambda self: self.env['bim.department'].search([], limit=1).id)

    customer = fields.Char('Customer')
    from_customer = fields.Char('From')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='State', readonly=True, copy=False, index=True, tracking=True, default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('customer.survey') or 'New'
        return super().create(vals_list)

    def action_done(self):
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'


    @api.onchange('customer_question_template_id')
    def onchange_customer_question_template_id(self):
        if self.customer_question_template_id:
            self.lines_ids.unlink()
            lines = []
            for line in self.customer_question_template_id.lines_ids:
                lines.append((0, 0, {'name': line.name.id,
                                     'sequence': line.sequence,
                                     'survey_id': self.id}
                                     ))
            self.lines_ids = lines
            self.project_id = self.customer_question_template_id.project_id.id
            self.budget_id = self.customer_question_template_id.budget_id.id
            self.bim_concepts = self.customer_question_template_id.bim_concepts.id

class CustomerSurveyLine(models.Model):
    _description = "Customer Survey Line"
    _name = 'customer.survey.line'
    _order = "sequence"

    sequence = fields.Integer(string='Sequence')
    name = fields.Many2one('customer.question', string='Question')
    value = fields.Integer('Value')
    survey_id = fields.Many2one('customer.survey', ondelete='cascade')
    customer = fields.Char('Customer', related='survey_id.customer')
    from_customer = fields.Char('From', related='survey_id.from_customer')
    department_id = fields.Many2one('bim.department', string='Departament', related='survey_id.department_id')
    project_id = fields.Many2one('bim.project', string='Project', related='survey_id.project_id')
    budget_id = fields.Many2one('bim.budget', string='Budget', related='survey_id.budget_id')
    bim_concepts = fields.Many2one('bim.concepts', string='Concepts', related='survey_id.bim_concepts')
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)

    @api.onchange('value')
    def onchange_value(self):
        if self.value > self.name.long:
            raise ValidationError(_("The value can't be greater than the long of the question"))
        if self.value < 0:
            raise ValidationError(_("The value can't be less than 0"))