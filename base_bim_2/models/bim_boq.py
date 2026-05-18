# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import os
import csv
from odoo.exceptions import UserError
import base64
import xlrd
import xlwt
from io import BytesIO

class BimBoq(models.Model):
    _description = "Bim Boq"
    _name = 'bim.boq'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    observation = fields.Text('Observation')
    lines_ids = fields.One2many('bim.boq.line', 'boq_id', string='Lines')
    file = fields.Binary('File')
    file_name = fields.Char('File Name')
    bim_boq_id = fields.Many2one('bim.boq', string='BOQ')
    amount = fields.Float('Amount', compute='_compute_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    manual_prices = fields.Boolean('Manual Prices')

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

    type = fields.Selection([
        ('contract', 'Contract'),
        ('project', 'Project'),
        ('increase', 'Increase'),
        ('decreases', 'Decreases'),
    ], string='Type', default='contract')

    @api.depends('lines_ids')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(line.amount for line in rec.lines_ids)



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

    def clear_lines(self):
        self.lines_ids.unlink()


    def create_budget(self):
        if self.budget_id:
            raise UserError(_('Budget already created'))

        budget_id = self.env['bim.budget'].create({
            'name': self.name,
            'project_id': self.project_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
            'currency_id': self.currency_id.id,
        })

        # Cramos el concepto principal
        concept_id = self.env['bim.concepts'].create({
            'name': self.name,
            'code': "01",
            'budget_id': budget_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'type': 'chapter',
        })

        # Creamos los conceptos hijos
        for line in self.lines_ids:
            if line.bim_concept_template_id:
                apu_id = self.env['bim.concepts'].create({
                    'name': line.bim_concept_template_id.name,
                    'code': line.bim_concept_template_id.code,
                    'company_id': self.company_id.id,
                    'currency_id': self.currency_id.id,
                    'quantity': line.qty,
                    'parent_id': concept_id.id,
                    'budget_id': budget_id.id,
                    'type': 'departure',
                })

                # Creamos los apus hijos
                for apu in line.bim_concept_template_id.template_line_ids:
                    if apu.type == 'M':
                        type = 'material'
                    elif apu.type == 'H':
                        type = 'labor'
                    elif apu.type == 'E':
                        type = 'equip'
                    else:
                        type = 'aux'

                    self.env['bim.concepts'].create({
                        'name': apu.name,
                        'code': apu.code,
                        'company_id': self.company_id.id,
                        'currency_id': self.currency_id.id,
                        'quantity': line.qty,
                        'parent_id': apu_id.id,
                        'budget_id': budget_id.id,
                        'type': type,
                        'amount_fixed': apu.price,
                    })

            else:

                if self.manual_prices:
                    apu_id = self.env['bim.concepts'].create({
                        'name' : line.description,
                        'code': line.name,
                        'company_id': self.company_id.id,
                        'currency_id': self.currency_id.id,
                        'quantity': line.qty,
                        'parent_id': concept_id.id,
                        'budget_id': budget_id.id,
                        'type': 'departure',
                        'amount_type' : 'fixed',
                        'amount_fixed' : line.price,
                    })
                else:
                    apu_id = self.env['bim.concepts'].create({
                        'name': line.description,
                        'code': line.name,
                        'company_id': self.company_id.id,
                        'currency_id': self.currency_id.id,
                        'quantity': line.qty,
                        'parent_id': concept_id.id,
                        'budget_id': budget_id.id,
                        'type': 'departure',
                    })

            if apu_id:
                line.bim_concepts_id = apu_id.id


        if budget_id:
            self.budget_id = budget_id.id
            self.message_post(body='Budget created %s' % (budget_id.name))


    def update_budget(self):
        if not self.budget_id:
            raise UserError(_('Budget not created'))

        for line in self.lines_ids:
            if line.bim_concepts_id:
                line.concept_amount = line.bim_concepts_id.sale_amount


    def export_boq(self):
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet("Product")
        file_name = 'boq_export_' + str(self.id) + '.xls'
        style_border_table_top = xlwt.easyxf(
            'borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        style_border_table_details_red = xlwt.easyxf('borders: bottom thin; font: colour red, bold True;')

        worksheet.write(0, 0, _("code"), style_border_table_top)
        worksheet.write(0, 1, _("description"), style_border_table_top)
        worksheet.write(0, 2, _("quantity"), style_border_table_top)
        worksheet.write(0, 3, _("uom"), style_border_table_top)
        worksheet.write(0, 4, _("price"), style_border_table_top)
        worksheet.write(0, 5, _("amount"), style_border_table_top)

        row = 1
        for line in self.lines_ids:
            worksheet.write(row, 0, line.name, style_border_table_details)
            worksheet.write(row, 1, line.description, style_border_table_details)
            worksheet.write(row, 2, line.qty, style_border_table_details)
            worksheet.write(row, 3, line.uom, style_border_table_details)
            worksheet.write(row, 4, line.price, style_border_table_details)
            worksheet.write(row, 5, line.amount, style_border_table_details)
            row += 1

        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        data_b64 = base64.encodebytes(data)
        doc = self.env['ir.attachment'].create({
            'name': '%s.xls' % (file_name),
            'datas': data_b64,
        })
        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'no_destroy': False,
        }

    def import_boq(self):
        # Importamos desde un archivo excel (code,quantity,description,uom)
        if not self.file:
            raise UserError(_('You must select a file to import'))
        try:
            file_path = '/tmp/boq_import.xlsx'
            with open(file_path, 'wb') as file:
                file.write(base64.b64decode(self.file))
            workbook = xlrd.open_workbook(file_path)
            sheet = workbook.sheet_by_index(0)
            for row in range(1, sheet.nrows):
                code = sheet.cell_value(row, 0)
                qty = sheet.cell_value(row, 2)
                description = sheet.cell_value(row, 1)
                uom = sheet.cell_value(row, 3)
                price = sheet.cell_value(row, 4)

                boq_line = self.env['bim.boq.line'].create({
                    'boq_id': self.id,
                    'name': code,
                    'qty': qty,
                    'description': description,
                    'uom': uom,
                    'price': price,
                })
        except Exception as e:
            raise UserError(_('Error importing file: %s') % e)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.boq') or 'New'
        return super().create(vals_list)

class BimBoqLine(models.Model):
    _description = "Bim Boq Line"
    _name = 'bim.boq.line'

    boq_id = fields.Many2one('bim.boq', string='Boq', required=True)
    name = fields.Char('Code')
    description = fields.Char('Description')
    qty = fields.Float('Quantity')
    bim_concepts_id = fields.Many2one('bim.concepts', string='Concept')
    uom = fields.Char('UM')
    price = fields.Float('Price')
    amount = fields.Float('Amount', compute='_compute_amount', store=True)
    concept_amount = fields.Float('Budget Amount')

    bim_concept_template_id = fields.Many2one('bim.concept.template', string='BD APU')
    bim_apu_template_id = fields.Many2one('bim.apu.template', string='Template APU')

    hh_plan = fields.Float('HH Plan')
    hh_real = fields.Float('HH Real')
    qty_exec = fields.Float('Qty Exec')
    hh_win = fields.Float('HH Win')

    @api.depends('qty', 'price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.qty * rec.price