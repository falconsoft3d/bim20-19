from odoo import fields, models


class View(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('folder', 'Folder')], ondelete={'folder': 'cascade'})

    def _get_view_info(self):
        view_info = super()._get_view_info()
        view_info['folder'] = {'icon': 'fa fa-folder-open'}
        return view_info
