from odoo import api, fields, models, _


class BimMaintenance(models.Model):
    _name = 'bim.maintenance'
    _description = 'Assets and Discounts'
    name = fields.Char('Code', default='New')

class BimAsset(models.Model):
    _name = 'bim.assets'
    _description = 'Assets and Discounts'
    _rec_name = 'desc'

    name = fields.Char('Code', default='New', copy=False)
    desc = fields.Char('Gloss', required=True, translate=True)
    default_value = fields.Float('Default value')

    type = fields.Selection([('M', 'Total Materials'),
                             ('H', 'Total Labor'),
                             ('Q', 'Total Equipment'),
                             ('S', 'Total Sub-Contracts'),
                             ('T', 'Total Direct Costs'),
                             ('N', 'Total Net'),
                             ('O', 'Other')], default='N')

    obs = fields.Text('Observation', default="")
    show_on_report = fields.Boolean('Show in report', default=True,
                                    help="Indicates if you want to show credit / discount in budget report")
    not_billable = fields.Boolean('Not Billable', default=False)
    sum_all = fields.Boolean('Suma Todo', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        sec_obj = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = sec_obj.next_by_code('bim.assets') or 'New'
        return super().create(vals_list)

    @api.depends('name','desc')
    def _compute_display_name(self):
        for record in self:
            if record.name and record.desc:
                record.display_name = "[%s] %s" % (record.name, record.desc)
            else:
                record.display_name = record.name or record.desc

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if name:
            records = self.search(args + [('desc', operator, name)], limit=limit)
            if records:
                return [(record.id, record.display_name) for record in records]
        return super().name_search(name=name, args=args, operator=operator, limit=limit)


class BimHaberesydescTemplateLine(models.Model):
    _name = 'bim.assets.template.line'
    _description = 'Assets and Discounts template line'
    _rec_name = 'asset_id'
    _order = 'sequence'


    @api.model
    def default_get(self, default_fields):
        values = super(BimHaberesydescTemplateLine, self).default_get(default_fields)
        values['sequence'] = len(self.template_id.line_ids) + 1
        return values

    sequence = fields.Integer('Sequence')
    template_id = fields.Many2one('bim.assets.template', 'Template', ondelete="restrict")
    asset_id = fields.Many2one('bim.assets', 'Credit or Discount', required=True)
    type = fields.Selection(related='asset_id.type', readonly=True)
    value = fields.Float('Value')
    affect_ids = fields.Many2many(
        string='Affects',
        comodel_name='bim.assets.template.line',
        relation='template_line_assets_afect_rel',
        column1='parent_id',
        column2='child_id',
    )
    main_asset = fields.Boolean(default=False)

    @api.onchange('asset_id')
    def _onchange_assets(self):
        for record in self:
            record.value = record.asset_id and record.asset_id.default_value or 0.0
            record.sequence = len(record.template_id.line_ids)


class BimHaberesydescTemplate(models.Model):
    _name = 'bim.assets.template'
    _description = 'Assets and Discounts Template'

    @api.model
    def _default_lines(self):
        return [(0, 0, {
            'sequence': i,
            'asset_id': self.env.ref('base_bim_2.had0000%d' % i)
        }) for i in range(1, 5)]

    name = fields.Char('Name', required=True)
    desc = fields.Text('Description', default="")
    sale_ok = fields.Boolean('Sale template', default=False)
    line_ids = fields.One2many('bim.assets.template.line', 'template_id', string='Lines', required=True, copy=True, default=_default_lines)
    asset_id = fields.Many2one('bim.assets', 'Total')
    active = fields.Boolean('Active', default=True)


