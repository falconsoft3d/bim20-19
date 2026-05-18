# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class HrLevelStudy(models.Model):
    _name = 'hr.level.study'
    _description = 'Hr Level Study'

    name = fields.Char('Name', copy=False, required=True)