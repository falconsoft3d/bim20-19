from odoo import api, fields, models,_
import random, string

class BimMarketingCampaign(models.Model):
    _name = "bim.marketing.campaign"
    _description = "Bim Marketing Campaign"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char("Name", required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Partner', tracking=True)
    type = fields.Selection([
                                ('contact','Contact'),
                                ('ticket','Ticket'),
                                ('mant','OT de Mantenimiento')
                             ]
                            , required=True, tracking=True, default='contact')
    url = fields.Char('Url', compute='_compute_url', store=True, tracking=True)
    text_contact = fields.Text('Text Contact', tracking=True, required=True, default="Llene los datos del formulario para contactarnos")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    bim_project_id = fields.Many2one('bim.project', string='Project', tracking=True)
    utm_campaign_id = fields.Many2one('utm.campaign', string='UTM Campaign', tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)


    @api.depends('key')
    def _compute_url(self):
        for rec in self:
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.url = param_web_base_url + '/bim/form/' + str(rec.key)

    def _get_key(self):
        # Random key 10 digits
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    key = fields.Char("Key", tracking=True, default=_get_key)

