# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
from math import ceil
from datetime import timedelta
import random
import string

# bim.deliverable
class BimDeliverable(models.Model):
    _description = "BIM Deliverable"
    _name = 'bim.deliverable'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True)



class DiaryPart(models.Model):
    _description = "Diary Part"
    _name = 'diary.part'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget')
    bim_deliverable_id = fields.Many2one('bim.deliverable', string='Deliverable')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('dont_work', 'Dont Work'),
        ('loaded', 'Loaded'),
        ('review', 'Review'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft', required=True, copy=False, tracking=True)

    date = fields.Date('Date', required=True, default=fields.Date.context_today)
    begin_date = fields.Datetime('Begin Date', required=True, default=fields.Datetime.now)
    end_date = fields.Datetime('End Date', required=True, default=fields.Datetime.now)

    hr_employee_id = fields.Many2one('hr.employee', 'Responsible')
    sup_hr_employee_id = fields.Many2one('hr.employee', 'Supervisor')
    superintendent_hr_employee_id = fields.Many2one('hr.employee', 'Superintendent')
    employee_discipline_id = fields.Many2one('employee.discipline', string='Discipline')
    employee_area_id = fields.Many2one('employee.area', string='Area')

    observation = fields.Text('Observation')
    bim_resource_template_id = fields.Many2one('bim.resource.template', string='Brigade', required=True)
    lines_ids = fields.One2many('diary.part.lines', 'part_id', string='Lines')
    equip_ids = fields.One2many('diary.part.equip.lines', 'part_id', string='Equipos')
    lost_hour_ids = fields.One2many('lost.hour', 'diary_part_id', string='Lost Hours')

    employee_lines_ids = fields.One2many('diary.part.employee.lines', 'part_id', string='Employee Lines')
    employee_lines_sum_ids = fields.One2many('diary.part.employee.sum.lines', 'part_id', string='Employee Lines Sum')

    amount_total = fields.Float('Total', compute='_compute_amount_total', store=True)
    daily_part_liquidation_id = fields.Many2one('daily.part.liquidation', string='Daily Part Liquidation')
    work_order = fields.Char('Work Order')
    hh = fields.Float('HH', compute='_compute_hh')
    hhr = fields.Float('HH Real', compute='_compute_hhr')
    bim_pcp_ids = fields.Many2many('bim.pcp', string='PCP')
    url = fields.Char('URL', copy=False, compute='_compute_url')


    def _get_key(self):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    key = fields.Char("Key", tracking=True, default=_get_key)

    @api.depends('key')
    def _compute_url(self):
        for rec in self:
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.url = param_web_base_url + '/bim/diary-part/' + str(rec.key)

    @api.depends('employee_lines_ids')
    def _compute_hh(self):
        for record in self:
            record.hh = sum(line.hh for line in record.employee_lines_ids)

    @api.depends('employee_lines_ids')
    def _compute_hhr(self):
        for record in self:
            record.hhr = sum(line.hhr for line in record.employee_lines_ids)


    def to_dont_work(self):
        self.write({'state': 'dont_work'})
        return True


    @api.onchange('bim_pcp_ids')
    def _onchange_bim_pcp_ids(self):
        self.employee_lines_ids = [(5, 0, 0)]
        self.hr_employee_id = self.bim_resource_template_id.hr_employee_id.id
        self.sup_hr_employee_id = self.bim_resource_template_id.sup_hr_employee_id.id
        self.superintendent_hr_employee_id = self.bim_resource_template_id.superintendent_hr_employee_id.id
        self.employee_discipline_id = self.bim_resource_template_id.employee_discipline_id.id
        self.employee_area_id = self.bim_resource_template_id.employee_area_id.id

        # Cargamos las lineas de empleados
        for employee in self.bim_resource_template_id.line_ids:
            if self.bim_pcp_ids:
                for pcp in self.bim_pcp_ids:
                    self.employee_lines_ids = [(0, 0, {
                        'hr_employee_id': employee.hr_employee_id.id,
                        'bim_pcp_id': pcp.id,
                        'code_bim': employee.hr_employee_id.code_bim,
                        'main_code': employee.hr_employee_id.main_code,
                        'project_id': self.project_id.id,
                    })]
            else:
                self.employee_lines_ids = [(0, 0, {
                    'hr_employee_id': employee.hr_employee_id.id,
                    'bim_pcp_id': employee.hr_employee_id.bim_pcp_id.id,
                    'code_bim': employee.hr_employee_id.code_bim,
                    'main_code': employee.hr_employee_id.main_code,
                    'project_id': self.project_id.id,
                })]


    @api.onchange('bim_resource_template_id')
    def _onchange_bim_resource_template_id(self):
        self.employee_lines_ids = [(5, 0, 0)]
        self.lines_ids = [(5, 0, 0)]
        self.hr_employee_id = self.bim_resource_template_id.hr_employee_id.id
        self.sup_hr_employee_id = self.bim_resource_template_id.sup_hr_employee_id.id
        self.superintendent_hr_employee_id = self.bim_resource_template_id.superintendent_hr_employee_id.id
        self.employee_discipline_id = self.bim_resource_template_id.employee_discipline_id.id
        self.employee_area_id = self.bim_resource_template_id.employee_area_id.id
        self.bim_pcp_ids = self.bim_resource_template_id.bim_pcp_ids.ids


        # Cargamos las lineas de empleados
        for employee in self.bim_resource_template_id.line_ids:
            if self.bim_pcp_ids:
                for pcp in self.bim_pcp_ids:
                    self.employee_lines_ids = [(0, 0, {
                        'hr_employee_id': employee.hr_employee_id.id,
                        'bim_pcp_id': pcp.id,
                        'code_bim': employee.hr_employee_id.code_bim,
                        'main_code': employee.hr_employee_id.main_code,
                        'project_id': self.project_id.id,
                    })]
            else:
                self.employee_lines_ids = [(0, 0, {
                    'hr_employee_id': employee.hr_employee_id.id,
                    'bim_pcp_id': employee.hr_employee_id.bim_pcp_id.id,
                    'code_bim': employee.hr_employee_id.code_bim,
                    'main_code': employee.hr_employee_id.main_code,
                    'project_id': self.project_id.id,
                })]

        # Cargamos las lineas de avances
        for pcp in self.bim_resource_template_id.bim_pcp_ids:
            self.lines_ids = [(0, 0, {
                'bim_pcp_id': pcp.id,
            })]



    def search_hours(self):
        for line in self.employee_lines_ids:
            if line.hr_employee_id:
                hr_attendance_ids = self.env['hr.attendance'].search([
                    ('employee_id', '=', line.hr_employee_id.id),
                    ('check_in', '>=', self.date),
                    ('check_out', '<=', self.date)
                ])

                total_hours = 0
                for hr_attendance in hr_attendance_ids:
                    total_hours += hr_attendance.worked_hours
                line.hhr = total_hours

    def to_loaded(self):
        self.write({'state': 'loaded'})
        # limpiamos las suma de horas
        self.employee_lines_sum_ids.unlink()

        for line in self.employee_lines_ids:
            line.budget_id = self.budget_id
            line.code_bim = line.hr_employee_id.code_bim
            line.employee_shift_id = self.bim_resource_template_id.employee_shift_id
            line.employee_category_id = line.hr_employee_id.employee_category_id
            line.employee_specialty_id = line.hr_employee_id.employee_specialty_id
            line.employee_location_id = self.bim_resource_template_id.employee_location_id
            line.type_d = line.hr_employee_id.type_d
            line.employee_bim_payroll_id = line.hr_employee_id.employee_bim_payroll_id
            line.work_order = self.work_order
            line.bim_resource_template_id = self.bim_resource_template_id

            # Buscamos la bi week
            bi_week_id = self.env['bi.week'].search([('date_from', '<=', self.date), ('date_to', '>=', self.date)], limit=1)
            if bi_week_id:
                line.wek_number = bi_week_id.name


            employee_lines_sum_id = self.env['diary.part.employee.sum.lines'].search([
                ('hr_employee_id', '=', line.hr_employee_id.id),
                ('part_id', '=', self.id)
            ], limit=1)


            if employee_lines_sum_id:
                employee_lines_sum_id.hh += line.hh
                employee_lines_sum_id.hhr += line.hhr
                employee_lines_sum_id.bonus_hours += line.bonus_hours
            else:
                self.env['diary.part.employee.sum.lines'].create({
                    'hr_employee_id': line.hr_employee_id.id,
                    'part_id': self.id,
                    'hh': line.hh,
                    'hhr': line.hhr,
                    'bonus_hours': line.bonus_hours
                })



        return True

    @api.depends('lines_ids')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(line.qty for line in record.lines_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diary.part') or 'New'
        return super().create(vals_list)

    def load_data(self):
        self.lines_ids.unlink()

        bim_mto_line_ids = self.env['bim.mto.line'].search([('bim_deliverable_id', '=', self.bim_deliverable_id.id)])
        if not bim_mto_line_ids:
            raise UserError(_('There are no lines to load'))
        else:
            for line in bim_mto_line_ids:
                self.env['diary.part.lines'].create({
                    'part_id': self.id,

                })
        return True

    def approve(self):
        block = False
        bim_general_config_id = self.env['bim.general.config'].search([('key', '=', 'blok_aprove_part')], limit=1)
        if bim_general_config_id:
            if bim_general_config_id.value == '1':
                block = True

        if block:
            for line in self.employee_lines_ids:
                hh_sum_employee = sum(line.hh for line in self.employee_lines_ids if line.hr_employee_id == line.hr_employee_id)
                hhr_sum_employee = sum(line.hhr for line in self.employee_lines_ids if line.hr_employee_id == line.hr_employee_id)
                if hh_sum_employee != hhr_sum_employee:
                    raise UserError(_('The hours of the employee %s are different from the hours worked') % line.hr_employee_id.name)

        self.write({'state': 'approved'})
        return True

    def exe_draft(self):
        self.write({'state': 'draft'})
        return True

    def exe_done(self):
        self.write({'state': 'done'})
        return True

    def exe_review(self):
        self.write({'state': 'review'})
        return True

class DiaryPartLines(models.Model):
    _description = "Diary Part Lines"
    _name = 'diary.part.lines'

    part_id = fields.Many2one('diary.part', string='Diary Part', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', related='part_id.budget_id')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    ipr = fields.Float('IPR', compute='_compute_ipr', store=True)
    qty = fields.Float('Qty')
    work_breakdown_id = fields.Many2one('work.breakdown', string='Work Breakdown')
    bim_element_id = fields.Many2one('bim.element', string='Element')
    concepts_id = fields.Many2one('bim.concepts', string='Concepts')
    status = fields.Selection([
        ('plan', 'Plan'),
        ('in_process', 'En Proceso'),
        ('complete', 'Completo'),
        ('stopped', 'Detenido'),
    ], string='Estatus', default='plan', required=True)



    @api.depends('qty')
    def _compute_ipr(self):
        for record in self:
            total_hh = sum(line.hh for line in record.part_id.employee_lines_ids)
            if record.qty == 0:
                record.ipr = 0
            else:
                record.ipr = total_hh / record.qty

class DiaryPartEmployeeLines(models.Model):
    _description = "Diary Part Employee Lines"
    _name = 'diary.part.employee.lines'

    part_id = fields.Many2one('diary.part', string='Diary Part', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', related='part_id.budget_id')
    hr_employee_id = fields.Many2one('hr.employee', string='Employee')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    hh = fields.Float('HH')
    hhr = fields.Float('HH Real')
    bonus_hours = fields.Float('Bonus Hours',  digits="BIM qty", default=0.0)
    project_id = fields.Many2one('bim.project', string='Project')
    date = fields.Date('Date', related='part_id.date')
    main_code = fields.Char('Main Code')
    code_bim = fields.Char('Code BIM')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    bim_concept_id = fields.Many2one('bim.concepts', string='Departure')
    employee_shift_id = fields.Many2one('employee.shift', string='Shift')
    employee_category_id = fields.Many2one('employee.category', string='Category')
    employee_specialty_id = fields.Many2one('employee.specialty', string='Specialty')
    employee_location_id = fields.Many2one('employee.location', string='Location')
    type_d =  fields.Selection(string='Type', related='hr_employee_id.type_d')
    employee_bim_payroll_id = fields.Many2one('employee.bim.payroll', string='Nómina')
    wek_number = fields.Integer('Bi Week')
    work_order = fields.Char('Work Order', related='part_id.work_order')
    bim_resource_template_id = fields.Many2one('bim.resource.template', string='Brigade')

    @api.onchange('hr_employee_id')
    def _onchange_hr_employee_id(self):
        self.main_code = self.hr_employee_id.main_code
        self.code_bim = self.hr_employee_id.code_bim
        self.project_id = self.part_id.project_id

class DiaryPartEmployeeSumLines(models.Model):
    _description = "Diary Part Employee Sum Lines"
    _name = 'diary.part.employee.sum.lines'
    hr_employee_id = fields.Many2one('hr.employee', string='Employee')
    part_id = fields.Many2one('diary.part', string='Diary Part', required=True)
    hh = fields.Float('HH')
    hhr = fields.Float('HH Real')
    bonus_hours = fields.Float('Bonus Hours',  digits="BIM qty", default=0.0)



class DiaryPartEquipLines(models.Model):
    _description = "Diary Part Equip Lines"
    _name = 'diary.part.equip.lines'

    part_id = fields.Many2one('diary.part', string='Diary Part', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')

    budget_id = fields.Many2one('bim.budget', string='Budget', related='part_id.budget_id')
    bim_concept_id = fields.Many2one('bim.concepts', string='Departure')

    qty = fields.Float('Qty')
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Equipo')
    ref = fields.Char('Referencia')

    @api.onchange('fleet_vehicle_id')
    def _onchange_fleet_vehicle_id(self):
        self.product_id = self.fleet_vehicle_id.product_id.id
