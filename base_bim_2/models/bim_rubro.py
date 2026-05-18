# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class BimRubro(models.Model):
    _description = "Bim Product Group"
    _name = 'bim.rubro'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    parent_id = fields.Many2one('bim.rubro', 'Parent Rubro')
    type = fields.Selection([
        ('rubro', 'Rubro'),
        ('subrubro', 'Subrubro'),
    ], string='Type', required=True, default='rubro', compute='_compute_type', store=True)

    @api.depends('parent_id')
    def _compute_type(self):
        if self.parent_id:
            self.type = 'subrubro'
        else:
            self.type = 'rubro'

    @api.depends('code','name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s %s" % (record.code, record.name)