# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ProjectParameter(models.Model):
    _description = "Project Parameter"
    _name = 'project.parameter'
    _order = 'id desc'

    name = fields.Char(string='Name')
    value = fields.Char(string='Value')
    obs = fields.Text(string='Observations')
    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")