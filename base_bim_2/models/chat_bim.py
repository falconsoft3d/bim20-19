# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json
import base64
from io import BytesIO

try:
    import random
except ImportError:
    pass
try:
    from openai import OpenAI
    openai_installed = True
except ImportError:
    openai_installed = False

from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

array_random = [
        "General",
        "Cimentacion",
        "Muros",
        "Losas",
        "Castillos",
        "Acero",
        "Carpinteria",
        "Instalaciones",
        "Pintura",
        "Aluminio",
        "Cristal",
        "Pisos",
        "Plafones",
        "Impermeabilizacion",
        "Canceleria",
        "Pavimentos",
        "Pintura",
        "Aluminio",
        "Cristal",
        "Pisos",
        "Plafones",
]



class ChatBim(models.Model):
    _description = "Chat BIM"
    _name = 'chat.bim'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    prompt = fields.Text('Prompt', translate=True, default="")
    response = fields.Text('Response', translate=True, default="")
    edit_json = fields.Text('Edit Json', translate=True, default="")

    user_id = fields.Many2one('res.users', string='Created', tracking=True,
        default=lambda self: self.env.user)
    create_date = fields.Datetime('Create Date', default=fields.Datetime.now)
    budget_id = fields.Many2one('bim.budget', string='Budget')
    prompt_sample_id = fields.Many2one('chat.bim.prompt', string='Prompt Sample')
    model_ai = fields.Selection([
        ('base', 'Base'),
        ('other', 'Other'),
    ], string='Model', default='base')

    type = fields.Selection([
        ('create', 'Create'),
        ('edit', 'Edit'),
        ('read', 'Read'),
        ('report', 'Report'),
        ('programming', 'Programming'),
    ], string='Type', default='create')

    bim_ai_model_id = fields.Many2one('bim.ai.model', string='LLM')
    create_product = fields.Boolean('Create Product', default=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ia', 'IA Ejecutada'),
        ('done', 'Ejecuted'),
        ('canceled', 'Canceled')
    ], string='State', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    max_tokens = fields.Integer('Max Tokens', default=8192)
    bim_documentation_ids = fields.One2many('bim.documentation', 'chat_bim_id', string='Documentation')
    documentation_count = fields.Integer(string='Documentation Count', compute='_compute_documentation_count')
    exit_file = fields.Binary('Exit File')

    @api.depends('bim_documentation_ids')
    def _compute_documentation_count(self):
        for record in self:
            record.documentation_count = len(record.bim_documentation_ids)


    def action_open_documentation(self):
        action = self.env.ref('base_bim_2.action_bim_documentation').sudo().read()[0]
        action['domain'] = [('chat_bim_id', '=', self.id)]
        action['context'] = {
                              'default_project_id': self.id,
                              'default_chat_bim_id': self.id,
                            }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('chat.bim') or 'New'
        return super().create(vals_list)

    @api.onchange('prompt_sample_id')
    def _onchange_prompt_sample_id(self):
        if self.prompt_sample_id:
            self.prompt = self.prompt_sample_id.prompt

    def exe_done(self):
        if not self.response:
            self.run_prompt()
            if self.type in ['create', 'edit', 'programming']:
                self.state = 'ia'
            else:
                self.state = 'done'
        else:
            self.state = 'ia'

    def exe_draft(self):
        self.state = 'draft'
        self.response = False
        self.edit_json = False
        self.exit_file = False

    def exe_cancel(self):
        self.state = 'canceled'


    def create_budget_from_json(self):
        if self.response:
            json_response = json.loads(self.response)

            # recorremos el los concepts que vienen en el json

            space_id = self.env['bim.budget.space'].search([('budget_id', '=', self.budget_id.id)], limit=1)

            for concept in json_response['concepts']:
                # revisamos si ya existe el concepto por el id_import
                concept_id = self.env['bim.concepts'].search([
                                ('code', '=',concept['code']),
                                ('budget_id', '=', self.budget_id.id)
                            ], limit=1)

                if not concept_id:
                    concept_id = self.env['bim.concepts'].create({
                        'name': concept['name'],
                        'budget_id': self.budget_id.id,
                        'type': concept['type'],
                        'code' : concept['code'],
                        'quantity' : concept['quantity'],
                        'note' : concept['note'] if 'note' in concept else '',
                        'id_import' : concept['id'],
                        'parent_id_import' : concept['parent'],
                        'acs_date_start' : concept['begin_date'] if 'begin_date' in concept else '',
                        'acs_date_end' : concept['end_date'] if 'end_date' in concept else '',
                    })

                else:
                    if self.type in ['create', 'edit']:
                        concept_id.write({
                            'quantity' : concept['quantity'],
                            'note' : concept['note'] if 'note' in concept else '',
                            'acs_date_start' : concept['begin_date'],
                            'acs_date_end' : concept['end_date'],
                        })

                    if self.type in ['programming']:
                        concept_id.write({
                            'acs_date_start' : concept['begin_date'],
                            'acs_date_end' : concept['end_date'],
                        })


                if concept['type'] == 'departure' and self.type in ['create']:
                    # reviso si tiene los x,y,z
                    if 'x' in concept and 'y' in concept and 'z' in concept:
                        bim_concept_measuting_id = self.env['bim.concept.measuring'].create({
                            'concept_id': concept_id.id,
                            'space_id': space_id.id if space_id else False,
                            'qty': 1,
                            'length': concept['x'],
                            'width': concept['y'],
                            'height': concept['z'],
                            'name': 'X:' + str(concept['x']) + ' Y:' + str(concept['y']) + ' Z:' + str(concept['z']),
                        })


                if concept_id.type in ['material', 'labor', 'equipment', 'subcontract'] and self.type in ['create']:
                    concept_id.write({
                        'amount_fixed' : concept['price'],
                    })

                    # buscamos si existe el producto por el nombre o por el codigo
                    product_id = self.env['product.product'].search([
                        ('name', '=', concept['name'])
                    ], limit=1)

                    if not product_id:
                        product_id = self.env['product.product'].search([
                            ('default_code', '=', concept['code'])
                        ], limit=1)

                    if not product_id and self.create_product:
                        if concept['type'] == 'material':
                            product_id = self.env['product.product'].create({
                                'name': concept['name'],
                                'type': 'product',
                                'default_code': concept['code'],
                                'standard_price': concept['price'],
                                'resource_type': 'M',
                            })
                        if concept['type'] == 'labor':
                            product_id = self.env['product.product'].create({
                                'name': concept['name'],
                                'type': 'service',
                                'standard_price': concept['price'],
                                'resource_type': 'H',
                            })

                        if concept['type'] == 'equip':
                            product_id = self.env['product.product'].create({
                                'name': concept['name'],
                                'type': 'service',
                                'standard_price': concept['price'],
                                'resource_type': 'Q',
                            })

                        if concept['type'] == 'subcontract':
                            product_id = self.env['product.product'].create({
                                'name': concept['name'],
                                'type': 'service',
                                'standard_price': concept['price'],
                                'resource_type': 'S',
                            })

                    if product_id:
                        concept_id.write({
                            'product_id' : product_id.id,
                        })


                if concept_id.type == 'chapter' and self.type in ['create']:
                    concept_id.write({
                        'quantity' : 1,
                    })

            if self.type == 'create':
                # Ahora vamos a recorrerlo para asignar los padres
                for concept in json_response['concepts']:
                    if concept['parent']:
                        concept_id = self.env['bim.concepts'].search([
                                        ('id_import', '=', concept['id']),
                                        ('budget_id', '=', self.budget_id.id),
                                        ('parent_id', '=', False)
                                    ], limit=1)
                        parent_id = self.env['bim.concepts'].search([
                                        ('id_import', '=', concept['parent']),
                                        ('budget_id', '=', self.budget_id.id)
                                    ], limit=1)

                        if concept_id and parent_id:
                            _logger.info("Padre: %s  --> Concepto: %s" % (parent_id.name, concept_id.name))
                            concept_id.write({'parent_id': parent_id.id})

        self.state = 'done'



    def run_prompt_base(self):
        if 'random' in prompt and 'capitulos' in prompt or 'capítulos' in prompt:
            number = 0
            for word in prompt.split():
                if word.isdigit():
                    number = int(word)
                    break
            if number > 0:
                for i in range(number):
                    bim_concepts_id = self.env['bim.concepts'].create({
                        'name': array_random[i] if i < len(array_random) else 'Capi ' + str(i),
                        'budget_id': self.budget_id.id,
                        'type': 'chapter',
                        'code' : str(i),
                    })

        if 'random' in prompt and 'partida' in prompt:
            number = 0
            for word in prompt.split():
                if word.isdigit():
                    number = int(word)
                    break
            if number > 0:
                chap = self.env['bim.concepts'].create({
                        'name': array_random[1],
                        'budget_id': self.budget_id.id,
                        'type': 'chapter',
                        'code' : '01',
                    })
                for i in range(number):
                    bim_concepts_id = self.env['bim.concepts'].create({
                        'name': array_random[i] if i < len(array_random) else 'Capi ' + str(i),
                        'budget_id': self.budget_id.id,
                        'type': 'departure',
                        'code' : "01" + str(i),
                        'parent_id' : chap.id,
                        'quantity' : 1,
                    })


        if 'random' in prompt and 'material' in prompt or 'product' in prompt:
            number = 0
            for word in prompt.split():
                if word.isdigit():
                    number = int(word)
                    break
            if number > 0:
                chap = self.env['bim.concepts'].create({
                        'name': self.name,
                        'budget_id': self.budget_id.id,
                        'type': 'chapter',
                        'code' : '01',
                    })
                for i in range(number):
                    bim_concepts_id = self.env['bim.concepts'].create({
                        'name': array_random[i] if i < len(array_random) else 'Capi ' + str(i),
                        'budget_id': self.budget_id.id,
                        'type': 'departure',
                        'code' : "01" + str(i),
                        'parent_id' : chap.id,
                        'quantity' : 1,
                    })

                    find_product_ids = self.env['product.product'].search([
                                ('type', '=', 'product'),
                                ('standard_price', '>', 0)
                                ])

                    if find_product_ids:
                        # Ramdom id
                        iranm = random.randint(0, len(find_product_ids) - 1)
                        qty_random = random.randint(1, 100)
                        p = find_product_ids[iranm]
                        bim_concepts_son_id = self.env['bim.concepts'].create({
                            'name': p.name,
                            'budget_id': self.budget_id.id,
                            'type': 'material',
                            'code' : bim_concepts_id.code + str(i),
                            'parent_id' : bim_concepts_id.id,
                            'quantity' : qty_random,
                            'product_id' : p.id,
                            'amount_fixed' : p.standard_price,
                        })


    def clear_budget_from_json(self):
        self.budget_id.concept_ids.unlink()



    def create_json_from_budget(self):
        if self.budget_id:
            json_response = {}
            for concept in self.budget_id.concept_ids:
                json_response[concept.id] = {
                    'id': concept.id,
                    'name': concept.name,
                    'type': concept.type,
                    'code': concept.code,
                    'quantity': concept.quantity,
                    'price': concept.amount_fixed,
                    'note': concept.note,
                    'performance': concept.performance,
                    'parent': concept.parent_id_import,
                    'begin_date': str(concept.acs_date_start) if concept.acs_date_start else '',
                    'end_date': str(concept.acs_date_end) if concept.acs_date_end else '',
                }
                if concept.type == 'departure':
                    # reviso si tiene los x,y,z
                    measuring = self.env['bim.concept.measuring'].search([('concept_id', '=', concept.id)], limit=1)
                    if measuring:
                        json_response[concept.id].update({
                            'x': measuring.length,
                            'y': measuring.width,
                            'z': measuring.height,
                        })

            self.edit_json = json.dumps({'concepts': list(json_response.values())}, indent=4)
            return self.edit_json



    def to_ia(self):
        self.state = 'ia'


    def run_prompt_gpt(self):
        """Ejecuta un prompt con GPT y guarda archivo si el tipo es 'report'."""
        self.ensure_one()
        prompt = self.prompt or ""
        model_name = self.bim_ai_model_id.name
        client = OpenAI(api_key=self.bim_ai_model_id.key)

        # --- 1️⃣ Agregar presupuesto si aplica ---
        if self.type in ['edit', 'read', 'report', 'programming'] and self.budget_id:
            try:
                budget_json = self.create_json_from_budget()
                prompt += f"\n\nPresupuesto actual en formato JSON:\n{budget_json}"
                prompt += "\n\nDevuelve todas las partidas, en bloques si es necesario, usando el campo 'continuar=true' si no caben todas."
            except Exception as e:
                _logger.warning("No se pudo generar JSON del presupuesto: %s", e)
                prompt += "\n\n[⚠️ No se pudo cargar el JSON del presupuesto]"

        # --- 2️⃣ Adjuntos ---
        attachments_info = []
        for doc in self.bim_documentation_ids:
            if not doc.file_01:
                continue
            try:
                decoded = base64.b64decode(doc.file_01)
                sample_text = decoded[:500].decode('utf-8', errors='ignore')
                attachments_info.append({
                    "file_name": doc.file_name or "sin_nombre",
                    "preview": sample_text
                })
            except Exception:
                attachments_info.append({
                    "file_name": doc.file_name or "sin_nombre",
                    "preview": "[Archivo binario no legible]"
                })

        user_message = prompt
        if attachments_info:
            user_message += "\n\nArchivos adjuntos:\n"
            for a in attachments_info:
                user_message += f"📎 {a['file_name']}: {a['preview'][:200]}...\n"

        _logger.info("Ejecutando modelo %s tipo %s", model_name, self.type)

        # --- 3️⃣ Elegir el formato de respuesta según el tipo ---
        response_format = None
        if self.type not in ['report','read']:
            response_format = {"type": "json_object"}  # Solo JSON si no es reporte


        # --- 4️⃣ Llamada al modelo ---
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Eres un asistente técnico especializado en presupuestos de construcción."},
                    {"role": "user", "content": user_message},
                ],
                **({"response_format": response_format} if response_format else {}),  # solo si aplica
                temperature=1,
                top_p=1,
            )

            message = response.choices[0].message.content if response.choices else ""
            self.response = message or _("Sin respuesta del modelo.")

            # --- 5️⃣ Si es reporte, guardar archivo ---
            if self.type in ['report','read']:
                try:
                    # Guardar como archivo de texto
                    buffer = BytesIO(message.encode('utf-8'))
                    self.exit_file = base64.b64encode(buffer.getvalue())
                    self.file_name = f"GPT_Report_{self.id}.txt"
                    _logger.info("Archivo de reporte guardado correctamente en exit_file")
                except Exception as e:
                    _logger.error("Error al guardar archivo de salida: %s", e)

            notif_type = "success"
            notif_title = _("Ejecución completada")
            notif_message = _("Se ejecutó el modelo %s con %s adjuntos.") % (model_name, len(attachments_info))

        except Exception as e:
            _logger.error("Error al ejecutar modelo %s: %s", model_name, e)
            notif_type = "danger"
            notif_title = _("Error en ejecución")
            notif_message = str(e)

        # --- 6️⃣ Registrar en el chatter ---
        self.message_post(body=_("Modelo %s ejecutado (%s)") % (model_name, self.type))

        # --- 7️⃣ Notificación visual ---
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': notif_title,
                'message': notif_message,
                'type': notif_type,
                'sticky': notif_type != "success",
            }
        }



    def run_prompt(self):
        begin_date_run = fields.Datetime.now()
        prompt = self.prompt
        if self.model_ai == 'base':
            self.run_prompt_base()

        if self.model_ai == 'other':
            if not openai_installed:
                raise UserError(_("OpenAI not installed"))
            else:
                client = OpenAI(api_key=self.bim_ai_model_id.key)

            if self.bim_ai_model_id.name == 'gpt-5' or self.bim_ai_model_id.name == 'gpt-4o-mini':
                self.run_prompt_gpt()


            elif self.bim_ai_model_id.name == 'deepseek-chat':
                _logger.info(self.bim_ai_model_id.name)
                client = OpenAI(api_key=self.bim_ai_model_id.key, base_url="https://api.deepseek.com")

                try:
                    # Llama a la API de chat completions
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                         stream = False,
                         response_format={
                            "type": "json_object"
                          },
                         max_tokens=self.max_tokens,
                    )

                    # Extrae y almacena el contenido de la respuesta correctamente
                    self.response = response.choices[0].message.content
                except Exception as e:
                    raise UserError(_("Error: %s") % str(e))

            else:
                _logger.info(self.bim_ai_model_id.name)
                raise UserError(_("El Modelo en Odoo No esta implementado"))

        # Escibo en el chatter el nombre del modelo
        end_date_run = fields.Datetime.now()
        tim_run = end_date_run - begin_date_run

        self.message_post(body=_("Modelo: %s ,Ejecutado en: %s") % (self.bim_ai_model_id.name, tim_run))