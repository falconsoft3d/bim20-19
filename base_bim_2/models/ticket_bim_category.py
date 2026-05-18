# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class TicketBimCategory(models.Model):
    _description = "Ticket Bim Category"
    _name = 'ticket.bim.category'
    _inherit = ['mail.activity.mixin', 'mail.thread']

    @api.model
    def _needaction_domain_get(self):
        return [('name', '!=', '')]

    name = fields.Char('Name')
    email = fields.Char('Support Email')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
