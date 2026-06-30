import base64
import os
import json
import logging
import requests
from odoo import api
from odoo import fields, models, _
from io import BytesIO
import xlwt
_logger = logging.getLogger(__name__)

TEMPLATE_LINE_TYPES = {
    'M': '3',
    'H': '4',
    'Q': '5',
    'A': '6',
}

CONCEPT_TYPES = {
    'chapter': '1',
    'departure': '2',
    'material': '3',
    'labor': '4',
    'equip': '5',
    'aux': '6',
}


class BimConceptTemplateCopy(models.TransientModel):
    _name = 'bim.concept.template.copy'
    _description = 'Bim Concept Template Copy'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    concept_template_ids = fields.Many2many('bim.concept.template', string='APUs')
    concept_bim_concept_ids = fields.Many2many('bim.concepts', string='Departures')
    copy_bim_budget_ids = fields.Many2many('bim.budget', string='Budgets')

    @api.model
    def default_get(self, fields):
        res = super(BimConceptTemplateCopy, self).default_get(fields)

        if self._context.get('active_model') == 'bim.concept.template':
            if self._context.get('active_ids'):
                res.update({'concept_template_ids': [(6, 0, self._context.get('active_ids'))]})

        if self._context.get('active_model') == 'bim.concepts':
            if self._context.get('active_ids'):
                res.update({'concept_bim_concept_ids': [(6, 0, self._context.get('active_ids'))]})

        if self._context.get('active_model') == 'bim.budget':
            if self._context.get('active_ids'):
                res.update({'copy_bim_budget_ids': [(6, 0, self._context.get('active_ids'))]})

        return res


    def copy_concept(self):
        _logger.info('copy_concept')

        # APU
        for concept_template in self.concept_template_ids:
            self.user_id.concept_template_ids = [(4, concept_template.id)]

        # Partidas
        for concept in self.concept_bim_concept_ids:
            self.user_id.concept_bim_concept_ids = [(4, concept.id)]

        # Presupuestos
        for budget in self.copy_bim_budget_ids:
            self.user_id.copy_bim_budget_ids = [(4, budget.id)]


