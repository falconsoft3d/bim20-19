# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class PartnerAttendance(models.Model):
    _description = "Partner Attendance"
    _name = 'partner.attendance'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', 'Partner Employee', ondelete="cascade", required=True)
    project_ids = fields.Many2many('bim.project', string='Projects', compute='_compute_project_ids', help="Projects associated with the partner's attendance.")
    check_in = fields.Datetime('Check In', required=True)
    check_out = fields.Datetime('Check Out')
    attendance_duration = fields.Float('Attendance Duration', compute='_compute_attendance_duration', store=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    hourly_rate = fields.Float('Hourly Rate')
    balance = fields.Float('Balance', compute='_compute_balance', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    include_in_bim = fields.Boolean('Include in BIM', default=True, help="If checked, this attendance will be included in BIM calculations.")


    partner_attendance_contract_id = fields.Many2one('partner.attendance.contract', string='Attendance Contract',
    help="The attendance contract associated with this attendance record.", required=True)
    partner_attendance_contract_ids = fields.Many2many('partner.attendance.contract', string='Attendance Contracts', compute='_compute_partner_attendance_contract_ids', help="Attendance contracts associated with the partner's attendance.")

    hours_of_rest = fields.Float('Hours of Rest', default=0.0, help="The number of hours of rest included in the contract. This is used to calculate the balance for the partner's attendance.")
    fixed_cost = fields.Float('Fixed Cost', default=0.0, help="A fixed cost associated with the contract, if applicable. This can be used to cover additional expenses or fees related to the partner's attendance.")

    @api.depends('partner_id')
    def _compute_project_ids(self):
        for rec in self:
            if rec.partner_id:
                partner_attendance_contract_ids = self.env['partner.attendance.contract'].search([('partner_id', '=', rec.partner_id.parent_id.id)])
                rec.project_ids = partner_attendance_contract_ids.mapped('project_id')
            else:
                rec.project_ids = False


    @api.depends('partner_id', 'check_in', 'check_out', 'include_in_bim', 'project_id')
    def _compute_partner_attendance_contract_ids(self):
        for rec in self:
            if rec.partner_id:
                # Obtengo los contratos de asistencia del partner
                partner_attendance_contracts = self.env['partner.attendance.contract'].search([
                                        ('partner_id', '=', rec.partner_id.parent_id.id),
                                        ('project_id', '=', rec.project_id.id),
                                        ('state', 'in', ['active'])
                                    ])
                rec.partner_attendance_contract_ids = partner_attendance_contracts
                if rec.partner_attendance_contract_id and rec.partner_attendance_contract_id not in rec.partner_attendance_contract_ids:
                    rec.partner_attendance_contract_id = False
            else:
                rec.partner_attendance_contract_ids = False


    @api.onchange('partner_attendance_contract_id')
    def _onchange_partner_attendance_contract(self):
        if self.partner_attendance_contract_id:
            # busco en el la linea del contrato la tarifa por hora del partner
            contract_line = self.partner_attendance_contract_id.lines_ids.filtered(lambda l: l.partner_id == self.partner_id)
            if contract_line:
                self.hourly_rate = contract_line.hourly_rate
            else:
                self.hourly_rate = self.partner_attendance_contract_id.hourly_rate

            self.hours_of_rest = self.partner_attendance_contract_id.hours_of_rest
            self.fixed_cost = self.partner_attendance_contract_id.fixed_cost


    @api.depends('check_in', 'check_out')
    def _compute_attendance_duration(self):
        for rec in self:
            if rec.check_in and rec.check_out:
                rec.attendance_duration = (rec.check_out - rec.check_in).total_seconds() / 3600.0
            else:
                rec.attendance_duration = 0.0

    @api.depends('check_in', 'check_out', 'hourly_rate', 'hours_of_rest', 'fixed_cost')
    def _compute_balance(self):
        for rec in self:
            rec.balance = (( rec.attendance_duration - rec.hours_of_rest) * rec.hourly_rate ) + rec.fixed_cost