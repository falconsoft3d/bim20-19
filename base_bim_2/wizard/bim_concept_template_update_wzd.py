# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class BimConceptTemplateUpdateWzd(models.TransientModel):
    _name = 'bim.concept.template.update.wzd'
    _description = 'bim.concept.template.update.wzd'

    def _get_default_concept_template(self):
        ids = self.env.context.get('active_ids', [])
        templates = self.env['bim.concept.template'].browse(ids).ids or []
        return templates

    template_ids = fields.Many2many('bim.concept.template', string='Concept Template', default=_get_default_concept_template)
    product_id = fields.Many2one('product.template', string='Resource')
    pricelist_id = fields.Many2one('product.pricelist', string='Price List')
    new_price = fields.Float('Price New', digits="BIM price")
    type_update = fields.Selection([
                                    ('cost', 'Update massive concepts templates according to current cost'),
                                    ('sale', 'Update massive concepts templates according to current price'),
                                    ('manual', 'Update bulk concepts templates manually'),
                                    ('group', 'Update bulk concepts templates by Product Group'),
                                    ('template_group', 'Update bulk concepts templates by Concept Template Group'),
                                    ], string="Type",  default='cost')
    type_price = fields.Selection([('price','Price'),('percent','Percent')], string="Type Price", default='price')
    partner_id = fields.Many2one('res.partner', string='Contact')
    group_ids = fields.Many2many('bim.product.group', string="Group")
    template_group_ids = fields.Many2many('bim.concept.template.group', string="Template Group")

    @api.onchange('type_update')
    def onchange_type_update(self):
        if self.type_update in ('group','template_group'):
            self.type_price = 'percent'

    def update_price(self):
        templates = self.template_ids
        if self.type_update == 'template_group':
                templates = templates.filtered_domain(['|',('group_id','in', self.template_group_ids.ids),('sub_group_id','in', self.template_group_ids.ids)])
        for template_id in templates:
            if self.type_update == 'cost':
                resources = template_id.template_line_ids.filtered(lambda self: self.type in ['M', 'H', 'Q'])
                for resource in resources:
                    resource.price = resource.product_id.standard_price

            elif self.type_update == 'sale':
                resources = template_id.template_line_ids.filtered(lambda self: self.type in ['M', 'H', 'Q'])
                for resource in resources:
                    resource.price = resource.product_id.lst_price

            elif self.type_update == 'manual':
                resources = template_id.template_line_ids.filtered_domain([('product_id','=', self.product_id.id)])
                if self.new_price > 0.0:
                    if self.type_price == 'price':
                        for line in resources:
                            line.write({'price': self.new_price})
                    elif self.type_price == 'percent':
                        for line in resources:
                            line.write({'price': line.price * (self.new_price/100)})
                else:
                    raise ValidationError(_('Price should be bigger than 0.0'))
            elif self.type_update == 'group':
                resources = template_id.template_line_ids.filtered_domain([('product_id.bim_group_id','in', self.group_ids.ids)])
                if self.new_price > 0.0:
                    for line in resources:
                      line.write({'price': line.price * (self.new_price/100)})
                else:
                    raise ValidationError(_('Price should be bigger than 0.0'))
            elif self.type_update == 'template_group':
                resources = template_id.template_line_ids
                if self.new_price > 0.0:
                    for line in resources:
                      line.write({'price': line.price * (self.new_price/100)})
                else:
                    raise ValidationError(_('Price should be bigger than 0.0'))

