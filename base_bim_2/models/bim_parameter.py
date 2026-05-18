# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimParameter(models.Model):
    _name = 'bim.parameter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Parameter'
    _rec_name = 'attribute_id'

    description = fields.Char(compute='compute_parameter_name', store=True)
    active = fields.Boolean(default=True)
    attribute_id = fields.Many2one('bim.attribute', required=True, ondelete='restrict')
    template_id = fields.Many2one('bim.concept.template', string="Concept Template" , required=True, ondelete='restrict')
    product_ids = fields.Many2many('product.product', required=True, ondelete='restrict')
    value_ids = fields.One2many('bim.parameter.value', 'parameter_id')

    _sql_constraints = [
        ('name_uniq', 'unique(attribute_id,template_id)',
         'Attribute and Concept Template Combination must be unique!')
    ]

    @api.constrains('attribute_id')
    def on_save_attribute_id(self):
        for parameter in self:
            parameter.value_ids.filtered_domain([('attribute_value_id.attribute_id','!=',parameter.attribute_id.id)]).unlink()

    @api.depends('attribute_id','template_id')
    def compute_parameter_name(self):
        for parameter in self:
            name = ''
            if parameter.attribute_id:
                name += '%s '%parameter.attribute_id.name
            if parameter.template_id:
                name += '%s ' % parameter.template_id.name
            if name == '':
                name = _("New")
            parameter.description = name


class BimParameterValue(models.Model):
    _name = 'bim.parameter.value'
    _description = 'Bim Parameter Value'
    _rec_name = 'attribute_value_id'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    parameter_id = fields.Many2one('bim.parameter', ondelete='cascade')
    attribute_id = fields.Many2one('bim.attribute', related='parameter_id.attribute_id')
    attribute_value_id = fields.Many2one('bim.attribute.value', required=True, domain="[('attribute_id','=',attribute_id)]")
    price_factor = fields.Float(digits=(10,2), default=1)
    qty_factor = fields.Float(digits=(10,2), default=1)

    @api.constrains('parameter_id')
    def on_save_parameter_id_id(self):
        for value in self:
            repeated = value.search([('parameter_id','=',value.parameter_id.id),('attribute_value_id','=',value.attribute_value_id.id),
                                     ('id','!=',value.id)])
            if repeated:
                raise UserError(_("Values can not be repeated in the same parameter!"))


class BimConceptParameterAttribute(models.Model):
    _name = 'bim.concepts.parameter.attribute'
    _description = 'Bim Concepts Parameter Attribute'

    concept_id = fields.Many2one('bim.concepts', ondelete='cascade', readonly=True)
    parameter_id = fields.Many2one('bim.parameter', required=True, readonly=True)
    parameter_value_id = fields.Many2one('bim.parameter.value', required=True, domain="[('parameter_id','=',parameter_id)]")




