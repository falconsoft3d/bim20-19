# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

class HrEmployeeBimBase(models.Model):
    _inherit = 'hr.employee'

    wage_bim = fields.Float('BIM Salary', digits="BIM price")
    default_bim_project = fields.Many2one('bim.project', string='Default Project')
    total_hours_week = fields.Float(compute='compute_total_hours_week', digits="BIM qty")
    hour_cost = fields.Float(string='Hour Cost', digits="BIM price", default=lambda self: self.env.company.hourly_cost)
    bim_resource_id = fields.Many2one('product.product', domain="[('type','=','service')]")
    code_bim = fields.Char('Code BIM')
    main_code = fields.Char('Main Code')
    old_code = fields.Char('Old Code')
    bim_pcp_id = fields.Many2one('bim.pcp', string='Job Type (PCP)')
    employee_location_id = fields.Many2one('employee.location', string='Location')
    employee_bim_payroll_id = fields.Many2one('employee.bim.payroll', string='Employee Bim Payroll')
    employee_category_id = fields.Many2one('employee.category', string='Category')
    employee_specialty_id = fields.Many2one('employee.specialty', string='Specialty')
    employee_shift_id = fields.Many2one('employee.shift', string='Shift')
    bim_resource_template_id = fields.Many2one('bim.resource.template', string='Resource Template', compute='_compute_bim_resource_template_id')
    include_for_bim = fields.Boolean(default=True)
    bim_portal_access = fields.Boolean('BIM Portal Access')
    bim_user = fields.Char('BIM User')
    bim_password = fields.Char('BIM Password')
    employee_dcategory_id = fields.Many2one('employee.dcategory', string='Doc . Category')




    def _compute_bim_resource_template_id(self):
        for record in self:
            record.bim_resource_template_id = record.env['bim.resource.template.line'].search([('hr_employee_id', '=', record.id)], limit=1).template_id


    type_d = fields.Selection([
        ('t_direct', 'Directo'),
        ('t_indirect', 'Indirecto'),
    ], string='Tipo', default='t_indirect')

    def compute_total_hours_week(self):
        for record in self:
            total = 0
            for line in record.resource_calendar_id.attendance_ids:
                total += line.hour_to - line.hour_from
            record.total_hours_week = total





class HrEmployeeBim(models.Model):
    _inherit = 'hr.employee'

    wage_bim = fields.Float('BIM Salary', digits="BIM price")
    default_bim_project = fields.Many2one('bim.project', string='Default Project')
    total_hours_week = fields.Float(compute='compute_total_hours_week', digits="BIM qty")
    hour_cost = fields.Float(string='Hour Cost', digits="BIM price")
    bim_resource_id = fields.Many2one('product.product', domain="[('type','=','service')]")
    project_ids = fields.Many2many('bim.project', copy=False)
    
    pant_size = fields.Many2one('hr.size', string='Pant', domain="[('type','=','pants')]")
    shirt_size = fields.Many2one('hr.size', string='Shirt', domain="[('type','=','shirt')]")
    shoes_size = fields.Many2one('hr.size', string='Shoes', domain="[('type','=','shoes')]")
    gloves_size = fields.Many2one('hr.size', string='Gloves', domain="[('type','=','gloves')]")
    vest_size = fields.Many2one('hr.size', string='Vest', domain="[('type','=','vest')]")
    tshirt_size = fields.Many2one('hr.size', string='T-shirt', domain="[('type','=','tshirt')]")
    polo_size = fields.Many2one('hr.size', string='Polo', domain="[('type','=','polo')]")
    jacket_size = fields.Many2one('hr.size', string='Jacket', domain="[('type','=','jacket')]")
    level_study_id = fields.Many2one('hr.level.study', string='Level Study')
    epi_location_id = fields.Many2one('stock.location', string='EPI Location', check_company=True)
    hr_employee_project_cost_ids = fields.One2many('hr.employee.project.cost', 'employee_id', string='Project Cost')
    equipment_ids = fields.One2many('maintenance.equipment', 'employee_id', string='Assigned Equipment')
    equipment_count = fields.Integer('Equipment Count', compute='_compute_equipment_count')
    bim_portal_access = fields.Boolean('BIM Portal Access')
    bim_user = fields.Char('BIM User')
    bim_password = fields.Char('BIM Password')

    # Documentacion de empleados
    employee_dcategory_id = fields.Many2one('employee.dcategory', string='Doc . Category')
    employee_documentation_ids = fields.One2many('employee.documentation', 'hr_employee_id', string='Documentation')
    employee_documentation_count = fields.Integer('Documentation Count', compute='_compute_employee_documentation_count')

    @api.depends('employee_documentation_ids')
    def _compute_employee_documentation_count(self):
        for employee in self:
            employee.employee_documentation_count = len(employee.employee_documentation_ids)


    def action_view_employee_documentation(self):
        """."""
        documentations = self.env['employee.documentation'].search(
            [('hr_employee_id', '=', self.id)])

        lines = []
        for documentation in documentations:
            lines.append(documentation.id)

        context = self.env.context.copy()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Employee Documentation"),
            'res_model': 'employee.documentation',
            'views': [[False, 'tree'], [False, 'form']],
            'domain': [('id', 'in', lines)],
            'context': context}




    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for employee in self:
            employee.equipment_count = len(employee.equipment_ids)

    def compute_total_hours_week(self):
        for record in self:
            total = 0
            for line in record.resource_calendar_id.attendance_ids:
                total += line.hour_to - line.hour_from
            record.total_hours_week = total

    partner_id = fields.Many2one('res.partner', 'Client')
    deliveries_count = fields.Char(compute='_compute_deliveries_count', string='Total')
    deliver_cost = fields.Char(compute='_compute_deliveries_cost', string='Deliveries cost')
    retry_count = fields.Char(
        compute='_compute_retry_count', string='Withdrawal')

    hr_employee_project_ids = fields.One2many('hr.employee.project', 'employee_id', string='Projects')



    def _compute_deliveries_count(self):
        """."""
        obj = self.env['product.line.list']
        for employee in self:
            products = 0
            delivers = obj.search(
                [('employee_id', '=', employee.id), ('state', '=', 'done'),
                 ('type', 'in', ('delivery', 'transfer'))])
            for deliver in delivers:
                if not deliver.retry:
                    products = products + deliver.qty
            employee.deliveries_count = '{}'.format(products)

    def _compute_deliveries_cost(self):
        """."""
        obj = self.env['product.line.list']
        for employee in self:
            products_sum = 0
            delivers = obj.search(
                [('employee_id', '=', employee.id), ('state', '=', 'done'),
                 ('type', 'in', ('delivery', 'transfer'))])
            for deliver in delivers:
                products_sum = products_sum + deliver.subtotal
            employee.deliver_cost = '{}'.format(products_sum)

    def _compute_retry_count(self):
        """."""
        obj = self.env['product.line.list']
        for employee in self:
            products = 0
            products_sum = 0
            delivers = obj.search(
                [('employee_id', '=', employee.id), ('state', '=', 'done'),
                 ('type', 'in', ('withdrawal',))])
            for deliver in delivers:
                products = products + deliver.qty
                products_sum = products_sum + deliver.subtotal

            employee.retry_count = '{} / {}'.format(
                products, products_sum)

    def get_deliveries(self, employee_id):
        """."""
        delivery_obj = self.env['product.line.list']
        return delivery_obj.search(
            [('employee_id', '=', employee_id)])

    def action_view_deliveries(self):
        """."""
        retries = self.env['product.line.list'].search(
            [('employee_id', '=', self.id), ('state', '=', 'done'),
             ('type', 'in', ('delivery', 'transfer'))])

        lines = []
        for retry in retries:
            if not retry.retry:
                lines.append(retry.id)

        context = self.env.context.copy()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Current EPIs"),
            'res_model': 'product.line.list',
            'views': [[False, 'tree'], [False, 'form']],
            'domain': [('id', 'in', lines)],
            'context': context}

    def action_view_deliver(self):
        """."""
        retries = self.env['product.line.list'].search(
            [('employee_id', '=', self.id), ('state', '=', 'done'),
             ('type', 'in', ('delivery', 'transfer'))])

        lines = []
        for retry in retries:
            lines.append(retry.id)

        context = self.env.context.copy()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Delivery/Transfer cost"),
            'res_model': 'product.line.list',
            'views': [[False, 'tree'], [False, 'form']],
            'domain': [('id', 'in', lines)],
            'context': context}

    def action_view_retry(self):
        """."""
        retries = self.env['product.line.list'].search(
            [('employee_id', '=', self.id), ('state', '=', 'done'),
             ('type', '=', 'withdrawal')])

        lines = []
        for retry in retries:
            lines.append(retry.id)

        context = self.env.context.copy()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Delivery cost"),
            'res_model': 'product.line.list',
            'views': [[False, 'tree'], [False, 'form']],
            'domain': [('id', 'in', lines)],
            'context': context}


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    wage_bim = fields.Float('BIM Salary', digits="BIM price")
    default_bim_project = fields.Many2one('bim.project', string='Default Project')
    total_hours_week = fields.Float(compute='compute_total_hours_week', digits="BIM qty")
    hour_cost = fields.Float(string='Hour Cost', digits="BIM price", default=lambda self: self.env.company.hourly_cost)
    bim_resource_id = fields.Many2one('product.product', domain="[('type','=','service')]")
    code_bim = fields.Char('Code BIM')
    main_code = fields.Char('Main Code')
    old_code = fields.Char('Old Code')
    bim_pcp_id = fields.Many2one('bim.pcp', string='Job Type (PCP)')
    employee_location_id = fields.Many2one('employee.location', string='Location')
    employee_bim_payroll_id = fields.Many2one('employee.bim.payroll', string='Employee Bim Payroll')
    employee_category_id = fields.Many2one('employee.category', string='Category')
    employee_specialty_id = fields.Many2one('employee.specialty', string='Specialty')
    employee_shift_id = fields.Many2one('employee.shift', string='Shift')
    bim_resource_template_id = fields.Many2one('bim.resource.template', string='Resource Template',
                                               compute='_compute_bim_resource_template_id')
    include_for_bim = fields.Boolean(default=True)

    equipment_ids = fields.One2many('maintenance.equipment', 'employee_id', string='Assigned Equipment')
    equipment_count = fields.Integer('Equipment Count', compute='_compute_equipment_count')

    bim_portal_access = fields.Boolean('BIM Portal Access')
    bim_user = fields.Char('BIM User')
    bim_password = fields.Char('BIM Password')
    employee_dcategory_id = fields.Many2one('employee.dcategory', string='Doc . Category')

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for employee in self:
            employee.equipment_count = len(employee.equipment_ids)

    def compute_total_hours_week(self):
        for record in self:
            total = 0
            for line in record.resource_calendar_id.attendance_ids:
                total += line.hour_to - line.hour_from
            record.total_hours_week = total



    def _compute_bim_resource_template_id(self):
        for record in self:
            record.bim_resource_template_id = record.env['bim.resource.template.line'].search(
                [('hr_employee_id', '=', record.id)], limit=1).template_id

    type_d = fields.Selection([
        ('t_direct', 'Directo'),
        ('t_indirect', 'Indirecto'),
    ], string='Tipo', default='t_indirect')

    def compute_total_hours_week(self):
        for record in self:
            total = 0
            for line in record.resource_calendar_id.attendance_ids:
                total += line.hour_to - line.hour_from
            record.total_hours_week = total

class HrEmployeeProject(models.Model):
    _name = 'hr.employee.project'
    _description = 'Employee Tools'

    project_id = fields.Many2one('bim.project', string='Project', required=True)
    site_code = fields.Char('Site Code')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)


class HrEmployeeProjectCost(models.Model):
    _name = 'hr.employee.project.cost'
    _description = 'Employee Project Cost'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    begin_date = fields.Date('Begin Date', required=True)
    end_date = fields.Date('End Date', required=True)
    cost = fields.Float('Cost', required=True)
