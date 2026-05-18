# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class BimConceptTemplateGroup(models.Model):
    _name = 'bim.concept.template.group'
    _order = "code asc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = "Concept Template Group"

    name = fields.Char("Name", required=True, index=True)
    code = fields.Char("Code", required=True, index=True)

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company,
                                 readonly=True)
    user_id = fields.Many2one('res.users', string='User', readonly=True, default=lambda self: self.env.user)
    parent_id = fields.Many2one('bim.concept.template.group', domain="[('id','!=',id),('parent_id','=',False)]")

    @api.onchange('parent_id')
    def onchange_groups(self):
        self.code = self.parent_id.code or ''