# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging
_logger = logging.getLogger(__name__)


class DiaryPartWizard(models.TransientModel):
    _name = 'diary.part.wizard'
    _description = 'Diary Part Wizard'

    @api.model
    def default_get(self, fields_list):
        res = super(DiaryPartWizard, self).default_get(fields_list)
        diary_part_id = self.env['diary.part'].search([('id', '=', self._context.get('active_id'))])
        res['diary_part_id'] = diary_part_id.id
        return res

    diary_part_id = fields.Many2one(comodel_name="diary.part", string="Diary Part")
    hr_employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    lines_ids = fields.One2many('diary.part.wizard.line', 'diary_part_wizard_id', string="Lines")
    hr_employee_ids = fields.Many2many('hr.employee', string="Employees")


    def action_done(self):
        for l in self.lines_ids:
            # Busco ese PCP en la linea par ese empleado
            employee_lines_ids = self.env['diary.part.employee.lines'].search([
                ('bim_pcp_id', '=', l.bim_pcp_id.id),
                ('hr_employee_id', '=', self.hr_employee_id.id)
            ])
            if employee_lines_ids:
                employee_lines_ids.write({
                    'hh': l.hh
                })
            else:
                raise UserError(_('No se encontró la línea de ese empleado para ese PCP'))

    @api.onchange('diary_part_id')
    def _onchange_diary_part_id(self):
        self.hr_employee_ids = self.diary_part_id.employee_lines_ids.mapped('hr_employee_id')


    @api.onchange('hr_employee_id')
    def _onchange_hr_employee_id(self):
        self.lines_ids = [(5, 0, 0)]
        if self.diary_part_id:
            pcp_ids = self.diary_part_id.employee_lines_ids.filtered(lambda x: x.hr_employee_id.id == self.hr_employee_id.id)
            for line in pcp_ids:
                self.lines_ids = [(0, 0, {
                    'bim_pcp_id': line.bim_pcp_id.id,
                    'hh': line.hh
                })]


class DiaryPartWizardLine(models.TransientModel):
    _name = 'diary.part.wizard.line'
    _description = 'Diary Part Wizard Line'

    diary_part_wizard_id = fields.Many2one(comodel_name="diary.part.wizard", string="Diary Part Wizard")
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    hh = fields.Float(string="HH", required=True)

