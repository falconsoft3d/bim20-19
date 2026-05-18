# coding: utf-8
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _description = "Bim Partner "
    _inherit = 'res.partner'

    retention_product = fields.Many2one('product.product', 'Product Retention',
                                        help="Product that will be used to bill the Retention")

    project_ids = fields.One2many('bim.project', 'customer_id', 'Projects')
    project_count = fields.Integer('# Projects', compute="_get_project_count")
    attendance_summary = fields.Boolean(string='Attendance summary', default=True)
    vies_failed_message = fields.Boolean(string='VIES failed message', default=False)


    latitude = fields.Float('Latitude', digits=(16, 15))
    longitude = fields.Float('Longitude', digits=(16, 15))


    c_classification = fields.Selection([
        ('private', 'Private'),
        ('public', 'Public'),
        ('contractor', 'Contractor'),
        ('other', 'Other')], string='Classification', default='other')

    @api.onchange('latitude')
    def _onchange_latitude(self):
        if self.latitude:
            self.partner_latitude = self.latitude

    @api.onchange('longitude')
    def _onchange_longitude(self):
        if self.longitude:
            self.partner_longitude = self.longitude


    def _get_project_count(self):
        for projects in self:
            projects.project_count = len(projects.project_ids)

    def action_view_projects(self):
        projects = self.mapped('project_ids')
        context = self.env.context.copy()
        context.update(default_customer_id=self.id)
        return {
            'type': 'ir.actions.act_window',
            'name': u'Projects',
            'res_model': 'bim.project',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', projects.ids)],
            'context': context
        }
