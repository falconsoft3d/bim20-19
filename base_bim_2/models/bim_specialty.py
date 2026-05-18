# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BimSpecialty(models.Model):
    _description = "Bim Specialty"
    _name = 'bim.specialty'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Name', required=True)


