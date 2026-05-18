from odoo import _,fields, api, models

class BimConcept(models.Model):
    _inherit = 'bim.concepts'
    _description = 'BimConcept'

    color = fields.Integer("Color", compute='_compute_color', store=True)

    def _compute_color(self):
        for record in self:
            if not record.color:
                if record.type == 'departure':
                    record.color = 4 # Amarillo
                if record.type == 'chapter':
                    record.color = 3 # Verde
                else:
                    record.color = 5

