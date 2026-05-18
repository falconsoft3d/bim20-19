# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
import random, string

class BimDocumentation(models.Model):
    _description = "Documentation BIM"
    _name = 'bim.documentation'
    _order = "id desc"
    _rec_name = 'desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Seq', default="New", copy=False)
    code_doc = fields.Char('Code', copy=True)
    desc = fields.Char('Description', copy=True)
    obs = fields.Text('Notes', default="")
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade", copy=True)
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade", copy=True)
    bim_concepts = fields.Many2one('bim.concepts', string='Concept')
    chat_bim_id = fields.Many2one('chat.bim', string='Chat IA')

    budget_cost = fields.Float('Budget (P)', digits='Budget Cost', compute='_get_cost')
    real_cost = fields.Float('Real (P)', digits='Real Cost', compute='_get_real_cost')
    benefit = fields.Float('Benefit (P)', digits='Benefit', compute='_get_benefit')
    maintenance_task_id = fields.Many2one('maintenance.task', 'Maintenance Task', ondelete="cascade", copy=False)

    costumer_state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')], default='draft', tracking=True)

    def _get_cost(self):
        for record in self:
            if record.bim_concepts:
                record.budget_cost = record.bim_concepts.balance
            else:
                record.budget_cost = 0



    def _get_real_cost(self):
        for record in self:
            doc_ids = record.env['hr.attendance.mass'].search([('bim_documentation_id', '=', record.id)])
            if doc_ids:
                record.real_cost = sum(doc_ids.mapped('total_amount'))
            else:
                record.real_cost = 0


    def _get_benefit(self):
        for record in self:
            record.benefit = record.budget_cost - record.real_cost



    public_obs = fields.Text('Public Notes', default="Sin Notas")

    balance = fields.Float('Balance', copy=False
                            , compute='_compute_balance'
                           )

    pending = fields.Float('Pending', copy=False
                            , compute='_compute_balance'
                           )

    user_id = fields.Many2one('res.users', string='User', tracking=True,
        default=lambda self: self.env.user, copy=False)

    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company,
                                 required=True, copy=False)

    file_name = fields.Char("File Name", copy=False)
    file_01 = fields.Binary(string='File', copy=False)
    url = fields.Char('URL', copy=False)
    url_file = fields.Char('URL Fichero', copy=False)

    image_medium = fields.Binary("Image size", copy=False)
    specialty_id = fields.Many2one('bim.specialty', ondelete='restrict')


    amount = fields.Float('Amount', digits='New Amount', copy=False)
    date = fields.Date('Date', default=fields.Date.today(), copy=False)
    expiration_date = fields.Date('End Date', copy=False)
    bim_documentation_format_id = fields.Many2one('bim.documentation.format', 'Format', copy=True)
    number_open = fields.Integer('Number Open', copy=True)
    open_date = fields.Datetime('Open Date', copy=False)

    rev = fields.Char('Rev', copy=True, default="1")

    type = fields.Selection([
        ('contract', 'Contract'),
        ('info', 'Info'),
        ('budget', 'Budget'),
        ('other', 'Other')], default='other')

    state = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired')], default='active',
        compute='_compute_state', store=True , name="Expiration status"
    )

    producer_by_id = fields.Many2one('res.partner', string='Producer', tracking=True, copy=False)
    producer_date = fields.Datetime('Producer Date', copy=False)

    partner_id = fields.Many2one('res.partner', string='Partner', tracking=True, copy=False)
    delivery_date = fields.Datetime('Delivery Date', copy=False)
    partner_obs = fields.Text('Partner Notes', copy=False)

    share = fields.Boolean('Share', default=False, copy=False, tracking=True)
    share_url = fields.Char('Share Url', compute='_compute_url', store=True)
    lines_ids = fields.One2many('bim.document.review', 'bim_documentation_id', string='Lines')
    punctuation = fields.Float('Punctuation', copy=False , compute='_compute_punctuation', store=True)


    @api.depends('lines_ids')
    def _compute_punctuation(self):
        for record in self:
            punctuation = 0
            number_lines = 0

            if record.lines_ids:
                number_lines = len(record.lines_ids)
                for line in record.lines_ids:
                    punctuation += line.punctuation

            if number_lines > 0 and punctuation > 0:
                record.punctuation = punctuation / number_lines
            else:
                record.punctuation = 0


    @api.depends('key','share', 'file_name')
    def _compute_url(self):
        for rec in self:
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.share_url = param_web_base_url + '/bim/document/' + str(rec.key)
            rec.url_file = param_web_base_url + '/bim/document/download/' + str(rec.key)

    def _get_key(self):
        # Random key 10 digits
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    key = fields.Char("Key", tracking=True, default=_get_key)


    def _set_image_medium(self):
        self._set_image_value(self.image_medium)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', "New") == "New":
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.documentation') or "New"

        records = super().create(vals_list)
        return records




    @api.depends('budget_id')
    def _compute_balance(self):
        for record in self:
            record.balance = record.budget_id.balance
            record.pending = record.amount - record.balance

    def print_document_notes(self):
        return self.env.ref('base_bim_2.notes_report_document').report_action(self)

    @api.depends('expiration_date')
    def _compute_state(self):
        for record in self:
            if record.expiration_date and record.expiration_date < fields.Date.today():
                record.state = 'expired'
            else:
                record.state = 'active'

class BimDocumentReview(models.Model):
    _description = "Bim Document Review"
    _name = 'bim.document.review'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Many2one('res.partner', string='Partner', tracking=True, copy=False)
    date = fields.Datetime('Date', copy=False)
    obs = fields.Text('Notes', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')], default='draft', copy=False)

    bim_documentation_id = fields.Many2one(
        'bim.documentation', 'Bim documentation', ondelete='cascade')

    punctuation = fields.Float('Punctuation', copy=False, default=10)



class BimDocumentationFormat(models.Model):
    _description = "Documentation BIM Format"
    _name = 'bim.documentation.format'
    _order = "id desc"

    name = fields.Char('Name', copy=True)