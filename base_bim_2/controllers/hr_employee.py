import jinja2
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo import models, fields, _
import werkzeug
import werkzeug.utils
import json
import base64
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)
loader = jinja2.PackageLoader('odoo.addons.base_bim_2', 'web')
env = jinja2.Environment(loader=loader, autoescape=True)


class HrEmployeeWeb(http.Controller):
    # login with bim_user and bim_password in hr.employee
    @http.route('/bim/employee/login', type='json', auth='public', cors='*')
    def employee_login(self, **kwargs):
        _logger.info(f"begin employee_login: {kwargs}")
        user = kwargs.get('bim_user')
        password = kwargs.get('bim_password')

        _logger.info(f"searching employee with email: {user}")
        _logger.info(f"searching employee with password: {password}")

        employee_id = http.request.env['hr.employee'].sudo().search([
            ('bim_user', '=', user),
            ('bim_password', '=', password),
        ], limit=1)

        # obtengo su compañia
        company_id = employee_id.company_id if employee_id else None

        _logger.info(f"company found: {company_id.id if company_id else 'none'}")

        # busco todos los proyectos de esa compañia
        bim_project_ids = http.request.env['bim.project'].sudo().search([
            ('company_id', '=', company_id.id),
        ]) if company_id else http.request.env['bim.project'].sudo().browse([])

        _logger.info(f"bim projects found: {[project.id for project in bim_project_ids]}")

        if employee_id:
            _logger.info(f"employee found: {employee_id.id}")
            return {
                'status': 'ok',
                'employee_id': employee_id.id,
                'employee_name': employee_id.name,
                'company_id': company_id.id if company_id else None,
                'company_name': company_id.name if company_id else None,
                'bim_projects': [{
                    'id': project.id,
                    'name': project.name,
                } for project in bim_project_ids],
            }
        else:
            _logger.info(f"employee not found")
            return {
                'status': 'error',
                'message': 'Invalid credentials',
            }

        _logger.info("end employee_login")

    # change password with bim_user and old_password in hr.employee
    @http.route('/bim/employee/change-password', type='json', auth='public', cors='*')
    def change_employee_password(self, **kwargs):
        _logger.info(f"change_employee_password: {kwargs}")
        user = kwargs.get('bim_user')
        old_password = kwargs.get('old_password')
        new_password = kwargs.get('new_password')

        employee_id = http.request.env['hr.employee'].sudo().search([
            ('bim_user', '=', user),
            ('bim_password', '=', old_password),
        ], limit=1)

        if employee_id:
            employee_id.sudo().write({
                'bim_password': new_password,
            })
            _logger.info(f"password changed for employee: {employee_id.id}")
            return {
                'status': 'ok',
                'message': 'Password changed successfully',
            }
        else:
            _logger.info(f"employee not found or old password incorrect")
            return {
                'status': 'error',
                'message': 'Invalid credentials',
            }

    # Check login o out of employee
    # es para saber que botón mostrar en la app movil
    @http.route('/bim/employee/check-attendance', type='json', auth='public', cors='*')
    def check_employee_attendance(self, **kwargs):
        _logger.info(f"check_employee_attendance: {kwargs}")
        employee_id = kwargs.get('employee_id')

        hr_employee = http.request.env['hr.employee'].sudo().browse(employee_id)
        if not hr_employee:
            return {
                'status': 'error',
                'message': 'Employee not found',
            }

        today = date.today()
        attendance_id = http.request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', hr_employee.id),
            ('check_in', '>=', str(today)),
            ('check_in', '<', str(today + timedelta(days=1))),
        ], limit=1)

        if attendance_id and not attendance_id.check_out:
            _logger.info(f"employee {hr_employee.id} is checked in")
            return {
                'status': 'ok',
                'checked_in': True,
            }
        else:
            _logger.info(f"employee {hr_employee.id} is checked out")
            return {
                'status': 'ok',
                'checked_in': False,
            }


    # creamos un enpdpoint para listar todas las asistencias de un empleado
    @http.route('/bim/employee/attendances', type='json', auth='public', cors='*')
    def list_employee_attendances(self, **kwargs):
        _logger.info(f"list_employee_attendances: {kwargs}")
        employee_id = kwargs.get('employee_id')

        hr_employee = http.request.env['hr.employee'].sudo().browse(employee_id)
        if not hr_employee:
            return {
                'status': 'error',
                'message': 'Employee not found',
            }

        attendance_ids = http.request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', hr_employee.id),
        ], order='check_in desc')

        attendances = []
        for attendance in attendance_ids:
            attendances.append({
                'id': attendance.id,
                'check_in': attendance.check_in,
                'check_out': attendance.check_out,
                'project_id': attendance.project_id.id if attendance.project_id else None,
                'project_name': attendance.project_id.name if attendance.project_id else None,
            })

        return {
            'status': 'ok',
            'attendances': attendances,
        }



    # Registrar asistencia diaria del empleado
    # si ese empleado no tiene una asistencia para el dia de hoy, crearla
    # si ya tiene una asistencia para el dia de hoy, actualizarla
    @http.route('/bim/employee/attendance', type='json', auth='public', cors='*')
    def employee_attendance(self, **kwargs):
        _logger.info(f"employee_attendance: {kwargs}")
        employee_id = kwargs.get('employee_id')
        check_in = kwargs.get('check_in')
        check_out = kwargs.get('check_out')
        project = kwargs.get('project')

        hr_employee = http.request.env['hr.employee'].sudo().browse(employee_id)
        if not hr_employee:
            return {
                'status': 'error',
                'message': 'Employee not found',
            }

        today = date.today()
        attendance_id = http.request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', hr_employee.id),
            ('check_in', '>=', str(today)),
            ('check_out', '=', False)
        ], limit=1)

        if attendance_id:
            # actualizar asistencia existente
            attendance_id.sudo().write({
                'check_out': check_out,
            })
            _logger.info(f"attendance updated for employee: {hr_employee.id}")
        else:
            # crear nueva asistencia

            hr_attendance = http.request.env['hr.attendance'].sudo().create({
                'employee_id': hr_employee.id,
                'check_in': check_in,
                'check_out': check_out,
            })

            if project:
                bim_project = http.request.env['bim.project'].sudo().browse(project)
                if bim_project:
                    hr_attendance.sudo().write({
                        'project_id': bim_project.id,
                    })

            _logger.info(f"attendance created for employee: {hr_employee.id}")

        return {
            'status': 'ok',
            'message': 'Attendance recorded successfully',
        }