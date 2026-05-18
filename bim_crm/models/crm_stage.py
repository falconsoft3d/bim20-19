# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class CrmStage(models.Model):
    _inherit = 'crm.stage'

    bim_project_state_id = fields.Many2one('bim.project.state', string='BIM Project State')