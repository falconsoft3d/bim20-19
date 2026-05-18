# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta

class HrAttendanceMass(models.Model):
    _name = 'hr.attendance.mass'
    _description = 'Massive attendance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"


    name = fields.Char('Name', default="New")
    project_id = fields.Many2one('bim.project', string='Project')
    customer_id = fields.Many2one('res.partner', string='Customer', related='project_id.customer_id')
    bim_documentation_id = fields.Many2one('bim.documentation', string='Document')

    employee_ids = fields.Many2many('hr.employee', related='project_id.employee_ids')
    budget_id = fields.Many2one('bim.budget', string='Budget', domain="[('project_id','=',project_id),('state_id.include_in_attendance','=',True)]")
    concept_id = fields.Many2one('bim.concepts', string='Concept', domain="[('budget_id','=',budget_id),('type','=','departure')]")
    date_from = fields.Date(default=lambda e: fields.Date.today(), required=True)
    date_to = fields.Date(default=lambda e: fields.Date.today(), required=True)
    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')
    working_hours = fields.Float('Bim Working Hours', default=lambda self: self.env.company.working_hours, digits="BIM qty")
    line_ids = fields.One2many('hr.attendance.mass.line','attendance_mass_id')
    description = fields.Text(default="")
    include_weekend = fields.Boolean(default=False)
    show_alert = fields.Boolean(compute="_compute_show_alert")
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    hour_start_job = fields.Selection(
        [('0', '00'), ('1', '01'), ('2', '02'), ('3', '03'), ('4', '04'), ('5', '05'),
         ('6', '06'), ('7', '07'),('8', '08'), ('9', '09'), ('10', '10'), ('11', '11'),
         ('12', '12'),('13', '13'), ('14', '14'), ('15', '15'), ('16', '16'), ('17', '17'),
         ('18', '18'), ('19', '19'), ('20', '20'),('21', '21'), ('22', '22'), ('23', '23')],
         required=True,
         default=lambda self: self.env.company.hour_start_job)
    minute_start_job = fields.Selection(
        [('0', '00'), ('5', '05'), ('10', '10'), ('15', '15'),
         ('20', '20'), ('25', '25'), ('30', '30'),('35', '35'),
         ('40', '40'), ('45', '45'),('50', '50'),('55', '55')],
         default=lambda self: self.env.company.minute_start_job,
         required=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('done', 'Confirmed'),
         ('cancel', 'Cancelled')],
        'Status', readonly=True, copy=False,
        tracking=True,
        default='draft')
    attendance_count = fields.Integer('Count', compute="_compute_attendances")
    total_hours = fields.Float(compute="_compute_total_hours", store=True)

    total_amount = fields.Float(compute="_compute_total_amount")

    @api.depends('line_ids')
    def _compute_total_amount(self):
        for record in self:
            if record.line_ids:
                hr_attendance_ids = record.line_ids.mapped('attendance_id')
                if hr_attendance_ids:
                    record.total_amount = sum(hr_attendance_ids.mapped('attendance_cost'))
                else:
                    record.total_amount = 0
            else:
                record.total_amount = 0

    # onchange date_from
    @api.onchange('date_from')
    def onchange_date_from(self):
        self.date_to = self.date_from


    @api.depends('line_ids')
    def _compute_attendances(self):
        for record in self:
            record.attendance_count = len(record.line_ids.mapped('attendance_id'))

    @api.depends('line_ids')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = sum(record.line_ids.mapped('working_hours'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.attendance.mass') or 'New'
        return super().create(vals_list)


    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
        
    def action_confirm(self):
        delta = timedelta(days=1)
        for record in self:
            difference = record.date_to - record.date_from
            if not record.include_weekend and (record.date_from == record.date_to or difference.days == 1) and record.date_from.isoweekday() in [6,7]:
                raise UserError(_("Check Include Weekend to Register Attendance in the Selected Dates"))
            while record.date_from <= record.date_to:
                if record.include_weekend or record.date_from.isoweekday() not in [6,7]:
                    for line in record.line_ids:
                        line.register_project_attendance(record.date_from)
                record.date_from += delta
            record.write({'state': 'done'})

            # update project
            if record.project_id:
                record.project_id.action_update_all()

    def action_view_attendances(self):
        att_ids = self.line_ids.mapped('attendance_id').ids
        action = self.env["ir.actions.actions"]._for_xml_id("hr_attendance.hr_attendance_action")
        action['domain'] = [('id', 'in', att_ids)]
        action['context'] = {'search_default_project_id': self.project_id.id}
        return action


    @api.depends('date_from','date_to')
    def _compute_show_alert(self):
        self.show_alert = self.date_from > self.date_to

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            self.line_ids = [(0,0,{
             'employee_id': employee.id,
             'hour_start_job': self.hour_start_job,
             'minute_start_job': self.minute_start_job,
             'working_hours': self.working_hours,
            }) for employee in self.project_id.employee_ids]

    @api.onchange('hour_start_job')
    def onchange_hour_start_job(self):
        for line in self.line_ids:
            line.hour_start_job = self.hour_start_job

    @api.onchange('minute_start_job')
    def onchange_minute_start_job(self):
        for line in self.line_ids:
            line.minute_start_job = self.minute_start_job

    @api.onchange('bim_extra_hour_id')
    def onchange_bim_extra_hour_id(self):
        for line in self.line_ids:
            line.bim_extra_hour_id = self.bim_extra_hour_id.id if self.bim_extra_hour_id else False

    @api.onchange('working_hours')
    def onchange_working_hours(self):
        for line in self.line_ids:
            line.working_hours = self.working_hours


class HrAttendanceMassLine(models.Model):
    _name = 'hr.attendance.mass.line'
    _description = 'Massive Attendance Lines'

    attendance_mass_id = fields.Many2one('hr.attendance.mass')
    attendance_id = fields.Many2one('hr.attendance')
    employee_ids = fields.Many2many('hr.employee', related='attendance_mass_id.employee_ids', string='Employees')
    employee_id = fields.Many2one('hr.employee', required=True, string='Employee')
    project_id = fields.Many2one('bim.project', string='Project')
    note = fields.Text('Note')
    working_hours = fields.Float('B Working Hours', default=lambda self: self.env.company.working_hours, digits="BIM qty")
    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')
    hour_start_job = fields.Selection(
        [('0', '00'), ('1', '01'), ('2', '02'), ('3', '03'), ('4', '04'), ('5', '05'), ('6', '06'), ('7', '07'),
         ('8', '08'), ('9', '09'), ('10', '10'), ('11', '11'), ('12', '12'),
         ('13', '13'), ('14', '14'), ('15', '15'), ('16', '16'), ('17', '17'), ('18', '18'), ('19', '19'), ('20', '20'),
         ('21', '21'), ('22', '22'), ('23', '23')],
         required=True, default=lambda self: self.env.company.hour_start_job)
    minute_start_job = fields.Selection(
        [('0', '00'), ('5', '05'), ('10', '10'), ('15', '15'), ('20', '20'), ('25', '25'), ('30', '30'),
         ('35', '35'), ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')],
        default=lambda self: self.env.company.minute_start_job, required=True)


    @api.onchange('employee_id')
    def onchange_employee_id(self):
        self.project_id = self.attendance_mass_id.project_id.id
    

    def register_project_attendance(self, date_attendance):
        """
        if self.employee_id.hour_cost <= 0:
            raise UserError(_("It is not possible to register Attendance if the Employee %s does not have hour cost defined!")%self.employee_id.name)
        """
        year = date_attendance.year
        month = date_attendance.month
        day = date_attendance.day
        hour = int(self.hour_start_job)
        minute = int(self.minute_start_job)
        check_in = datetime(year,month,day, hour, minute)
        check_out = check_in + timedelta(hours=int(self.working_hours))
        minutes_str = str(self.working_hours).split('.')[1]
        minutes = int(minutes_str)
        if minutes > 0:
            if len(minutes_str) > 1:
                minutes = int(minutes_str[:2])
                minutes = minutes * 6 / 10
            else:
                minutes = minutes * 60 / 10
            check_out = check_out + timedelta(minutes=int(minutes))

        bim_client_hour = self.env['bim.client.hour'].search([
                ('partner_id','=',self.project_id.customer_id.id)],
            limit=1)

        vals = {
            'project_id': self.attendance_mass_id.project_id.id,
            'budget_id': self.attendance_mass_id.budget_id.id,
            'concept_id': self.attendance_mass_id.concept_id.id,
            'employee_id': self.employee_id.id,
            'bim_client_hour_id': bim_client_hour.id if bim_client_hour else False,
            'check_in': check_in,
            'from_wizard': True,
            'check_out': check_out,
            'description': self.attendance_mass_id.description,
            'bim_extra_hour_id': self.bim_extra_hour_id.id or False,
        }

        attendance = self.env['hr.attendance'].create(vals)
        attendance.compute_attendance_cost()
        self.attendance_id = attendance.id

