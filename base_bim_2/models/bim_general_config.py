from odoo import api, fields, models,_


class BimGeneralConfig(models.Model):
    _name = "bim.general.config"
    _description = "Bim General Config"
    _order = 'id desc'
    _rec_name = "key"

    key = fields.Char("Key", required=True)
    value = fields.Char("Value", required=True)
    note = fields.Text("Note")
    user_id = fields.Many2one('res.users', "User", default=lambda self: self.env.user)
    create_date = fields.Datetime("Create Date", default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', "Company")