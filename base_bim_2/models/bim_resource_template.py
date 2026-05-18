from odoo import api, fields, models, _


class BimResourceTemplate(models.Model):
    _name = 'bim.resource.template'
    _description = 'Assets and Discounts Template'

    name = fields.Char('Name', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    code = fields.Char('Code', required=True)
    desc = fields.Text('Description', default="")
    line_ids = fields.One2many('bim.resource.template.line', 'template_id', string='Lines', required=True, copy=True)
    categories_ids = fields.Many2many('product.category', string='Product Categories')
    product_ids = fields.Many2many('product.product', string='Products')
    partner_id = fields.Many2one('res.partner', string='Contact')

    hr_employee_id = fields.Many2one('hr.employee', 'Responsible')
    sup_hr_employee_id = fields.Many2one('hr.employee', 'Supervisor')
    superintendent_hr_employee_id = fields.Many2one('hr.employee', 'Superintendent')

    employee_discipline_id = fields.Many2one('employee.discipline', string='Discipline')
    employee_area_id = fields.Many2one('employee.area', string='Area')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    employee_shift_id = fields.Many2one('employee.shift', string='Shift')
    employee_location_id = fields.Many2one('employee.location', string='Location')

    is_active = fields.Boolean('Is Active', default=True)
    active = fields.Boolean('Active', default=True)

    bim_pcp_ids = fields.Many2many('bim.pcp', string='PCP')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.code = self.product_id.default_code or self.product_id.id
            self.name = self.product_id.name or 'Brigada'


class BimResourceTemplateLine(models.Model):
    _name = 'bim.resource.template.line'
    _description = 'Assets and Discounts template line'
    _order = 'sequence'

    sequence = fields.Integer('Sequence')
    template_id = fields.Many2one('bim.resource.template', 'Template', ondelete="restrict")
    resource_type = fields.Selection([('M', 'Material'),('H', 'Labor'),('Q', 'Equipment'),('A', 'Administrative')],
                                        'Resourse Type', default='H', required=True)
    product_id = fields.Many2one('product.product')
    quantity = fields.Float('Quantity',  digits="BIM qty", default=1.0)
    hr_employee_id = fields.Many2one('hr.employee', 'Employee')

    @api.onchange('hr_employee_id')
    def _onchange_hr_employee_id(self):
        if self.hr_employee_id:
            self.resource_type = 'H'
            self.product_id = self.hr_employee_id.bim_resource_id.id
        else:
            self.resource_type = 'M'
            self.product_id = False

