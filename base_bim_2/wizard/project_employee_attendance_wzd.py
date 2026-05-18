# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta

import logging
_logger = logging.getLogger(__name__)


class ProjectEmployeeAttendanceWzd(models.TransientModel):
    _name = "project.employee.attendance.wzd"
    _description = 'Project Employee Attendance'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        employee_id = self._context['active_id']
        res['project_id'] = employee_id
        return res

    project_id = fields.Many2one('bim.project', string='Project')
    employee_ids = fields.Many2many('hr.employee', related='project_id.employee_ids')
    budget_id = fields.Many2one('bim.budget', string='Budget', domain="[('project_id','=',project_id),('state_id.include_in_attendance','=',True)]")
    concept_id = fields.Many2one('bim.concepts', string='Concept', domain="[('budget_id','=',budget_id),('type','=','departure')]")
    date_from = fields.Date(default=lambda e: fields.Date.today(), required=True)
    date_to = fields.Date(default=lambda e: fields.Date.today(), required=True)
    hour_start_job = fields.Selection(
        [('0', '00'), ('1', '01'), ('2', '02'), ('3', '03'), ('4', '04'), ('5', '05'), ('6', '06'), ('7', '07'),
         ('8', '08'), ('9', '09'), ('10', '10'), ('11', '11'), ('12', '12'),
         ('13', '13'), ('14', '14'), ('15', '15'), ('16', '16'), ('17', '17'), ('18', '18'), ('19', '19'), ('20', '20'),
         ('21', '21'), ('22', '22'), ('23', '23')], required=True, default=lambda self: self.env.company.hour_start_job)
    minute_start_job = fields.Selection(
        [('0', '00'), ('5', '05'), ('10', '10'), ('15', '15'), ('20', '20'), ('25', '25'), ('30', '30'),
         ('35', '35'), ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')], default=lambda self: self.env.company.minute_start_job, required=True)
    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')

    working_hours = fields.Float('Working Hours', default=lambda self: self.env.company.working_hours, digits="BIM qty")
    line_ids = fields.One2many('project.employee.attendance.wzd.line','wizard_id')
    description = fields.Text(default="")
    include_weekend = fields.Boolean(default=False)
    show_alert = fields.Boolean(compute="_compute_show_alert")
    calc = fields.Boolean(default=False)

    @api.onchange('calc')
    def onchange_calc(self):
        if self.calc:
            self.action_calculate()
        else:
            self.line_ids.unlink()


    # @api.onchange('calc')
    def action_calculate(self):
        _logger.info("= begin onchange_calc = ")
        if self.calc:
            _logger.info("if")
            # clear lines
            self.line_ids.unlink()
            _logger.info("clear")

            # create lines
            employee_ids = self.env['hr.employee'].search([('default_bim_project', '=', self.project_id.id)])
            _logger.info(employee_ids)

            if employee_ids:
                for employee in employee_ids:
                    vals = {
                     'employee_id': employee.id,
                     'hour_start_job': self.hour_start_job,
                     'minute_start_job': self.minute_start_job,
                     'working_hours': self.working_hours,
                    }

                    _logger.info("vals")
                    _logger.info(vals)

                    self.line_ids = [(0,0,vals)]
        else:
            _logger.info("else")

        _logger.info("= end onchange_calc = ")


    def action_register_attendance(self):
        delta = timedelta(days=1)
        difference = self.date_to - self.date_from
        if not self.include_weekend and (self.date_from == self.date_to or difference.days == 1) and self.date_from.isoweekday() in [6,7]:
            raise UserError(_("Check Include Weekend to Register Attendance in the Selected Dates"))
        while self.date_from <= self.date_to:
            if self.include_weekend or self.date_from.isoweekday() not in [6,7]:
                for line in self.line_ids:
                    line.register_project_attendance(self.date_from)
            self.date_from += delta

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


class ProjectEmployeeAttendanceWzdLine(models.TransientModel):
    _name = "project.employee.attendance.wzd.line"
    _description = 'Project Employee Attendance Line'

    wizard_id = fields.Many2one('project.employee.attendance.wzd')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    employee_id = fields.Many2one('hr.employee', required=True)
    hour_start_job = fields.Selection(
        [('0', '00'), ('1', '01'), ('2', '02'), ('3', '03'), ('4', '04'), ('5', '05'), ('6', '06'), ('7', '07'),
         ('8', '08'), ('9', '09'), ('10', '10'), ('11', '11'), ('12', '12'),
         ('13', '13'), ('14', '14'), ('15', '15'), ('16', '16'), ('17', '17'), ('18', '18'), ('19', '19'), ('20', '20'),
         ('21', '21'), ('22', '22'), ('23', '23')], required=True, default=lambda self: self.env.company.hour_start_job)
    minute_start_job = fields.Selection(
        [('0', '00'), ('5', '05'), ('10', '10'), ('15', '15'), ('20', '20'), ('25', '25'), ('30', '30'),
         ('35', '35'), ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')],
        default=lambda self: self.env.company.minute_start_job, required=True)
    working_hours = fields.Float('Working Hours', default=lambda self: self.env.company.working_hours, digits="BIM qty")
    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')

    def register_project_attendance(self, date_attendance):
        if self.employee_id.hour_cost <= 0:
            raise UserError(_("It is not possible to register Attendance if the Employee %s does not have hour cost defined!")%self.employee_id.name)
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

        self.env['hr.attendance'].create({
            'project_id': self.wizard_id.project_id.id,
            'budget_id': self.wizard_id.budget_id.id,
            'concept_id': self.wizard_id.concept_id.id,
            'employee_id': self.employee_id.id,
            'check_in': check_in,
            'from_wizard': True,
            'check_out': check_out,
            'description': self.wizard_id.description,
            'bim_extra_hour_id': self.bim_extra_hour_id.id or False,
        })

