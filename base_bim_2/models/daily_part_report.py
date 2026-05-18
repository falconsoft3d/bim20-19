# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class DailyPartReport(models.Model):
    _description = "Daily Part Report"
    _name = 'daily.part.report'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)
    date = fields.Date('Date', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('read', 'Read'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='State', readonly=True, copy=False, index=True, tracking=True, default='draft')

    line_ids = fields.One2many('daily.part.report.line', 'daily_part_report_id', string='Lines')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('daily.part.report') or 'New'
        return super().create(vals_list)


    def action_read(self):
        self.write({'state': 'read'})
        # Eliminar todas las lineas
        self.line_ids.unlink()

        # Crear las lineas
        for line in self.env['bim.resource.template'].search([
            ('active', '=', True)]):

            line = self.env['daily.part.report.line'].create({
                'daily_part_report_id': self.id,
                'bim_resource_template_id': line.id,
                'hr_employee_id': line.hr_employee_id.id,
                'sup_hr_employee_id': line.sup_hr_employee_id.id,
                'superintendent_hr_employee_id': line.superintendent_hr_employee_id.id,
                'employee_location_id': line.employee_location_id.id,
                'is_active': line.is_active,
            })

            diary_part_id = self.env['diary.part'].search([
                ('bim_resource_template_id', '=', line.bim_resource_template_id.id),
                ('date', '=', self.date),
            ])
            if diary_part_id:
                diary_part_id.search_hours()
                line.diary_part_id = diary_part_id.id
                line.state = diary_part_id.state
                line.hh = diary_part_id.hh
                line.hhr = diary_part_id.hhr
                line.employee_discipline_id = diary_part_id.employee_discipline_id.id
                line.employee_area_id = diary_part_id.employee_area_id.id


    def action_draft(self):
        self.write({'state': 'draft'})

    def action_done(self):
        self.write({'state': 'done'})

class DailyPartReportLine(models.Model):
    _description = "Daily Part Report Line"
    _name = 'daily.part.report.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    daily_part_report_id = fields.Many2one('daily.part.report', string='Daily Part Report')

    diary_part_id = fields.Many2one('diary.part', string='Diary Part')
    bim_resource_template_id = fields.Many2one('bim.resource.template', string='Brigade')
    hr_employee_id = fields.Many2one('hr.employee', 'Responsible')
    sup_hr_employee_id = fields.Many2one('hr.employee', 'Supervisor')
    superintendent_hr_employee_id = fields.Many2one('hr.employee', 'Superintendent')
    employee_location_id = fields.Many2one('employee.location', string='Location')
    employee_discipline_id = fields.Many2one('employee.discipline', string='Discipline')
    employee_area_id = fields.Many2one('employee.area', string='Area')
    is_active = fields.Boolean('Is Active', default=True)
    hh = fields.Float('HH', default=0)
    hhr = fields.Float('HH R', default=0)
    dif_hh = fields.Float('Dif HH', compute='_compute_dif_hh', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('dont_work', 'Dont Work'),
        ('loaded', 'Loaded'),
        ('review', 'Review'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft', required=True, copy=False, tracking=True)

    @api.depends('hh', 'hhr')
    def _compute_dif_hh(self):
        for record in self:
            record.dif_hh = record.hh - record.hhr