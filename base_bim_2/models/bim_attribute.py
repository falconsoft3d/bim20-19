# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class BimAttribute(models.Model):
    _name = 'bim.attribute'
    _description = 'Bim Attribute'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    show = fields.Boolean(default=True)
    value_ids = fields.One2many('bim.attribute.value', 'attribute_id')
    parent_id = fields.Many2one('bim.attribute', string='Parent', ondelete='cascade')


class BimAttributeValue(models.Model):
    _name = 'bim.attribute.value'
    _description = 'Bim Attribute Value'

    attribute_id = fields.Many2one('bim.attribute', ondelete='cascade')
    name = fields.Char(required=True, translate=True)
    sequence = fields.Float('Sequence', default=1)



