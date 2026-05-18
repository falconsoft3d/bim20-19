# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
from math import ceil
from datetime import timedelta
import random
import string


class DcategoryTag(models.Model):
    _description = "Dcategory Tag"
    _name = 'dcategory.tag'
    _order = 'id desc'

    name = fields.Char('Name', required=True)

class EmployeeDcategory(models.Model):
    _description = "Employee Dcategory"
    _name = 'employee.dcategory'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Name', required=True)
    tag_ids = fields.Many2many('dcategory.tag', string='Documents')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True, copy=False)