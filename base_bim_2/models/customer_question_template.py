# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import random, string

class CustomerQuestionTemplate(models.Model):
    _description = "Customer Question Template"
    _name = 'customer.question.template'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', copy=False)
    long = fields.Integer('Long', default=5)
    lines_ids = fields.One2many('customer.question.template.line', 'template_id', 'Lines', copy=False)

    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    bim_concepts = fields.Many2one('bim.concepts', string='Concepts')
    department_id = fields.Many2one('bim.department', string='Departament', default=lambda self: self.env['bim.department'].search([], limit=1).id)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    text_template = fields.Text('Text Template', default="Estimado cliente, por favor responda las siguientes preguntas:")

    url = fields.Char('Url', compute='_compute_url', store=True, tracking=True)
    @api.depends('key')
    def _compute_url(self):
        for rec in self:
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.url = param_web_base_url + '/bim/survey/' + str(rec.key)

    def _get_key(self):
        # Random key 10 digits
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    key = fields.Char("Key", tracking=True, default=_get_key)

class CustomerQuestionTemplateLine(models.Model):
    _description = "Customer Question Template Line"
    _name = 'customer.question.template.line'
    _order = "sequence"

    name = fields.Many2one('customer.question', string='Question')
    sequence = fields.Integer(string='Sequence')
    template_id = fields.Many2one('customer.question.template', ondelete='cascade')