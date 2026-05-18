# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CauseLostHour(models.Model):
    _description = "Cause Lost Hour"
    _name = 'cause.lost.hour'
    _order = "id desc"

    name = fields.Char('Name', copy=False)