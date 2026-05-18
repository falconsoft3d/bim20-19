from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    employee_id = fields.Many2one('hr.employee', string='Assigned to Employee')