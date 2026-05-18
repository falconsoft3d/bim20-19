# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class BimEquipmentCost(models.Model):
    _description = "Bim Equipment Cost"
    _name = 'bim.equipment.cost'
    _order = "id desc"
    _rec_name = 'equipment_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, copy=False)
    equipment_id = fields.Many2one('product.template', domain="[('resource_type','=','Q')]", required=True, ondelete="restrict",)
    value = fields.Float('Equipment Value', tracking=1, digits='BIM qty')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    date = fields.Datetime('Date', copy=False, default=fields.Datetime.now, tracking=True)
    amount_total = fields.Float(compute='_compute_amount_total', store=True, digits='BIM price')
    cost_ids = fields.One2many('bim.equipment.cost.line', 'cost_id')
    note = fields.Text(default="")

    @api.depends('value','cost_ids','cost_ids.amount','cost_ids.type')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.value * line.amount/100 if line.type == 'percent' else line.amount for line in record.cost_ids)

    def apply_cost(self):
        self.equipment_id.with_company(self.env.company).standard_price = self.amount_total
        self.message_post(body=_("Current cost %s %s was applied to Equipment %s")%(str(self.amount_total),self.currency_id.symbol,self.equipment_id.display_name))
        self.equipment_id.message_post(body=_("Cost %s %s was apply to this Equipment")%(str(self.amount_total),self.currency_id.symbol))


class BimEquipmentCostLine(models.Model):
    _description = "Bim Equipment Cost Line"
    _name = 'bim.equipment.cost.line'

    cost_id = fields.Many2one('bim.equipment.cost')
    name = fields.Char(required=True)
    type = fields.Selection([('percent','Percent'),('amount','Amount')], default='percent', required=True)
    amount = fields.Float(digits='BIM price')




