
from odoo import _, api, fields, models

class BimUpdate(models.Model):
    _name = 'bim.update'
    _description = 'Bim Update'
    _order = 'sequence, date desc, id desc'

    name = fields.Char('Name', required=True)
    date = fields.Date('Date', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('#')
    type = fields.Selection([
        ('bug', 'Bug Fix'),
        ('improvement', 'Improvement'),
        ('new_feature', 'New Feature'),
    ], string='Type', required=True, default='improvement')
    developed = fields.Char('Desarrollado', default='MFH')