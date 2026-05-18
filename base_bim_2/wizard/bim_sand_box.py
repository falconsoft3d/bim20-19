# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import random

class BimSandBox(models.TransientModel):
    _name = 'bim.sand.box'
    _description = 'Bim Sand Box'

    @api.model
    def default_get(self, fields_list):
        res = super(BimSandBox, self).default_get(fields_list)
        project_id = self.env['bim.project'].search([('id', '=', self._context.get('active_id'))])
        res['project_id'] = project_id.id
        return res

    project_id = fields.Many2one(comodel_name="bim.project", string="Project")
    type = fields.Selection(string="Type", selection=[
            ('from_apu', 'From APU'),
    ], default='from_apu')

    number = fields.Integer(string="Number", default=10)
    quantity = fields.Float(string="Quantity", default=100)
    update_budget = fields.Boolean(string="Update", default=True)


    def create_budget(self):
        if self.type == 'from_apu':
            self.create_budget_from_apu()
        else:
            raise UserError(_("Not implemented yet"))


    def create_budget_from_apu(self):
        date_start = fields.Date.today()
        date_end = date_start + timedelta(days=365)

        budget = self.env['bim.budget'].create({
            'project_id': self.project_id.id,
            'name': 'Budget from APU',
            'currency_id': self.project_id.currency_id.id,
            'date_start': date_start,
            'date_end': date_end,
        })

        bim_concept_general = self.env['bim.concepts'].create({
            'budget_id': budget.id,
            'name': 'GENERAL',
            'type': 'chapter',
            'code': '01',
            'quantity': self.quantity,
            'acs_date_start': date_start,
            'acs_date_end': date_start,
        })


        bim_concept_template_ids = self.env['bim.concept.template'].search([
            ('amount_total', '>', 0),
        ], limit=self.number)
        ctlen = self.env['bim.concept.template'].search_count([])

        if self.number < ctlen:
            cycles = 1
        else:
            cycles = self.number // ctlen

        for i in range(cycles):
            for bim_concept_template in bim_concept_template_ids:

                # Generamen un numero entero random de 1 a 10
                random_number = random.randint(1, 10)
                date_startrandom = date_start + timedelta(days=random_number)
                random_number_2 = random.randint(1, 20)
                date_endrandom = date_startrandom + timedelta(days=random_number_2)

                bim_concept = self.env['bim.concepts'].create({
                    'budget_id': budget.id,
                    'name': bim_concept_template.name,
                    'type': 'departure',
                    'code': bim_concept_template.code,
                    'quantity': self.quantity,
                    'parent_id': bim_concept_general.id,
                    'performance': bim_concept_template.performance,
                    'concept_template_id': bim_concept_template.id,
                    'acs_date_start': date_startrandom,
                    'acs_date_end': date_endrandom,
                })

                bim_concept.onchange_dates()

                for _rec in bim_concept_template.template_line_ids:
                    if _rec.type == 'H':
                        type = 'labor'
                    elif _rec.type == 'Q':
                        type = 'equip'
                    elif _rec.type == 'S':
                        type = 'subcontract'
                    elif _rec.type == 'A':
                        type = 'aux'
                    elif _rec.type == 'M':
                        type = 'material'
                    else:
                        raise UserError(_("Type not defined"))

                    self.env['bim.concepts'].create({
                        'budget_id': budget.id,
                        'name': _rec.name,
                        'type': type,
                        'code': _rec.code,
                        'quantity': _rec.quantity,
                        'parent_id': bim_concept.id,
                        'product_id': _rec.product_id.id,
                        'amount_fixed': _rec.price,
                    })

        if self.update_budget:
            budget.update_amount()

