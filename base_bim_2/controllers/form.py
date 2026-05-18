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

class BimWeb(http.Controller):
    @http.route('/bim_report_sql/<token>', methods=['GET'], cors='*', auth='public')
    def bim_report_sql(self, **kwargs):
        token = kwargs.get('token')
        report_id = http.request.env['bim.sql.report'].sudo().search([
            ('token', '=', token),
        ], limit=1)

        if not report_id:
            return http.request.make_response(
                headers=[('Content-Type', 'application/json')],
                data=json.dumps({'error': 'No data'}, indent=4),
                cookies={'token': token}
            )
        else:
            if report_id.type == 'sql':
                _logger.info("bim_report_sql : SQL")
                response = report_id.get_json_report()

                # Serialización personalizada para manejar fechas
                def custom_serializer(obj):
                    if isinstance(obj, date):
                        return obj.isoformat()  # Convierte el objeto date a formato ISO (YYYY-MM-DD)
                    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

                # Imprimimos un json con las líneas
                return http.request.make_response(
                    headers=[('Content-Type', 'application/json')],
                    data=json.dumps(response, indent=4, default=custom_serializer),  # Usamos 'default' para manejar fechas
                    cookies={'token': token}
                )

            elif report_id.type == 'apus':
                _logger.info("bim_report_sql : apus")
                templates = http.request.env['bim.concept.template'].sudo().search([
                    ('company_id', '=', report_id.company_id.id)
                ])

                data = {
                    'name': 'apus',
                }

                for t in templates:
                    # insertamos un nodo por cada concepto con todos sus campos
                    data[t.code] =  t.read()[0] if t else {}
                    # leemos las líneas del concepto
                    lines = http.request.env['bim.concept.template.line'].sudo().search([
                        ('template_id', '=', t.id)
                    ])
                    data[t.code]['template_line_ids'] = lines.read() if lines else []

                json_data = [data]
                return http.request.make_response(
                    headers=[('Content-Type', 'application/json')],
                    data=json.dumps(json_data, indent=4, default=str),
                    cookies={'token': token}
                )


            elif report_id.type == 'project':
                _logger.info("bim_report_sql : project")
                # Obtener el proyecto como registro Odoo
                project = report_id.project_id
                # Serializar el proyecto a un diccionario usando el método read
                data = project.read()[0] if project else {}
                # quitamos el campo image_1920 que es muy grande
                if 'image_1920' in data:
                    data['image_1920'] = False
                if 'image_1024' in data:
                    data['image_1024'] = False
                if 'image_512' in data:
                    data['image_512'] = False
                if 'image_256' in data:
                    data['image_256'] = False
                if 'image_128' in data:
                    data['image_128'] = False
                json_data = [{"project": data}]
                return http.request.make_response(
                    headers=[('Content-Type', 'application/json')],
                    data=json.dumps(json_data, indent=4, default=str),
                    cookies={'token': token}
                )

            else:
                _logger.info("bim_report_sql : budget")
                budget = report_id.budget_id
                # Serializar el proyecto a un diccionario usando el método read
                # lee solo el presupuesto
                data = budget.read()[0] if budget else {}

                # abrimos el nodo concept_ids que biene de bim.concepts para ese budget_id
                concepts = http.request.env['bim.concepts'].sudo().search([
                    ('budget_id', '=', budget.id)
                ])
                data['concept_ids'] = concepts.read() if concepts else []
                json_data = [{"budget": data}]
                return http.request.make_response(
                    headers=[('Content-Type', 'application/json')],
                    data=json.dumps(json_data, indent=4, default=str),
                    cookies={'token': token}
                )

    @http.route('/bim/form/<key>', methods=['GET'],  cors='*', auth='public')
    def get_form(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        campaign = http.request.env['bim.marketing.campaign'].sudo().search([
            ('key', '=', kwargs.get('key')),
            ('active', '=', True),
        ], limit=1)

        if campaign:
            return env.get_template('contact.html').render({
                'csrf_token': http.request.csrf_token(),
                'campaign': campaign,
            })



    @http.route('/bim/form/save', type='json', auth='public', cors='*')
    def save_form(self, **kwargs):
        ok = True
        my_current_url = request.session.get('my_current_url')
        name = kwargs.get('name')
        email = kwargs.get('email')
        phone = kwargs.get('phone')
        text = kwargs.get('text')
        campaign = kwargs.get('campaign')

        if campaign:
            campaign_id = http.request.env['bim.marketing.campaign'].sudo().search([
                ('id', '=', campaign)
            ], limit=1)
            if campaign_id:
                if campaign_id.type == 'contact':
                    partner_id = http.request.env['res.partner'].sudo().search([
                        ('email', '=', email)
                    ], limit=1)

                    vals = {
                        'name': name,
                        'email_from': email,
                        'phone': phone,
                        'description': text,
                        'company_id': campaign_id.company_id.id,
                        'user_id' : campaign_id.user_id.id,
                        'partner_id': partner_id.id if partner_id else False,
                        'campaign_id': campaign_id.utm_campaign_id.id if campaign_id.utm_campaign_id else False,
                        'referred': campaign_id.key,
                    }
                    lead_id = http.request.env['crm.lead'].sudo().create(vals)

                if campaign_id.type == 'ticket':
                    partner_id = http.request.env['res.partner'].sudo().search([
                        ('email', '=', email)
                    ], limit=1)

                    vals = {
                        'title': campaign_id.name + ' - ' + name,
                        'user_id' : campaign_id.user_id.id,
                        'obs': text,
                        'company_id': campaign_id.company_id.id,
                        'project_id': campaign_id.bim_project_id.id if campaign_id.bim_project_id else False,
                        'category_id': http.request.env['ticket.bim.category'].sudo().search([], limit=1).id,
                    }
                    lead_id = http.request.env['ticket.bim'].sudo().create(vals)

                if campaign_id.type == 'mant':
                    partner_id = http.request.env['res.partner'].sudo().search([
                        ('email', '=', email)
                    ], limit=1)

                    vals = {
                        'description': "Formulario de contacto",
                        'observation': text,
                        'requested_by': name,
                        'requested_email': email,
                        'requested_phone': phone,
                        'company_id': campaign_id.company_id.id,
                        'user_id' : campaign_id.user_id.id,
                        'partner_id': partner_id.id if partner_id else False,
                        'reference': campaign_id.key,
                    }
                    lead_id = http.request.env['maintenance.work.request'].sudo().create(vals)

        if ok:
            return {
                'status': 'ok',
            }
        else:
            return {
                'status': 'error',
            }

    @http.route('/bim/survey/<key>', methods=['GET'],  cors='*', auth='public')
    def get_survey(self, **kwargs):
        my_current_url = request.session.get('my_current_url')
        user = kwargs.get('user_id')
        template_id = http.request.env['customer.question.template'].sudo().search([
            ('key', '=', kwargs.get('key')),
            ('active', '=', True),
        ], limit=1)

        if template_id:
            return env.get_template('survey.html').render({
                'csrf_token': http.request.csrf_token(),
                'template_id': template_id,
            })


    @http.route('/bim/survey/save', type='json', auth='public', cors='*')
    def save_survey(self, **kwargs):
        ok = False

        my_current_url = request.session.get('my_current_url')
        name = kwargs.get('name')
        de = kwargs.get('de')
        template = kwargs.get('template_id')
        radioData = kwargs.get('radioData')

        print(radioData)

        template_id = http.request.env['customer.question.template'].sudo().search([
                ('id', '=', template)
            ], limit=1)

        if template_id:
            vals = {
                'customer': name,
                'from_customer': de,
                'state': 'done',
                'customer_question_template_id': template_id.id,
                'project_id' : template_id.project_id.id,
                'budget_id' : template_id.budget_id.id,
                'bim_concepts' : template_id.bim_concepts.id,
                'company_id': template_id.company_id.id,
            }
            survey_id = http.request.env['customer.survey'].sudo().create(vals)
            if survey_id:
                lines_ids = []

                for radio in radioData:
                    radio_i = radio['id']
                    print(radio['id'])

                    if "YNinlineRadio" in radio_i:
                        array_radio = radio_i.split('-')
                        line = array_radio[2]
                        value = 1 if array_radio[1] == 'Yes' else 0

                        customer_question_template_line_id = http.request.env['customer.question.template.line'].sudo().search([
                            ('id', '=', line)
                        ], limit=1)
                        customer_question_id = customer_question_template_line_id.name.id
                        line  = {
                            'survey_id': survey_id.id,
                            'name': customer_question_id,
                            'value': value,
                        }
                        lines_ids.append(line)

                    else:
                        array_radio = radio_i.split('-')
                        line = array_radio[1]
                        value = array_radio[2]

                        customer_question_template_line_id = http.request.env['customer.question.template.line'].sudo().search([
                            ('id', '=', line)
                        ], limit=1)
                        customer_question_id = customer_question_template_line_id.name.id
                        line  = {
                            'survey_id': survey_id.id,
                            'name': customer_question_id,
                            'value': value,
                        }

                        lines_ids.append(line)

                survey_id.write({
                      'lines_ids': [(0, 0, line) for line in lines_ids],
                   })



        if ok:
            return {
                'status': 'ok',
            }
        else:
            return {
                'status': 'error',
            }
