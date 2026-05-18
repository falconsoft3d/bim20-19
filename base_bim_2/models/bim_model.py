# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import requests
import json
import logging
_logger = logging.getLogger(__name__)
import base64
import os

class BimModel(models.Model):
    _name = 'bim.model'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Model'
    _order = 'id desc'

    name = fields.Char("Name", required=True, tracking=True)
    url = fields.Char("URL", compute='_compute_url', store=True)
    description = fields.Text("Description")
    bim_bucket_id = fields.Many2one('bim.bucket', "Bim Bucket", required=True)
    urn = fields.Char("URN")
    urn2 = fields.Char("URN 2")

    attachment_name = fields.Char("Attachment Name")
    attachment = fields.Binary(
        string='Attachment',
        copy=False,
        help='Attachment')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('uploaded', 'Uploaded'),
        ('uploaded', 'Uploaded'),
        ('derived', 'Derived'),
        ('status', 'Status'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ], string='State', default='draft',
    tracking=True,
    readonly=True)

    line_ids = fields.One2many('bim.model.line', 'model_id', "Lines")
    data = fields.Text("Data")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.onchange('attachment_name')
    def _onchange_attachment_name(self):
        if self.name == '':
            self.name = self.attachment_name


    @api.depends('urn2')
    def _compute_url(self):
        for record in self:
            if record.urn2:
                param_web_base_url = record.env['ir.config_parameter'].sudo().get_param('web.base.url')
                record.url = param_web_base_url + '/bim/docs/model/' + str(record.urn2)

    def upload_model(self):
        for record in self:
            _logger.info("upload_model BimModel")
            access_token = self.bim_bucket_id.bim_server_id.get_token()
            bucket_key = self.bim_bucket_id.name

            # codifico el archivo
            _attachment64 = base64.b64decode(self.attachment)

            # Guardo el archivo en un directorio temporal
            file_path = os.path.join('/tmp', self.attachment_name)

            try:
                # Guardar el archivo temporalmente
                with open(file_path, 'wb') as file:
                    file.write(_attachment64)

                # Asegurarse de que el archivo se guardó correctamente
                if not os.path.exists(file_path):
                    raise UserError(_("El archivo no se ha guardado correctamente en el directorio temporal."))

                else:
                    record.message_post(body="Archivo guardado correctamente en el directorio temporal.")

                file_size = os.path.getsize(file_path)
                _logger.info("file_size: %s", file_size)

                # Configurar la URL de subida y los encabezados
                upload_url = f'https://developer.api.autodesk.com/oss/v2/buckets/{bucket_key}/objects/{self.attachment_name}'
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/x-3ds'  # Tipo de contenido adecuado para archivos .3ds
                }

                # Subir el archivo a Forge
                with open(file_path, 'rb') as file_data:
                    _logger.info("file_data: %s", file_data)
                    response = requests.put(upload_url, headers=headers, data=file_data)

                # Verificar la respuesta de Forge
                if response.status_code == 200:
                    response_data = response.json()
                    record.urn = response_data.get('objectId')
                    record.message_post(body=response.text)
                    record.state = 'uploaded'
                    _logger.info("Archivo subido correctamente: %s", response_data.get('objectId'))
                    record.message_post(body="Archivo subido correctamente.")
                else:
                    _logger.error("Error al subir el archivo a Forge: %s", response.text)
                    record.message_post(body=response.text)
                    raise UserError(_("Error al subir el archivo a Forge: ") + response.text)

            except Exception as e:
                _logger.error("Error en la subida del archivo: %s", str(e))
                raise UserError(_("Error en la subida del archivo: ") + str(e))


    def derive_model(self):
        for record in self:
            _logger.info("derive_model")
            access_token = self.bim_bucket_id.bim_server_id.get_token()
            urn_encoded = base64.b64encode(record.urn.encode('utf-8')).decode('utf-8')

            derivative_url = record.bim_bucket_id.bim_server_id.url + "modelderivative/v2/designdata/job"
            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

            # Datos para derivar el archivo al formato SVF (para visualización en 2D y 3D)
            data = {
                "input": {
                    "urn": urn_encoded
                },
                "output": {
                    "formats": [
                        {
                            "type": "svf",
                            "views": ["2d", "3d"]
                        }
                    ]
                }
            }

            response = requests.post(derivative_url, json=data, headers=headers)
            record.message_post(body=response.text)
            record.urn2 = response.json()['urn']
            record.state = 'derived'

    def status_derive_model(self):
        for record in self:
            _logger.info("status_derive_model")
            access_token = record.bim_bucket_id.bim_server_id.get_token()

            urn = record.urn
            urn_encoded = base64.b64encode(urn.encode('utf-8')).decode('utf-8')

            status_url = record.bim_bucket_id.bim_server_id.url + f"modelderivative/v2/designdata/{urn_encoded}/manifest"
            headers = {'Authorization': f'Bearer {access_token}'}

            response = requests.get(status_url, headers=headers)
            record.message_post(body=response.text)
            record.state = 'status'


            try:
                record.urn2 = response.json()['urn']
                status = response.json()['status']
                if status == 'success':
                    record.state = 'done'
                elif status == 'failed':
                    record.state = 'failed'
            except Exception as e:
                record.state = 'failed'
                raise UserError(e)

            return response.json()['status']


    def set_draft(self):
        for record in self:
            record.state = 'draft'


    def delete_model(self):
        for record in self:
            _logger.info("delete_model")
            access_token = record.bim_bucket_id.bim_server_id.get_token()
            urn = record.urn
            urn_encoded = base64.b64encode(urn.encode('utf-8')).decode('utf-8')

            delete_url = record.bim_bucket_id.bim_server_id.url + f"oss/v2/buckets/{record.bim_bucket_id.name}/objects/{record.attachment_name}"
            headers = {'Authorization': f'Bearer {access_token}'}

            response = requests.delete(delete_url, headers=headers)
            record.message_post(body=response.text)
            record.state = 'draft'

            return response.text


    def load_data(self):
        # limpiamos las líneas
        for record in self:
            record.line_ids.unlink()

        # Obtener el token de acceso
        access_token = record.bim_bucket_id.bim_server_id.get_token()

        # Codificar el URN en Base64
        urn = record.urn
        urn_encoded = base64.b64encode(urn.encode('utf-8')).decode('utf-8')

        # URL para obtener los metadatos del modelo
        metadata_url = f"{record.bim_bucket_id.bim_server_id.url}/modelderivative/v2/designdata/{urn_encoded}/metadata"
        headers = {'Authorization': f'Bearer {access_token}'}

        # Realizar la solicitud para obtener los metadatos
        response = requests.get(metadata_url, headers=headers)
        if response.status_code != 200:
            _logger.error(f"Error al cargar los metadatos: {response.status_code} - {response.text}")
            raise UserError(_("Error al cargar los metadatos: ") + response.text)

        metadata = response.json()
        _logger.info(f"Metadatos obtenidos: {metadata}")

        # Obtener el 'metadataId' para acceder a las propiedades de los objetos
        metadata_id = metadata['data']['metadata'][0]['guid']  # Asumimos que el primer 'guid' es el que queremos
        properties_url = f"{record.bim_bucket_id.bim_server_id.url}/modelderivative/v2/designdata/{urn_encoded}/metadata/{metadata_id}/properties"

        # Realizar la solicitud para obtener las propiedades de los objetos
        response = requests.get(properties_url, headers=headers)
        if response.status_code != 200:
            _logger.error(f"Error al cargar las propiedades de los objetos: {response.status_code} - {response.text}")
            raise UserError(_("Error al cargar las propiedades de los objetos: ") + response.text)

        # Verificar si 'objects' está en la respuesta
        properties = response.json()

        # recorremos las propiedades de los objetos
        for obj in properties['data']['collection']:
            obj_name = obj['objectid']
            obj_properties = obj['properties']
            _logger.info(f"Objeto: {obj_name}")
            _logger.info(f"Propiedades: {obj_properties}")

            # Recorremos las propiedades de cada objeto
            for prop in obj_properties:
                _logger.info(f"Propiedad: {prop}")
                """
                Propiedades: {'Construction':
                                {'Structure': '', 'Wrapping at Inserts': 'Do not wrap', 'Wrapping at Ends': 'Interior', 'Width': '0.200 m', 'Function': 'Exterior'},
                                'Graphics': {'Coarse Scale Fill Pattern': '', 'Coarse Scale Fill Color': '0'},
                                'Identity Data': {'Type Image': '', 'Keynote': '', 'Model': '', 'Manufacturer': '', 'Type Comments': '', 'URL': '', 'Description': '', 'Assembly Description': '', 'Assembly Code': '', 'Type Mark': '', 'Fire Rating': '', 'Cost': '0.000 ฿'},
                                'Materials and Finishes': {'Structural Material': 'Ceramic Tile'},
                                'Analytical Properties': {'Heat Transfer Coefficient (U)': '6.000 W/(m²·K)', 'Thermal Resistance (R)': '0.167 (m²·K)/W', 'Thermal Mass': '340.000 autodesk.unit.unit:kilojoulesPerSquareMeterKelvin-1.0.0', 'Absorptance': '0.700', 'Roughness': '3'}
                                }
                """
                area = 0
                volume = 0
                perimeter = 0
                thickness = 0

                # Obtenemos el área del objeto
                if 'Area' in prop:
                    area = prop['Area']
                if 'Volume' in prop:
                    volume = prop['Volume']
                if 'Perimeter' in prop:
                    perimeter = prop['Perimeter']
                # Obtenemos el espesor del objeto
                if 'Thickness' in prop:
                    thickness = prop['Thickness']

                # Creamos una línea en el modelo con las dimensiones del objeto si no existe
                if not record.line_ids.filtered(lambda r: r.name == obj_name):
                    record.line_ids.create({
                        'name': obj_name,
                        'area': area,
                        'volume': volume,
                        'perimeter': perimeter,
                        'thickness': thickness,
                        'model_id': record.id
                    })
                else:
                    record.line_ids.filtered(lambda r: r.name == obj_name).write({
                        'area': area,
                        'volume': volume,
                        'perimeter': perimeter,
                        'thickness': thickness,
                    })



        record.data = response.text

class BimModelLine(models.Model):
    _name = 'bim.model.line'
    _description = 'Bim Model Line'

    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    area = fields.Float("Area")
    volume = fields.Float("Volume")
    perimeter = fields.Float("Perimeter")
    thickness = fields.Float("Thickness")
    model_id = fields.Many2one('bim.model', "Model")
    bim_concept_template_id = fields.Many2one('bim.concept.template', "Concept Template")



