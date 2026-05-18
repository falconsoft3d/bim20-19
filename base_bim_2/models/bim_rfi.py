# -*- coding: utf-8 -*-
import base64
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime

class BimRfi(models.Model):
    _description = "Bim Rfi"
    _name = 'bim.rfi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, index=True,default='New')
    date = fields.Date('Date', default=datetime.today(), required=True)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    contact_id = fields.Many2one('res.partner', string='Contact')
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    origin_request = fields.Selection([
        ('external_rfi', 'External RFI'),
        ('internal_rfi', 'Internal RFI'),
    ], string='Origin Request', required=True, default='internal_rfi')

    type = fields.Selection([
        ('clarification', 'Clarification'),
        ('conflict', 'Conflict'),
        ('unclear', 'Unclear'),
        ('discrepancy', 'Discrepancy'),
        ('suggestions', 'Suggestions'),
        ('contractual', 'Contractual'),
        ('specifications', 'Specifications'),
        ('finances', 'Finances'),
    ], string='Type', required=True, default='clarification')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('working', 'Working'),
        ('submitted_review', 'Submitted Review'),
        ('rev1', 'Revised 1'),
        ('sent_to_customer', 'Sent To Customer'),
        ('rev2', 'Revised 2'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='State', required=True, default='draft', tracking=True)

    bim_rfi_id = fields.Many2one('bim.rfi', string='RFI Related')

    description = fields.Text('Description')

    response = fields.Text('Response')
    line_ids = fields.One2many('bim.rfi.line', 'rfi_id', string='Lines')

    internal_approval_state = fields.Selection([
        ('no', 'No'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Internal State', default='no', copy=False, tracking=True)

    external_approval_state = fields.Selection([
        ('no', 'No'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='External State', default='no', copy=False, tracking=True)

    reference_plans = fields.Char('Reference Plans')
    response_plans = fields.Char('Response Plans')
    impact_cost = fields.Boolean('Impact Cost')
    impact_schedule = fields.Boolean('Impact Schedule')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.rfi') or 'New'
        return super().create(vals_list)

    def to_draft(self):
        self.state = 'draft'

    def to_done(self):
        self.state = 'done'

    def send_to_client(self):
        self.state = 'sent_to_customer'

    def review_1(self):
        if self.internal_approval_state == 'no':
            raise UserError(_('You must approve the internal approval first'))
        self.state = 'rev1'

    def review_2(self):
        if self.external_approval_state == 'no':
            raise UserError(_('You must approve the external approval first'))
        self.state = 'rev2'

    def submit_review(self):
        self.state = 'submitted_review'

    def to_working(self):
        self.state = 'working'

    def send_report_by_email(self):
        # Mandamos el reporte por email
        _logger.info(':::BEGIN RFI SEND')
        email_to = self.contact_id.email
        email_from = self.env.user.email
        email_subject = 'Reporte de RFI'
        email_body = 'Adjunto reporte de RFI'
        email_attachments = []

        # Creamos el reporte
        _logger.info('A')
        pdf = self.env['ir.actions.report']._render_qweb_pdf("base_bim_2.bim_rfi_report", self.id)[0]
        b64_pdf = base64.b64encode(pdf).decode()
        _logger.info('B')

        ATTACHMENT_NAME = self.name
        attach_report = self.env['ir.attachment'].create({
            'name': ATTACHMENT_NAME,
            'type': 'binary',
            'datas': b64_pdf,
            'store_fname': ATTACHMENT_NAME,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        template_id = self.env.ref('base_bim_2.email_template_rfi').id

        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        template.attachment_ids = [(6, 0, [attach_report.id])]
        if template.lang:
            lang = template._render_template(template.lang, 'bim.rfi', self.ids)
        ctx = {
            'default_model': 'bim.rfi',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
        }

        _logger.info(':::END RFI SEND')
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }



class BimRfiLine(models.Model):
    _description = "Bim Rfi Line"
    _name = 'bim.rfi.line'

    rfi_id = fields.Many2one('bim.rfi', string='RFI', required=True)
    file = fields.Binary('File')
    file_name = fields.Char('File Name')