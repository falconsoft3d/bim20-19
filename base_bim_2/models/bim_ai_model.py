# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
try:
    from openai import OpenAI
    openai_installed = True
except ImportError:
    openai_installed = False

class BimAiModel(models.Model):
    _description = "Bim Ai Model"
    _name = 'bim.ai.model'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Selection([
                                ('gpt-4o-mini', 'gpt-4o-mini'),
                                ('gpt-5', 'gpt-5'),
                                ('deepseek-chat', 'deepseek-chat'),
                            ], string='Model', default='gpt-4o-mini')

    key = fields.Char('Key')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)

    def do_test_connection(self):
        self.ensure_one()
        if not self.key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('API Key Missing'),
                    'message': _('Please set the API key before testing the connection.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }

        output_text = ""
        notif_type = "success"
        notif_title = _("Connection Successful")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.key)

            response = client.chat.completions.create(
                model=self.name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Dime si estas conectado"}
                ]
            )

            # Acceder al contenido
            if response and response.choices:
                output_text = response.choices[0].message.content
            else:
                output_text = _("No se recibió respuesta del modelo.")

        except Exception as e:
            notif_type = "danger"
            notif_title = _("Connection Failed")
            output_text = str(e)


        # escribimos en chatter
        _text = _("Test de conexión al modelo AI '%s':\n%s") % (self.name, output_text)
        self.message_post(body=_text)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': notif_title,
                'message': output_text,
                'type': notif_type,
                'sticky': False,
            }
        }