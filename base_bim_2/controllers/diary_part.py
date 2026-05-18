import jinja2
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo import models, fields, _
import werkzeug
import werkzeug.utils
import json
import base64
from datetime import date
import logging
_logger = logging.getLogger(__name__)

loader = jinja2.PackageLoader('odoo.addons.base_bim_2', 'web')
env = jinja2.Environment(loader=loader, autoescape=True)

class DiaryPartWeb(http.Controller):

    @http.route('/bim/diary-part/save-matriz', type='json', auth='public', cors='*')
    def save_matriz(self, **kwargs):
        ok = True
        _logger.info(f"save_matriz: {kwargs}")
        part_id = http.request.env['diary.part'].sudo().search([('id', '=', kwargs.get('part_id'))], limit=1)
        inputsData = kwargs.get('inputsData')

        for l in inputsData:
            id = l.get('id')
            employee_id = l['id'].split('-')[0]
            pcp_id = l['id'].split('-')[1]
            hh = l.get('hh')

            _args = [
               ('part_id', '=', part_id.id),
               ('bim_pcp_id', '=', int(pcp_id)),
               ('hr_employee_id', '=', int(employee_id)),
            ]
            diary_part_employee_lines_id = http.request.env['diary.part.employee.lines'].sudo().search(_args, limit=1)

            if diary_part_employee_lines_id:
                _logger.info(f"if diary_part_employee_lines_id: {diary_part_employee_lines_id}")
                diary_part_employee_lines_id.sudo().write({
                    'hh': float(hh),
                })


        if ok:
            return {
                'status': 'ok',
            }
        else:
            return {
                'status': 'error',
            }





    @http.route('/bim/diary-part/<key>', methods=['GET'],  cors='*', auth='public')
    def get_document(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        part_id = http.request.env['diary.part'].sudo().search([
            ('key', '=', kwargs.get('key')),
        ], limit=1)

        mat_pcp = []
        employees = []
        employees_c = []
        pcps = []
        for line in part_id.employee_lines_ids:
            mat_pcp.append({
                'id': line.id,
                'hr_employee_id': line.hr_employee_id,
                'bim_pcp_id' : line.bim_pcp_id,
            })
            if line.bim_pcp_id not in pcps:
                pcps.append(line.bim_pcp_id)

            if line.hr_employee_id not in employees_c:
                employees_c.append(line.hr_employee_id)

                # Buscamos todos los pcp del empleado
                diary_part_employee_lines_ids = http.request.env['diary.part.employee.lines'].sudo().search([
                    ('hr_employee_id', '=', line.hr_employee_id.id),
                    ('part_id', '=', part_id.id),
                ])

                pcp = []
                for line in diary_part_employee_lines_ids:
                    pcp.append({
                        'id': line.id,
                        'bim_pcp_id': line.bim_pcp_id,
                        'hh': line.hh,
                    })


                employees.append([line.hr_employee_id,pcp])

        _logger.info(f"employees: {employees}")

        # ordeno pcps
        pcps = sorted(pcps, key=lambda x: x.name)

        return env.get_template('diary_part.html').render({
                'csrf_token': http.request.csrf_token(),
                'part_id': part_id,
                'employees' : employees,
                'pcps' : pcps,
            })