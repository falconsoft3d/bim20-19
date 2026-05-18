# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class LostHour(models.Model):
    _description = "Lost Hour"
    _name = 'lost.hour'
    _order = "id desc"

    diary_part_id = fields.Many2one('diary.part', 'Diary Part', required=True)
    date = fields.Date('Date', required=True,
                        store=True,
                        related='diary_part_id.date')
    project_id = fields.Many2one('bim.project', 'Project', related='diary_part_id.project_id')
    sub_project_id = fields.Many2one('bim.project', string='Sub Project')
    employee_category_id = fields.Many2one('employee.category', string='Category')
    employee_specialty_id = fields.Many2one('employee.specialty', string='Specialty')
    description = fields.Char('Description')
    cause_lost_hour_id = fields.Many2one('cause.lost.hour', 'Cause')
    quantity = fields.Float('Quantity')

    validate = fields.Selection([
        ('ok', 'Ok'),
        ('claim', 'Claim'),
    ], string='Validate', default='ok', required=True)

    @api.onchange('diary_part_id')
    def _onchange_diary_part_id(self):
        self.project_id = self.diary_part_id.project_id.id