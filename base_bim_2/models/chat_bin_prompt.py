# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ChatBimPrompt(models.Model):
    _description = "Chat BIM Prompt"
    _name = 'chat.bim.prompt'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', copy=False)
    prompt = fields.Text('Prompt', translate=True, default="")