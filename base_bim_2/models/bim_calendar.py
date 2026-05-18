# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)

class BimCalendar(models.Model):
    _description = "Bim Calendar"
    _name = 'bim.calendar'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code')

    monday = fields.Boolean('Monday', default=True)
    tuesday = fields.Boolean('Tuesday', default=True)
    wednesday = fields.Boolean('Wednesday', default=True)
    thursday = fields.Boolean('Thursday', default=True)
    friday = fields.Boolean('Friday', default=True)
    saturday = fields.Boolean('Saturday', default=False)
    sunday = fields.Boolean('Sunday', default=False)

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)


    def get_working_days_count(self, begin_date, end_date):
        for rec in self:
            allowed_days = {i for i, flag in enumerate([
                rec.monday, rec.tuesday, rec.wednesday,
                rec.thursday, rec.friday, rec.saturday, rec.sunday
            ]) if flag}

            _logger.info(f"Allowed days: {allowed_days}")

            day_count = 0
            while begin_date <= end_date:
                _logger.info(f"Checking date: {begin_date}, weekday: {begin_date.weekday()}")
                if begin_date.weekday() in allowed_days:
                    day_count += 1
                begin_date += timedelta(days=1)

            return day_count