# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import xlrd
import base64
from datetime import timedelta


class AssistanceImporter(models.Model):
    _description = "Assistance Importer"
    _name = 'assistance.importer'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('imported', 'Imported'),
         ('inserted', 'Inserted'),
        ('error', 'Error'),
    ], string='State', default='draft', required=True, copy=False, tracking=True)

    file = fields.Binary('File', required=True)
    file_name = fields.Char('File Name', required=True)

    line_ids = fields.One2many('assistance.importer.line', 'assistance_importer_id', string='Lines')

    type = fields.Selection([
        ('zktime-1', 'zktime 1'),
        ('zktime-2', 'zktime 2'),
        ('zktime-3', 'zktime 3'),
    ], string='Type', default='zktime-3', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('assistance.importer') or 'New'
        return super().create(vals_list)

    def import_file(self):
        if self.state != 'draft':
            raise UserError(_('The file has already been imported'))

        # Borramos las asistencias
        for line in self.line_ids:
            line.hr_attendance_id.unlink()

        # Limpiamos las lineas
        self.line_ids.unlink()


        # zktime-2
        if self.type == 'zktime-2':
            # Importamos desde excel  ID de Usuario, Fecha, Turno, TipClockIn, TipClockOut, CODIGO, NOMBRE
            try:
                workbook = xlrd.open_workbook(file_contents=base64.b64decode(self.file))
            except Exception as e:
                _logger.error(e)
                self.state = 'error'
                return False

            sheet = workbook.sheet_by_index(0)
            for row in range(1, sheet.nrows):
                row_values = sheet.row_values(row)
                name = row_values[0]
                employee_id = self.env['hr.employee'].search([('code_bim', '=', name)], limit=1)
                in_time_str = row_values[3]
                out_time_str = row_values[4]

                if in_time_str and out_time_str:
                    server_hour_difference = self.env.company.server_hour_difference

                    # Verificar si el valor no está vacío antes de convertirlo
                    in_hour_datetime = None
                    out_hour_datetime = None
                    if in_time_str:
                        in_hour = datetime.strptime(in_time_str, '%H:%M').time()
                        in_hour_datetime = datetime.combine(datetime.strptime(row_values[1], '%m/%d/%Y').date(), in_hour)
                        in_hour_datetime = in_hour_datetime - timedelta(hours=server_hour_difference)
                    else:
                        in_hour = None  # O algún valor predeterminado o manejo especial

                    if out_time_str:
                        out_hour = datetime.strptime(out_time_str, '%H:%M').time()
                        out_hour_datetime = datetime.combine(datetime.strptime(row_values[1], '%m/%d/%Y').date(), out_hour)
                        out_hour_datetime = out_hour_datetime - timedelta(hours=server_hour_difference)
                    else:
                        out_hour = None
                    date = datetime.strptime(row_values[1], '%m/%d/%Y').date()


                    if employee_id:
                        self.env['assistance.importer.line'].create({
                            'name': name,
                            'employee_id': employee_id.id if employee_id else False,
                            'din_hour': in_hour_datetime,
                            'dout_hour': out_hour_datetime,
                            'assistance_importer_id': self.id,
                        })

        # zktime-1
        if self.type == 'zktime-1':
            # Importamos desde excel  ID de Usuario, Fecha, TipClockIn, TipClockOut
            try:
                workbook = xlrd.open_workbook(file_contents=base64.b64decode(self.file))
            except Exception as e:
                _logger.error(e)
                self.state = 'error'
                return False

            sheet = workbook.sheet_by_index(0)
            for row in range(1, sheet.nrows):
                row_values = sheet.row_values(row)
                name = row_values[0]
                employee_id = self.env['hr.employee'].search([('code_bim', '=', name)], limit=1)
                in_time_str = row_values[3]
                out_time_str = row_values[4]

                server_hour_difference = self.env.company.server_hour_difference

                # Verificar si el valor no está vacío antes de convertirlo
                in_hour_datetime = None
                out_hour_datetime = None
                if in_time_str:
                    in_hour = datetime.strptime(in_time_str, '%H:%M').time()
                    in_hour_datetime = datetime.combine(datetime.strptime(row_values[1], '%m/%d/%Y').date(), in_hour)
                    in_hour_datetime = in_hour_datetime - timedelta(hours=server_hour_difference)
                else:
                    in_hour = None  # O algún valor predeterminado o manejo especial

                if out_time_str:
                    out_hour = datetime.strptime(out_time_str, '%H:%M').time()
                    out_hour_datetime = datetime.combine(datetime.strptime(row_values[1], '%m/%d/%Y').date(), out_hour)
                    out_hour_datetime = out_hour_datetime - timedelta(hours=server_hour_difference)
                else:
                    out_hour = None
                date = datetime.strptime(row_values[1], '%m/%d/%Y').date()

                self.env['assistance.importer.line'].create({
                    'name': name,
                    'employee_id': employee_id.id if employee_id else False,
                    'din_hour': in_hour_datetime,
                    'dout_hour': out_hour_datetime,
                    'assistance_importer_id': self.id,
                })


        if self.type == 'zktime-3':
            try:
                workbook = xlrd.open_workbook(file_contents=base64.b64decode(self.file))
            except Exception as e:
                _logger.error(e)
                self.state = 'error'
                return False

            server_hour_difference = self.env.company.server_hour_difference
            sheet = workbook.sheet_by_index(0)
            for row in range(1, sheet.nrows):
                row_values = sheet.row_values(row)
                _code_bim = row_values[1]
                _fecha = row_values[2]
                _TipClockIn = row_values[5]
                _TipClockOut = row_values[7]


                if _code_bim not in ['Nombre Completo', 'ID de Usuario', 'Departamento', '','Total de Tiempo Laboral','Revisado por']:
                    employee_id = self.env['hr.employee'].search([('code_bim', '=', _code_bim)], limit=1)
                    if employee_id:
                        if not _TipClockIn == '':
                            in_hour = datetime.strptime(_TipClockIn, '%H:%M').time()
                            in_hour_datetime = datetime.combine(datetime.strptime(_fecha, '%m/%d/%Y').date(), in_hour)
                            in_hour_datetime = in_hour_datetime - timedelta(hours=server_hour_difference)

                        if not _TipClockOut == '':
                            out_hour = datetime.strptime(_TipClockOut, '%H:%M').time()
                            out_hour_datetime = datetime.combine(datetime.strptime(_fecha, '%m/%d/%Y').date(), out_hour)
                            out_hour_datetime = out_hour_datetime - timedelta(hours=server_hour_difference)

                        if not _TipClockIn == '' and not _TipClockOut == '':
                            self.env['assistance.importer.line'].create({
                                'name': _code_bim,
                                'employee_id': employee_id.id,
                                'din_hour': in_hour_datetime if not _TipClockIn == '' else False,
                                'dout_hour': out_hour_datetime if not _TipClockOut == '' else False,
                                'assistance_importer_id': self.id,
                            })






        self.state = 'imported'
        return True

    def insert_hr_attendance(self):
        for line in self.line_ids:
            project_id = line.employee_id.default_bim_project
            cost = line.employee_id.hour_cost

            if line.hr_attendance_id:
                line.hr_attendance_id.write({
                    'check_in': line.din_hour,
                    'check_out': line.dout_hour,
                })
            else:
                hr_attendance_id = self.env['hr.attendance'].create({
                    'employee_id': line.employee_id.id,
                    'check_in': line.din_hour,
                    'check_out': line.dout_hour,
                })
                line.hr_attendance_id = hr_attendance_id.id
        self.state = 'inserted'
        return True

    def to_draft(self):
        if self.state != 'imported':
            for l in self.line_ids:
                l.hr_attendance_id.unlink()
        self.state = 'draft'
        return True

class AssistanceImporterLine(models.Model):
    _description = "Assistance Importer Line"
    _name = 'assistance.importer.line'

    name = fields.Char('Code')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    din_hour = fields.Datetime('In Hour')
    dout_hour = fields.Datetime('Out Hour')
    assistance_importer_id = fields.Many2one('assistance.importer', string='Assistance Importer')
    hr_attendance_id = fields.Many2one('hr.attendance', string='Attendance')