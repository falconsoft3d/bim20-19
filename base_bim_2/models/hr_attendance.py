from odoo import api, fields, models, _
from datetime import datetime, date, timedelta


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    project_id = fields.Many2one('bim.project', string='Project', domain="[('state_id.include_in_attendance','=',True)]")
    budget_id = fields.Many2one('bim.budget', string='Budget', domain="[('project_id','=',project_id),('state_id.include_in_attendance','=',True)]")
    concept_id = fields.Many2one('bim.concepts', string='Concept', domain="[('budget_id','=',budget_id),('type','=','departure')]")
    attendance_summary_id = fields.Many2one('hr.attendance.mass.summary', string='Attendance Summary', ondelete='cascade')

    bim_extra_hour_id = fields.Many2one('bim.extra.hour', string='Extra Hour')
    bim_client_hour_id = fields.Many2one('bim.client.hour', string='Client Hour')

    hour_cost = fields.Float(string='Cost/hour', compute='compute_attendance_cost', store=True, digits="BIM price")
    attendance_cost = fields.Float(string='Cost', compute='compute_attendance_cost', store=True, digits="BIM price")

    hour_price = fields.Float(string='Price/hour', compute='compute_attendance_price', store=True, digits="BIM price")
    attendance_price = fields.Float(string='Price', compute='compute_attendance_price', store=True, digits="BIM price")

    hour_profit = fields.Float(string='Profit', compute='compute_attendance_profit', store=True, digits="BIM price")

    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda r: r.env.company.currency_id)

    description = fields.Char()
    from_wizard = fields.Boolean(default=False)


    @api.onchange('employee_id')
    def bim_onchange_employee_id(self):
        if self.employee_id:
            if self.employee_id.default_bim_project:
                self.project_id = self.employee_id.default_bim_project.id

    def get_check_in(self):
        for record in self:
            return record.get_hour_dif(record.check_in) if record.check_in else "-"

    def get_check_out(self):
        for record in self:
            return record.get_hour_dif(record.check_out) if record.check_out else "-"

    def get_hour_dif(self, hour):
        if hour:
            DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
            date_field = datetime.strptime(str(hour), DATETIME_FORMAT)
            company_id = self.env['res.company'].search(
                [('active', '=', 'True')],
                limit=1)
            if company_id:
                dif_hf = company_id.server_hour_difference
            else:
                dif_hf = 0
            date_result = date_field + timedelta(hours=dif_hf)
            return date_result
        else:
            return ""

    @api.onchange('attendance_price', 'attendance_cost')
    def compute_attendance_profit(self):
        for record in self:
            record.hour_profit = record.attendance_price - record.attendance_cost

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            hour = self.env['bim.client.hour'].search([
                ('partner_id', '=', self.project_id.customer_id.id)], limit=1)
            if hour:
                self.bim_client_hour_id = hour.id
        self.budget_id = False

    @api.onchange('budget_id')
    def onchange_budget_id(self):
        self.concept_id = False

    @api.depends('worked_hours', 'bim_client_hour_id', 'employee_id')
    def compute_attendance_price(self):
        for record in self:
            line_cliente_hour = record.env['bim.client.hour.line'].search([
                ('bim_client_hour_id', '=', record.bim_client_hour_id.id),
                ('name', '=', record.employee_id.id)],
                limit=1)

            line_cliente_hour_by_default = record.env['bim.client.hour.line'].search([
                ('bim_client_hour_id', '=', self.env.user.company_id.id)],
                limit=1)

            if line_cliente_hour and self.bim_client_hour_id:
                record.hour_price = line_cliente_hour.price
            else:
                if line_cliente_hour_by_default:
                    record.hour_price = line_cliente_hour_by_default.price
                else:
                    record.hour_price = 0
            record.attendance_price = round(record.hour_price * record.worked_hours, 2)

    @api.depends('worked_hours','bim_extra_hour_id','bim_client_hour_id','employee_id')
    def compute_attendance_cost(self):
        for record in self:
            if record.bim_extra_hour_id:
                if record.bim_extra_hour_id.value > 0:
                    record.hour_cost = record.bim_extra_hour_id.value
                else:
                    record.hour_cost = record.bim_extra_hour_id.factor * record.employee_id.hour_cost
            else:
                if record.employee_id.hour_cost > 0:
                    record.hour_cost = record.employee_id.hour_cost
                else:
                    if record.employee_id.total_hours_week > 0 and record.employee_id.wage_bim > 0:
                        record.hour_cost = record.employee_id.wage_bim / (record.employee_id.total_hours_week * 4)
                    else:
                        record.hour_cost = record.env.company.hourly_cost

                # Sobrescribimos el costo si tengo uno el periodo
                hr_employee_project_cost_id = self.env['hr.employee.project.cost'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('begin_date', '<=', record.check_in),
                    ('end_date', '>=', record.check_in),
                ], limit=1)

                if hr_employee_project_cost_id:
                    record.hour_cost = hr_employee_project_cost_id.cost

            record.attendance_cost = round(record.hour_cost * record.worked_hours,2)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for res, vals in zip(records, vals_list):
            if res.from_wizard and res.env.company.server_hour_difference:
                hour_difference = res.env.company.server_hour_difference
                res.check_in += timedelta(hours=hour_difference)
                if res.check_out:
                    res.check_out += timedelta(hours=hour_difference)

            if 'project_id' not in vals and not res.project_id:
                res.project_id = res.employee_id.default_bim_project.id

        return records
