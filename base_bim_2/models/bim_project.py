# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
import base64
from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, RedirectWarning, ValidationError, AccessError
from odoo.modules.module import get_module_resource
from random import randint
import logging
_logger = logging.getLogger(__name__)

class BimTag(models.Model):
    _name = 'bim.tag'
    _description = 'Bim Tag'

    def _get_default_color(self):
        return randint(1, 11)

    active = fields.Boolean(default=True)
    color = fields.Integer('Color', default=_get_default_color)
    name = fields.Char(required=True)


class BimProjectState(models.Model):
    _name = 'bim.project.state'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Project State'
    _order = "sequence asc, id desc"

    name = fields.Char(required=True, translate=True)
    is_new = fields.Boolean()
    is_done = fields.Boolean()
    include_in_attendance = fields.Boolean(default=True, string="Register Attendance")
    sequence = fields.Integer(default=16)
    user_ids = fields.Many2many('res.users', string="Users")

    set_budget_state_id = fields.Many2one('bim.budget.state', string='Set Budget State')
    required_fields = fields.Char('Required Fields', help="Fields required to change the state of the project")
    create_purchase_order = fields.Boolean('Create Purchase Orders', default=True)


class bim_project(models.Model):
    _description = "Project"
    _name = 'bim.project'
    _order = "name desc"
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']



    name = fields.Char('Code', default="New", tracking=True, copy=False)
    nombre = fields.Char('Name', tracking=True, copy=True,
                         default=lambda self: self.env.company.name
                         )
    framework_contract_id = fields.Many2one('framework.contract', string="Framework Contract")
    contact_id = fields.Many2one('res.partner', string='Contact', tracking=True)
    notes = fields.Text(string="Observations", default="")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True )
    user_id = fields.Many2one('res.users', string='Supervisor', tracking=True,  default=lambda self: self.env.user)
    task_ids = fields.One2many('bim.task', 'project_id', 'Tasks')
    ticket_ids = fields.One2many('ticket.bim', 'project_id', 'Ticket')
    obs = fields.Text('Notes', default="")
    retention = fields.Float('Retención %', default=lambda self: self.env.company.retention, digits=(10, 2))

    budget_count = fields.Integer('N° Budgets', compute="_get_budget_count")
    budget_ids = fields.One2many('bim.budget','project_id','Budgets')

    partner_attendance_count = fields.Integer('N° Partner Attendance', compute="_compute_partner_attendance_count")
    partner_attendance_ids = fields.One2many('partner.attendance', 'project_id', 'Partner Attendance')

    # hh_planificadas = fields.Float('HH Planned', compute="_compute_hh", digits="BIM qty")
    currency_id = fields.Many2one('res.currency', required=True, default=lambda r: r.env.company.currency_id)
    customer_id = fields.Many2one('res.partner', string='Customer',
                                  tracking=True,
                                  default=lambda self: self.env.company.partner_id.id)
    invoice_address_id = fields.Many2one('res.partner', string='Invoice Address', tracking=True)
    requisition_ids = fields.One2many('bim.purchase.requisition','project_id')
    service_ids = fields.One2many('bim.purchase.services','project_id')
    fuel_ids = fields.One2many('tms.expense.record','bim_project_id')
    include_in_attendance = fields.Boolean('Include in Attendance',
                                            related='state_id.include_in_attendance')

    contractor_id = fields.Many2one('res.partner', string='Contratista', tracking=True)
    requisition_user_ids = fields.Many2many('res.users', string='Users Requisition')
    parent_id = fields.Many2one('bim.project', string='Parent Project')


    employee_ids = fields.Many2many('hr.employee', copy=False)

    employee_hr_count = fields.Integer('# Employees (HR)', compute="_compute_employee_hr_count")
    employee_hr_line_ids = fields.One2many('hr.employee', 'default_bim_project', 'Employee Lines (HR)')


    limit_purchase = fields.Boolean(default=lambda r: r.env.company.limit_purchase, tracking=True)
    project_tool_rent_ids = fields.One2many('bim.tool.rent', 'project_id', 'Project Tool Rent')
    update_date_all = fields.Datetime('Update Date')

    create_purchase_order = fields.Boolean('Create Purchase Orders', related='state_id.create_purchase_order', store=True)
    favorite = fields.Boolean('Favorite', default=False)
    budgeted_hours = fields.Float('HH Presup.')
    real_hours = fields.Float('HH Real')

    project_user_id = fields.Many2one('res.users', string='Project Manager', tracking=True)
    sale_user_id = fields.Many2one('res.users', string='Sales Manager', tracking=True)
    execution_manager = fields.Many2one('res.users', string='Execution Manager', tracking=True)
    customer_ids = fields.Many2many('res.partner', string='Customers', tracking=True)
    main_bim_budget_id = fields.Many2one('bim.budget', string='Main Budget', tracking=True)

    bim_cash_flow_ids = fields.One2many('bim.cash.flow','bim_project_id','Cash Flow')
    bim_cash_flow_count = fields.Integer('# Cash Flow', compute="_get_bim_cash_flow_count")


    total_purchase_invoice = fields.Monetary('Total Purchase Invoices')
    total_purchase_invoice_bruto = fields.Monetary('Total Purchase Invoices (Gross)')

    total_purchase_in_invoice = fields.Monetary('Total Sale Invoices')
    total_purchase_in_invoice_bruto = fields.Monetary('Total Sale Invoices (Gross)')

    total_benif_neto = fields.Monetary('Net Benefit')
    total_benif_bruto = fields.Monetary('Gross Benefit')
    total_benif_payment = fields.Monetary('Total Benif Payments')

    total_sale_payments = fields.Monetary('Total Sale Payments')
    total_purchase_payments = fields.Monetary('Total Purchase Payments')
    initial_sale = fields.Float('Venta')
    initial_coste = fields.Float('Coste')

    # _compute_partner_attendance_count
    @api.depends('partner_attendance_ids')
    def _compute_partner_attendance_count(self):
        for project in self:
            project.partner_attendance_count = len(project.partner_attendance_ids)


    @api.depends('name','nombre')
    def _compute_display_name(self):
        for record in self:
            record.display_name = "[%s] %s" % (record.name, record.nombre)


    @api.constrains('name')
    def _check_main_code(self):
        for record in self:
            if self.env['bim.project'].search_count([('name', '=', record.name)]) > 1:
                raise ValidationError("El código del proyecto debe ser único")


    def action_update_invoice(self):
        total = 0
        total_bruto = 0
        if self.analytic_id:
            analytic_lines = self.env['account.analytic.line'].search([('account_id','=',self.analytic_id.id),('move_line_id','!=',False),
                                                                       ('move_line_id.move_id.move_type','in',['in_invoice','in_refund']),
                                                                       ('move_line_id.move_id.include_for_bim','=',True),
                                                                       ('move_line_id.move_id.state','=','posted'),('move_line_id.display_type','=','product')])
            for line in analytic_lines:
                if line.move_line_id.move_id.move_type == 'in_invoice':
                    total = total + line.amount * -1
                    total_bruto = total_bruto + line.move_line_id.price_total
                else:
                    total = total - line.amount
                    total_bruto = total_bruto - line.move_line_id.price_total

        self.total_purchase_invoice = total
        self.total_purchase_invoice_bruto = total_bruto


        total = 0
        total_bruto = 0
        if self.analytic_id:
            analytic_lines = self.env['account.analytic.line'].search([('account_id','=',self.analytic_id.id),('move_line_id','!=',False),
                                                                       ('move_line_id.move_id.move_type','in',['out_invoice','out_refund']),
                                                                       ('move_line_id.move_id.include_for_bim','=',True),
                                                                       ('move_line_id.move_id.state','=','posted'),('move_line_id.display_type','=','product')])
            for line in analytic_lines:
                if line.move_line_id.move_id.move_type == 'out_invoice':
                    total = total + line.amount
                    total_bruto = total_bruto + line.move_line_id.price_total
                else:
                    total = total - line.amount
                    total_bruto = total_bruto - line.move_line_id.price_total

        self.total_purchase_in_invoice = total
        self.total_purchase_in_invoice_bruto = total_bruto

        self.total_benif_neto = self.total_purchase_in_invoice - self.total_purchase_invoice
        self.total_benif_bruto = self.total_purchase_in_invoice_bruto - self.total_purchase_invoice_bruto

        # Sale Payments
        account_payment_ids = self.env['account.payment'].search([
                                        ('project_id','=',self.id),
                                        ('payment_type','=','inbound'),
                                        ('state','=','posted')
                                    ])
        self.total_sale_payments = sum(x.amount for x in account_payment_ids)

        # Purchase Payments
        account_payment_ids = self.env['account.payment'].search([
                                        ('project_id','=',self.id),
                                        ('payment_type','=','outbound'),
                                        ('state','=','posted')
                                    ])
        self.total_purchase_payments = sum(x.amount for x in account_payment_ids)


        self.total_benif_payment = self.total_sale_payments - self.total_purchase_payments


    def _get_bim_cash_flow_count(self):
        for project in self:
            project.bim_cash_flow_count = len(project.bim_cash_flow_ids)


    def action_view_partner_attendance(self):
        action = self.env.ref('base_bim_2.action_partner_attendance').sudo().read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {
                              'default_project_id': self.id,
                              'default_partner_id': self.customer_id.id,
                            }
        return action


    def action_view_bim_cash_flow(self):
        action = self.env.ref('base_bim_2.action_bim_cash_flow').sudo().read()[0]
        action['domain'] = [('bim_project_id', '=', self.id)]
        action['context'] = {
                              'default_bim_project_id': self.id
                            }
        return action

    bim_element_ids = fields.One2many('bim.element', 'project_id', 'Elements')
    bim_element_count = fields.Integer('N° Elements', compute="_get_bim_element_count")

    def _get_bim_element_count(self):
        for project in self:
            project.bim_element_count = len(project.bim_element_ids)

    def action_view_bim_element(self):
        action = self.env.ref('base_bim_2.action_bim_element').sudo().read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {
                              'default_project_id': self.id
                            }
        return action



    bim_rfi_ids = fields.One2many('bim.rfi','project_id','RFI')
    bim_rfi_count = fields.Integer('RFI Count', compute="_get_bim_rfi_count")

    def _get_bim_rfi_count(self):
        for project in self:
            project.bim_rfi_count = len(project.bim_rfi_ids)


    def action_view_bim_rfi(self):
        action = self.env.ref('base_bim_2.action_bim_rfi').sudo().read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {
                              'default_project_id': self.id,
                              'default_partner_id': self.customer_id.id,
                              'default_contact_id': self.contact_id.id,
                            }
        return action


    # RQ
    bim_rq_ids = fields.One2many('bim.rq', 'project_id', 'RQ')
    bim_rq_count = fields.Integer('RQ Count', compute="_get_bim_rq_count")

    def _get_bim_rq_count(self):
        for project in self:
            project.bim_rq_count = len(project.bim_rq_ids)

    def action_view_bim_rq(self):
        action = self.env.ref('base_bim_2.action_bim_rq').sudo().read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {
            'default_project_id': self.id,
            'default_partner_id': self.customer_id.id,
        }
        return action


    @api.model
    def _default_image(self):
        image_path = get_module_resource('base_bim_2', 'static/src/img', 'default_image.png')
        return base64.b64encode(open(image_path, 'rb').read())

    image_1920 = fields.Image("Image", max_width=1920, max_height=1920, default=_default_image)
    image_128 = fields.Image("Image 128", max_width=128, max_height=128, store=True)


    def action_update_all(self):
        self.update_project_cost()
        self.update_sale_project_cost()


        # Limpiamos los customer_ids
        self.customer_ids = False

        # Calculamos los customer_ids de los presupuestos
        for budget in self.budget_ids:
            # revisamos si el cliente ya esta en la lista
            if budget.customer_ids:
                for customer in budget.customer_ids:
                    if customer not in self.customer_ids:
                        self.customer_ids += customer


        self.compute_total_project_cost()
        self.compute_sale_total_project_cost()
        self.compute_project_profit()
        self.compute_project_margin()
        self._compute_contracted_sale()
        return True

    def action_upd_all(self):
        for project in self:
            project.action_update_all()

    def cron_update_cost(self):
        _logger.info(' :::::: Begin cron_update_cost :::::: ')

        steep = self.env['ir.config_parameter'].sudo().get_param(
            'update.project.step')

        position = self.env['ir.config_parameter'].sudo().get_param(
            'update.project.position')

        nrows = self.env['bim.project'].search_count([])

        if int(position) > nrows:
            next_position = 0
        else:
            next_position = int(position) + int(steep)

        self.env['ir.config_parameter'].sudo().set_param(
            'update.project.position', str(next_position))

        project_ids = self.search([], offset=int(position), limit=int(steep))

        for project in project_ids:
            _logger.info('Project: %s' % project.nombre)
            try:
                project.update_project_cost()
                project.update_sale_project_cost()
            except Exception as e:
                _logger.info('Error: %s' % e)

        _logger.info(' :::::: End cron_update_cost :::::: ')

    @api.depends('timesheet_ids')
    def _compute_timesheet_count(self):
        for project in self:
            project.timesheet_count = len(project.timesheet_ids)

    @api.depends('document_ids')
    def _compute_count_docs(self):
        for project in self:
            project.count_docs = len(project.document_ids)

    @api.depends('objects_ids')
    def _compute_count_objects(self):
        for project in self:
            project.count_objects = len(project.objects_ids)

    @api.depends('task_ids')
    def _compute_count_tasks(self):
        for project in self:
            project.task_done_count = len(project.task_ids.filtered(lambda r: r.state == 'end'))
            project.count_tasks = len(project.task_ids.filtered(lambda r: r.state != 'cancel'))
            project.count_pending_tasks = len(project.task_ids.filtered(lambda r: r.state not in ['end', 'cancel']))

    @api.depends('ticket_ids')
    def _compute_count_tickets(self):
        for project in self:
            project.ticket_done_count = len(project.ticket_ids.filtered(lambda r: r.state == 'calificado'))
            project.count_tickets = len(project.ticket_ids.filtered(lambda r: r.state != 'cancel'))

    @api.depends('employee_line_ids')
    def _compute_employee_count(self):
        for project in self:
            project.employee_count = len(project.employee_line_ids)

    def _compute_requisition(self):
        for project in self:
            project.requisition_count = len(self.env['bim.purchase.requisition'].search([('project_id','=',project.id)]))

    def _compute_services(self):
        for project in self:
            project.services_required_count = len(self.env['bim.purchase.services'].search([('project_id','=',project.id)]))

    @api.depends('paidstate_ids')
    def _compute_paidstate(self):
        for project in self:
            project.paidstatus_count = len(project.paidstate_ids)

    @api.depends('budget_ids')
    def _get_budget_count(self):
        for project in self:
            project.budget_count = len(project.budget_ids)


    def _compute_invoice(self):
        for project in self:
            invoices = project.invoice_ids
            out_invoices = invoices.filtered(lambda i: i.state == 'posted' and i.move_type == 'out_invoice')
            in_invoices = invoices.filtered(lambda i: i.state == 'posted' and i.move_type == 'in_invoice')

            refunds = invoices.filtered(lambda i: i.state == 'posted' and i.move_type == 'out_refund')
            in_refunds = invoices.filtered(lambda i: i.state == 'posted' and i.move_type == 'in_refund')

            project.out_invoice_count = len(out_invoices)
            project.in_invoice_count = len(in_invoices)


            project.out_invoiced_amount = sum(x.amount_untaxed for x in out_invoices) - sum(x.amount_untaxed for x in refunds)
            project.in_invoiced_amount = sum(x.amount_untaxed for x in in_invoices) - sum(x.amount_untaxed for x in in_refunds)

    @api.depends('budget_ids','budget_ids.balance','budget_ids.surface','budget_ids.state_id.include_in_amount')
    def _compute_amount(self):
        for project in self:
            project.balance = sum(x.balance for x in project.budget_ids.filtered_domain([('state_id.include_in_amount','=',True)]))
            project.surface = sum(x.surface for x in project.budget_ids)

    """
    @api.depends('budget_ids')
    def _compute_hh(self):
        for project in self:
            project.hh_planificadas = 0
            """

    @api.depends('stock_location_id')
    def _compute_valuation(self):
        quant_obj = self.env['stock.quant']
        for project in self:
            if project.stock_location_id:
                quants = quant_obj.search([('location_id', '=', project.stock_location_id.id)])
                project.inventory_valuation = sum(q.value for q in quants)
            else:
                project.inventory_valuation = 0


    def _compute_shipment_count(self):
        for project in self:
            shipments = self.env['tms.shipment'].search(['|',
                        ('bim_project_origin_id','=',project.id),
                        ('bim_project_destination_id','=',project.id),
                        ('state','=','confirmed')
                        ])
            project.shipment_count = len(shipments)

    def action_view_shipments(self):
        shipments = self.env['tms.shipment'].search(['|',
                            ('bim_project_origin_id','=',self.id),
                            ('bim_project_destination_id','=',self.id),
                            ('state','=','confirmed')
                            ])
        action = self.env.ref('base_bim_2.action_bim_tms_shipment').sudo().read()[0]
        action['domain'] = [('id', 'in', shipments.ids)]
        return action





    @api.depends('stock_location_id')
    def _compute_outgoing_val(self):
        picking_obj = self.env['stock.picking']
        for project in self:
            if project.stock_location_id:
                pickings = picking_obj.search([
                    ('bim_project_id','=',project.id),
                    ('location_dest_id.usage','=','customer')])
                if pickings:
                    project.outgoing_val = sum(picking.total_cost for picking in pickings)
                else:
                    project.outgoing_val = 0
            else:
                project.outgoing_val = 0


    @api.depends('state_id')
    def _get_project_state(self):
        for record in self:
            record.project_state = 'in_process'

    @api.depends('outsourcing_ids')
    def _compute_outsourcing_count(self):
        for project in self:
            project.outsourcing_count = len(project.outsourcing_ids)

    @api.depends('checklist_ids')
    def _compute_chekclist_count(self):
        for project in self:
            project.checklist_count = len(project.checklist_ids)

    @api.depends('workorder_ids')
    def _compute_workorder_count(self):
        for project in self:
            project.workorder_count = len(project.workorder_ids)

    @api.depends('balance', 'surface')
    def _compute_balance_surface(self):
        for record in self:
            if record.surface != 0:
                balace_surface = record.balance / record.surface
            else:
                balace_surface = 0.0
            record.balace_surface = balace_surface

    def compute_executed_attendance_and_cost(self):
        for record in self:
            executed = 0
            cost = 0
            for line in record.project_attendance_ids:
                executed += line.worked_hours
                cost += line.attendance_cost
            record.executed_attendance = executed
            record.attendance_cost = cost

    @api.depends('project_cost_ids','project_cost_ids.amount', 'balance','initial_coste')
    def compute_total_project_cost(self):
        for record in self:
            total = sum(line.amount for line in record.project_cost_ids)
            record.total_project_cost = record.initial_coste + total
            record.total_project_cost_difference = record.balance - total

    @api.depends('sale_project_cost_ids', 'sale_project_cost_ids.amount', 'initial_sale')
    def compute_sale_total_project_cost(self):
        for record in self:
            record.sale_total_project_cost = self.initial_sale + sum(line.amount for line in record.sale_project_cost_ids)

    @api.depends('sale_total_project_cost', 'total_project_cost')
    def compute_project_profit(self):
        for record in self:
            record.project_profit = record.sale_total_project_cost - record.total_project_cost

    @api.depends('total_project_cost','sale_total_project_cost')
    def compute_project_margin(self):
        for record in self:
            oenc = 0
            picking_analysis_ids = self.env['picking.analysis'].search([
                    ('project_id','=',record.id),
                    ('include_for_bim' ,'=', True)
                ])
            for p in picking_analysis_ids.lines_ids:
                if p.oenc == True:
                    oenc = p.subtotal
            cost = record.total_project_cost + oenc
            sale = record.sale_total_project_cost + oenc
            record.project_margin = (1 - ( cost / sale  )) * 100 if sale > 0 else 0

    def unlink(self):
        for record in self:
            if not record.env.user.has_group('base_bim_2.group_bim_delete'):
                raise AccessError(_("You do not have permission to delete projects"))

            if len(record.budget_ids) > 0:
                raise UserError(_("You can not delete a project that has budgets"))

        return super().unlink()


    def write(self, values):
        res = super().write(values)
        _do = False

        bim_general_config_id = self.env['bim.general.config'].sudo().search([
            ('key', '=', 'cuenta_analitica_unica')
        ], limit=1)

        if bim_general_config_id:
            if bim_general_config_id.value != '0':
                _do = True

        if 'analytic_id' in values and self.analytic_id:
            other_projects = self.search([('analytic_id','=',self.analytic_id.id),('id','!=',self.id)])
            if other_projects:
                analytic = self.analytic_id
                raise UserError(_("It is not possible to assign Analytic Account {} because it is already in use in Project {}").format(analytic.display_name, other_projects[0].display_name))
        return res

    @api.onchange('customer_id')
    def onchange_customer_id(self):
        if self.customer_id:
            self.street_id = self.customer_id.id

        cost_obj = self.env['bim.cost.list']
        for record in self:
            invoice_addr = False
            if self.env.company.type_work == 'costlist':
                if record.customer_id:
                    cost_list = cost_obj.search([('partner_id','=',record.customer_id.id)], limit=1)
                    if not cost_list and record.customer_id.state_id:
                        cost_list = cost_obj.search([('state_id', '=', record.customer_id.state_id.id)], limit=1)
                    if cost_list:
                        record.cost_list_id = cost_list.id
                    else:
                        record.cost_list_id = False
            if record.analytic_id:
                record.analytic_id.partner_id = record.customer_id.id
            if record.customer_id.child_ids:
                for child in record.customer_id.child_ids.filtered_domain([('type','=','invoice')]):
                    invoice_addr = child.id
                    break
            if invoice_addr:
                record.invoice_address_id = invoice_addr
            else:
                record.invoice_address_id = record.id

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    stock_location_id = fields.Many2one('stock.location', string='Stock Location')
    country_id = fields.Many2one('res.country', string='Country')
    street_id = fields.Many2one('res.partner', string='Address')
    date_ini = fields.Date('Start Date', default=fields.Date.today)
    date_end = fields.Date('End Date')
    date_ini_real = fields.Date('Start Date Real')
    date_end_real = fields.Date('End Date Real')
    expedient = fields.Char('Proceedings', translate=True)
    date_contract = fields.Date('Contract Date', help="Contract Date")
    real_date_contract = fields.Date('Real Contract Date', help="Real Contract Date")
    offer_delivered_project = fields.Boolean('Offer Delivered', help="Offer Delivered")
    adjudication_date = fields.Date('Award date')
    document_ids = fields.One2many('bim.documentation','project_id','Documents')
    objects_ids = fields.One2many('bim.object', 'project_id', 'Objects')
    count_docs = fields.Integer('Quantity Documents', compute="_compute_count_docs")
    count_objects = fields.Integer('Quantity Objets', compute="_compute_count_objects")
    count_tasks = fields.Integer('Quantity Tasks', compute="_compute_count_tasks")
    count_pending_tasks = fields.Integer('Pending Tasks', compute="_compute_count_tasks")

    count_tickets = fields.Integer('Quantity Tickets', compute="_compute_count_tickets")
    task_done_count = fields.Integer('Quantity Executed Tasks', compute="_compute_count_tasks")
    ticket_done_count = fields.Integer('Quantity Executed Tickets', compute="_compute_count_tickets")
    timesheet_count = fields.Integer('Quantity Time Sheet', compute="_compute_timesheet_count")
    timesheet_ids = fields.One2many('bim.project.employee.timesheet', 'project_id', 'Hours Employees')
    employee_count = fields.Integer('Quantity Employees', compute="_compute_employee_count")
    employee_line_ids = fields.One2many('bim.project.employee', 'project_id', 'Employee Lines')
    requisition_count = fields.Integer('Quantity Material Requests', compute="_compute_requisition")
    services_required_count = fields.Integer('Quantity Service Requests', compute="_compute_services")
    paidstate_ids = fields.One2many('bim.paidstate','project_id','Payment Status')
    paidstatus_count = fields.Integer('Quantity EP', compute="_compute_paidstate")
    paidstate_product = fields.Many2one('product.product', string='Payment Status Product', default=lambda self: self.env.company.paidstate_product)
    retention_product = fields.Many2one('product.product', string='Retention Product', default=lambda self: self.env.company.retention_product)
    department_id = fields.Many2one('bim.department', string='Departament', default=lambda self: self.env['bim.department'].search([], limit=1).id)


    invoice_ids = fields.One2many('account.move', 'project_id', 'Invoices')
    out_invoice_count = fields.Integer('Quantity Sale Invoices', compute="_compute_invoice")
    in_invoice_count = fields.Integer('Quantity Purchase Invoices', compute="_compute_invoice")
    out_invoiced_amount = fields.Monetary('Sales Invoiced Amount', compute="_compute_invoice")
    in_invoiced_amount = fields.Monetary('Purchases Invoiced Amount', compute="_compute_invoice")



    other_expense_count = fields.Integer('Other Expense  ', compute="_compute_other_expense")
    in_stock_picking_count = fields.Integer('Incoming Deliveries', compute="_compute_in_stock_picking_count")



    outgoing_val = fields.Monetary('Income by Deliveries', compute="_compute_outgoing_val")
    shipment_count = fields.Integer(compute='_compute_shipment_count')


    inventory_valuation = fields.Monetary('Inventory Valuation', compute="_compute_valuation")
    expense_val = fields.Monetary('Calculation Surrender',)
    amount_award = fields.Monetary('Award Amount',)
    amount_tender = fields.Monetary('Bid Amount',)
    analytic_created = fields.Boolean('Cost Center Created', help="Indicates if the project cost centers have already been created")

    analytic_id = fields.Many2one('account.analytic.account','Cost Center')
    tag_ids = fields.Many2many('bim.tag', string='Tags')
    outsourcing_count = fields.Integer('Subcontracts', compute="_compute_outsourcing_count")
    outsourcing_ids = fields.One2many('bim.project.outsourcing', 'project_id', 'Subcontract expenses')






    surface = fields.Float(string="Surface m2", compute='_compute_amount', help="Builded surface (m2).", store=True, digits="BIM qty")
    balance = fields.Float(string="Balance", compute='_compute_amount', help="General Balance of the Budget.", store=True, digits="BIM price")
    balace_surface = fields.Monetary(string="Balance /m2", compute=_compute_balance_surface, help="Balance per m2")
    indicator_ids = fields.One2many('bim.project.indicator', 'project_id', 'Comparative indicators')
    color = fields.Integer('Index Color', default=0)
    priority = fields.Selection(
        [('1', 'Low'),
         ('2', 'Medium'),
         ('3', 'High'),
         ], 'Priority', default='1', help="Priority")

    c_classification = fields.Selection([
        ('private', 'Private'),
        ('public', 'Public'),
        ('contractor', 'Contractor'),
        ('other', 'Other')], string='Classification')

    warranty_end_date = fields.Date('Warranty End Date', help="End date of the warranty period")
    customer_payment_mode_id = fields.Many2one('account.payment.term', string='Payment Terms', help="Payment terms for the customer")
    project_state = fields.Selection(
        [('in_process', 'Awarded'),('cancel', 'Lost')],
        string='Tracking Status',compute="_get_project_state", store=True)

    state_id = fields.Many2one(
        'bim.project.state', string='State', index=True, tracking=True,
        compute='_compute_state_id', readonly=False, store=True,
        copy=False, ondelete='restrict', default= lambda s: s.env['bim.project.state'].search([], limit=1))
    cost_list_id = fields.Many2one('bim.cost.list')
    use_cost_list = fields.Boolean(compute='_giveme_cost_list')
    edit_code_project = fields.Boolean( compute="_get_edit_code_project")


    contracted_sale = fields.Monetary('Contracted Sales', help="Total amount of contracted sales")
    expansion_contract = fields.Monetary('Expansion Contract', help="Total amount of expansion contract")
    physical_advancement_m = fields.Float('% Avance Físico M.', help="Es un campo informativo que indica el % de avance físico")
    physical_advancement_v = fields.Float('% Avance Físico V.', help="Es un campo informativo que indica el % de avance físico", compute='_compute_valuation_v')

    def _compute_valuation_v(self):
        for record in self:
            budget_ids = self.env['bim.budget'].search([('project_id','=',record.id),('state_id.include_in_amount','=',True)])
            sum_certified = sum(budget.certified for budget in budget_ids)
            sum_amount_total = sum(budget.amount_total for budget in budget_ids)
            record.physical_advancement_v = sum_certified / sum_amount_total * 100 if sum_amount_total > 0 else 0


    contracted_cost = fields.Monetary('Contracted Costs', help="Total amount of contracted costs")
    contracted_coefficient = fields.Float('Contracted Coefficient', help="Contracted coefficient",
                        compute='_compute_contracted_coefficient', store=True, digits=(10, 2))
    pending_execution = fields.Monetary('Pendiente Ejecutar', help="Pendiente Ejecutar (Contratado - Coste)",
                        compute='_compute_contracted_sale', store=True)


    @api.depends('contracted_sale','contracted_cost')
    def _compute_contracted_coefficient(self):
        for record in self:
            if record.contracted_sale > 0:
                record.contracted_coefficient = (record.contracted_sale - record.contracted_cost)/record.contracted_sale*100
            else:
                record.contracted_coefficient = 0.0

    @api.depends('contracted_sale', 'sale_total_project_cost', 'expansion_contract')
    def _compute_contracted_sale(self):
        for record in self:
            record.pending_execution = record.contracted_sale - record.sale_total_project_cost + record.expansion_contract

    def _compute_in_stock_picking_count(self):
        for project in self:
            pickings = self.env['stock.picking'].search([('bim_project_id','=',project.id),
                                                         ('location_dest_id.usage','=','internal')])
            project.in_stock_picking_count = len(pickings)

    def action_view_in_stock_picking(self):
        pickings = self.env['stock.picking'].search([('bim_project_id','=',self.id),
                                                     ('location_dest_id.usage','=','internal')])
        action = self.env.ref('stock.stock_picking_action_picking_type').sudo().read()[0]
        action['domain'] = [('id', 'in', pickings.ids)]
        return action


    def _compute_other_expense(self):
        for project in self:
            other_expense_line_ids = self.env['other.expense.line'].search([('project_id','=',self.id)])
            expenses = []
            for line in other_expense_line_ids:
                if line.other_expense_id.id not in expenses:
                    expenses.append(line.other_expense_id.id)
            project.other_expense_count = len(expenses)


    def action_view_other_expense(self):
        other_expense_line_ids = self.env['other.expense.line'].search([('project_id','=',self.id)])
        expenses = []
        for line in other_expense_line_ids:
            if line.other_expense_id.id not in expenses:
                expenses.append(line.other_expense_id.id)

        action = self.env.ref('base_bim_2.action_other_expense').sudo().read()[0]
        action['domain'] = [('id', 'in', expenses)]
        return action


    @api.onchange('customer_id')
    def onchange_customer_id(self):
        if self.customer_id:
            self.c_classification = self.customer_id.c_classification

    def _get_edit_code_project(self):
        for record in self:
            record.edit_code_project =  self.env.user.company_id.edit_code_project

    def _giveme_cost_list(self):
        if self.env.company.type_work == 'costlist':
            self.use_cost_list = True
        else:
            self.use_cost_list = False

    def action_load_recourse(self):
        _logger.info(' :::::: Begin action_load_recourse :::::: ')
        if self.budget_ids:
            for budget in self.budget_ids:
                budget.action_calculate_budget_resources()

        for line in self.project_limit_ids:
            line._compute_budget_qty()

            if line.requested_qty == 0 and line.budget_qty == 0:
                line.unlink()


    @api.depends('employee_hr_line_ids')
    def _compute_employee_hr_count(self):
        for project in self:
            project.employee_hr_count = len(project.employee_hr_line_ids)

    def action_view_employees_hr(self):
        employees = self.mapped('employee_hr_line_ids')
        action = self.env.ref('hr.open_view_employee_list_my').sudo().read()[0]
        action['domain'] = [('id', 'in', employees.ids)]
        action['context'] = {'default_default_bim_project': self.id}
        return action





    def _compute_state_id(self):
        state_obj = self.env['bim.project.state']
        for project in self:
            if not project.state_id:
                project.state_id = state_obj.search([], limit=1).id

    checklist_ids = fields.One2many('bim.checklist', 'project_id', 'Checklists')
    checklist_count = fields.Integer('N° Checklists', compute="_compute_chekclist_count")
    workorder_ids = fields.One2many('bim.work.order', 'project_id', 'Work Orders')
    workorder_count = fields.Integer('N° Work Orders', compute="_compute_workorder_count")
    price_agreed_ids = fields.One2many('bim.list.price.agreed', 'project_id', string='Agreed Prices')
    parameter_ids = fields.One2many('project.parameter', 'project_id', string='Parameter')
    project_attendance_ids = fields.One2many('hr.attendance', 'project_id' )
    executed_attendance = fields.Float(compute='compute_executed_attendance_and_cost', digits="BIM price")
    attendance_cost = fields.Float(compute='compute_executed_attendance_and_cost', digits="BIM price")
    project_cost_ids = fields.One2many('bim.project.cost', 'project_id', string='Project Costs', readonly=True)
    sale_project_cost_ids = fields.One2many('bim.project.sale', 'project_id', readonly=True)
    total_project_cost = fields.Float(string='Project Cost', compute='compute_total_project_cost', store=True, digits="BIM price")
    total_project_cost_difference = fields.Float(string='Cost Difference', compute='compute_total_project_cost', store=True, digits="BIM price")
    sale_total_project_cost = fields.Float(string='Sales', compute='compute_sale_total_project_cost', store=True, digits="BIM price")
    project_profit = fields.Float(string='Benefit', compute='compute_project_profit', store=True, digits="BIM price")
    project_margin = fields.Float(string='Margin %', compute='compute_project_margin', digits="BIM price")
    accounting_ids = fields.One2many('account.move', 'project_id', domain="[('bim_classification','=','income')]")
    incomes_value = fields.Integer(compute='compute_incomes_expenses')
    expenses_value = fields.Integer(compute='compute_incomes_expenses')
    department_required = fields.Boolean(default=lambda self: self.env.company.department_required)
    search_bim_budget_id = fields.Many2one('bim.budget', string='Budget')
    purchase_ids = fields.One2many('purchase.order','project_id')
    picking_analysis_ids = fields.One2many('picking.analysis','project_id')
    purchase_count = fields.Integer(compute='compute_purchase_count')
    picking_analysis_count = fields.Integer(compute='_compute_picking_analysis_count')

    account_payment_ids = fields.One2many('account.payment','project_id')
    account_payment_count = fields.Integer(compute='compute_account_payment_count')

    opening_balance_ids = fields.One2many('bim.opening.balance','project_id')
    opening_balance_total = fields.Integer(compute='compute_opening_balance_count', store=True)
    quality_control_plan_ids = fields.One2many('bim.quality.control.plan', 'project_id')
    quality_control_plan_count = fields.Integer(compute='compute_quality_control_plan_count')
    active = fields.Boolean(default=True)
    tool_use_ids = fields.One2many('bim.tool.use', 'project_id')
    tool_use_total = fields.Float(compute='compute_tool_use_total')


    def action_load_agreed_prices(self):
        if not self.search_bim_budget_id:
            raise UserError(_("You must select a budget to load the agreed prices"))

        # Limpiamos los precios acordados
        self.price_agreed_ids.unlink()

        resource = self.env['bim.concepts'].search([
                        ('budget_id','=',self.search_bim_budget_id.id),
                        ('type','in',['material','equipment'])])

        for res in resource:
            # Revismos si ya existe el recurso
            if not self.price_agreed_ids.filtered_domain([
                    ('project_id','=',self.id),
                    ('product_id','=',res.product_id.id)
            ]):
                self.price_agreed_ids.create({
                    'project_id': self.id,
                    'product_id': res.product_id.id,
                    'price_agreed': res.amount_fixed,
                })

    @api.depends('picking_analysis_ids')
    def _compute_picking_analysis_count(self):
        for project in self:
            project.picking_analysis_count = len(project.picking_analysis_ids)


    @api.depends('tool_use_ids','tool_use_ids.total')
    def compute_tool_use_total(self):
        for record in self:
            record.tool_use_total = sum(use.total for use in record.tool_use_ids)

    @api.depends('quality_control_plan_ids')
    def compute_quality_control_plan_count(self):
        for record in self:
            record.quality_control_plan_count = len(record.quality_control_plan_ids)

    @api.depends('opening_balance_ids','opening_balance_ids.active')
    def compute_opening_balance_count(self):
        for record in self:
            balance = 0
            for bal_rec in record.opening_balance_ids.filtered_domain([('active','=',True)]):
                balance += bal_rec.amount
            record.opening_balance_total = balance

    def compute_purchase_count(self):
        for record in self:
            record.purchase_count = len(record.purchase_ids)


    def compute_account_payment_count(self):
        for record in self:
            record.account_payment_count = len(record.account_payment_ids)

    def compute_incomes_expenses(self):
        for record in self:
            total_inc = 0
            total_exp = 0
            for move in record.accounting_ids:
                if move.bim_classification == 'income' and move.state == 'posted':
                    total_inc += move.amount_total
                elif move.bim_classification == 'expense' and move.state == 'posted':
                    total_exp += move.amount_total
            record.incomes_value = total_inc
            record.expenses_value = total_exp

    def action_view_quality_control_plan(self):
        plans = self.mapped('quality_control_plan_ids')
        action = self.env.ref('base_bim_2.action_bim_quality_control').sudo().read()[0]
        if len(plans) == 0:
            action['context'] = {'default_project_id': self.id}
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('id', 'in', plans.ids)]
            action['context'] = {'default_project_id': self.id}
        return action

    def action_view_bim_picking_analysis(self):
        analysis = self.mapped('picking_analysis_ids')
        action = self.env.ref('base_bim_2.action_picking_analysis').sudo().read()[0]
        if len(analysis) == 0:
            action['context'] = {'default_project_id': self.id}
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('id', 'in', analysis.ids)]
            action['context'] = {'default_project_id': self.id}
        return action

    def action_view_opening_balance(self):
        balances = self.mapped('opening_balance_ids')
        action = self.env.ref('base_bim_2.action_bim_opening_balance').sudo().read()[0]
        if len(balances) == 0:
            action['context'] = {'default_project_id': self.id}
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('id', 'in', balances.ids)]
            action['context'] = {'default_project_id': self.id}
        return action

    def action_view_tool_use(self):
        action = self.env.ref('base_bim_2.action_bim_tool_use').sudo().read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action


    def action_view_account_payments(self):
        payments = self.mapped('account_payment_ids')
        action = self.env.ref('account.action_account_payments').sudo().read()[0]
        if len(payments) == 0:
            action['context'] = {'default_project_id': self.id, 'default_partner_id': self.customer_id.id }
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('id', 'in', payments.ids)]
            action['context'] = {'default_project_id': self.id, 'default_partner_id': self.customer_id.id }
        return action

    def action_view_purchases(self):
        purchases = self.mapped('purchase_ids')
        context = self.env.context.copy()
        context.update(default_project_id=self.id)
        if self.street_id:
            context.update(default_place_of_delivery_id=self.street_id.id)
        return {
            'type': 'ir.actions.act_window',
            'name': u'Compras',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'view_type': 'form',
            'domain': [('id', 'in', purchases.ids)],
            'context': context
        }

    def action_view_incomes(self):
        accounting_ids = self.mapped('accounting_ids')
        action = self.env.ref('account.action_move_journal_line').sudo().read()[0]
        if len(accounting_ids) == 0:
            action['accounting_ids'] = {'default_project_id': self.id, 'default_bim_classification': 'income'}
            action['views'] = [(False, 'form')]
        else:
            incomes = []
            for income in accounting_ids:
                if income.bim_classification == 'income' and income.state == 'posted':
                    incomes.append(income.id)
            action['domain'] = [('id', 'in', incomes)]
            action['context'] = {'default_project_id': self.id, 'default_bim_classification': 'income'}
        return action

    def action_view_expenses(self):
        accounting_ids = self.mapped('accounting_ids')
        action = self.env.ref('account.action_move_journal_line').sudo().read()[0]
        if len(accounting_ids) == 0:
            action['context'] = {'default_project_id': self.id, 'default_bim_classification': 'expense'}
            action['views'] = [(False, 'form')]
        else:
            expenses = []
            for expense in accounting_ids:
                if expense.bim_classification == 'expense' and expense.state == 'posted':
                    expenses.append(expense.id)
            action['domain'] = [('id', 'in', expenses)]
            action['context'] = {'default_project_id': self.id, 'default_bim_classification': 'expense'}
        return action



    @api.constrains('state_id')
    def _check_state_id(self):
        for record in self:
            if record.state_id.set_budget_state_id:
                for budget in record.budget_ids:
                    budget.state_id = record.state_id.set_budget_state_id




    @api.onchange('state_id')
    def onchange_state_id(self):
        if self.state_id.user_ids and self.env.user.id not in self.state_id.user_ids.ids:
            users = ""
            for user in self.state_id.user_ids:
                users += user.display_name + ", "
            raise UserError(
                _("Only users {} can set current Project to state {}").format(users[:-2], self.state_id.name))

        if self.state_id.required_fields:
            fields = self.state_id.required_fields.split(',')
            for field in fields:
                if not getattr(self, field):
                    raise UserError(_("Field {} is required").format(field))

    @api.onchange('warehouse_id')
    def onchange_stock(self):
        if self.warehouse_id:
            self.stock_location_id = self.warehouse_id.lot_stock_id.id

    """
    @api.onchange('warehouse_id','stock_location_id')
    def onchange_stock(self):
        if not self.stock_location_id and self.warehouse_id:
            self.stock_location_id = self.warehouse_id.lot_stock_id.id

        if not self.warehouse_id:
            self.stock_location_id = False

        if self.stock_location_id:
            warehouse = self.env['stock.warehouse'].search([('lot_stock_id','=',self.stock_location_id.id)],limit=1)
            if warehouse and self.warehouse_id != warehouse:
                self.warehouse_id = warehouse.id"""

    @api.onchange('date_end','date_ini')
    def onchange_date(self):
        if not self.date_ini:
           datetime.now()

        if self.date_end and self.date_end <= self.date_ini:
            warning = {
                'title': _('Warning!'),
                'message': _(u'The End Date cannot be less than the start date!'),
            }
            self.date_end = False
            return {'warning': warning}


    def create_warehouse(self):
        _logger.info('Creating warehouse')
        for project in self:
            _logger.info('Creating warehouse for project %s', project.name)
            name = project.company_id.warehouse_prefix + ' ' + project.nombre
            _logger.info(name)

            vals = {
                'name': name,
                'code': project.name[-4:].replace('/','').replace('-','').replace(' ',''),
                'partner_id': project.customer_id and project.customer_id.id or False,
                'company_id': project.company_id.id,
            }

            _logger.info(vals)

            warehouse = self.env['stock.warehouse'].sudo().create(vals)
            _logger.info("1")

            project.warehouse_id = warehouse.id
            _logger.info("2")

            project.stock_location_id = warehouse.lot_stock_id.id
            _logger.info("3")

    def create_project_object(self):
        for project in self:
            vals = {
                'desc': project.name + ' ' + project.nombre,
                'project_id': project.id,
            }
            self.env['bim.object'].sudo().create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        company = self.env.company
        auto_tasks = self.env['bim.task'].search([('project_auto_create', '=', True)])

        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                sequence_by_year = company.sequence_by_year

                if sequence_by_year:
                    first_letter_company = (company.name or 'X')[0]
                    year_two_digits = str(datetime.now().year)[2:]

                    bim_general_config = self.env['bim.general.config'].search([
                        ('company_id', '=', company.id),
                        ('key', '=', 'sequence')
                    ], limit=1)

                    if bim_general_config:
                        last_code = bim_general_config.value or '0'
                        try:
                            next_code = int(last_code) + 1
                        except ValueError:
                            next_code = 1
                        bim_general_config.value = str(next_code)
                        code = f"{first_letter_company}{year_two_digits}/{str(next_code).zfill(3)}"
                    else:
                        raise UserError(_('No sequence found for company %s') % company.name)
                else:
                    code = self.env['ir.sequence'].sudo().next_by_code('bim.project') or 'New'

                # Crear cuenta analítica
                if company.create_analytic_account:
                    try:
                        plan = self.env['account.analytic.plan'].sudo().search([], limit=1)
                        if not plan:
                            raise UserError(_('No plan found for company %s') % company.name)

                        analytic_vals = {
                            'name': vals.get('nombre') or code,
                            'plan_id': plan.id,
                            'code': code,
                        }
                        if vals.get('customer_id'):
                            analytic_vals['partner_id'] = vals['customer_id']

                        analytic = self.env['account.analytic.account'].sudo().create(analytic_vals)
                        vals['analytic_id'] = analytic.id
                    except Exception as e:
                        _logger.info('Error creating analytic account: %s', e)

                vals['name'] = code

        projects = super().create(vals_list)

        # Crear tareas automáticas después de crear el proyecto
        if auto_tasks:
            task_vals_list = []
            for project in projects:
                for task in auto_tasks:
                    task_vals_list.append({
                        'desc': task.desc,
                        'project_id': project.id,
                    })
            if task_vals_list:
                self.env['bim.task'].create(task_vals_list)

        for project in projects:
            project.create_project_object()

        return projects

    def name_get(self):
        res = super(bim_project, self).name_get()
        result = []
        for element in res:
            project_id = element[0]
            cod = self.browse(project_id).name
            desc = self.browse(project_id).nombre
            name = cod and '[%s] %s' % (cod, desc) or '%s' % desc
            result.append((project_id, name))
        return result

    def action_view_attendance(self):
        project_attendance_ids = self.mapped('project_attendance_ids')
        action = self.env.ref('hr_attendance.hr_attendance_action').sudo().read()[0]
        if self.state_id and not self.state_id.include_in_attendance:
            action['conntext'] = {'create': 0}
            action['domain'] = [('id', 'in', project_attendance_ids.ids)]
            subject = _("It is not possible register attendance during state %s") % self.state_id.name
            self.env["bus.bus"]._sendone(
                    self.env.user.partner_id,
                    "simple_notification",
                    {"title": "", "message": subject, "warning": True},
                )
        else:
            if len(project_attendance_ids) == 0:
                action['context'] = {'default_project_id': self.id}
                action['views'] = [(False, 'form')]
            else:
                action['domain'] = [('id', 'in', project_attendance_ids.ids)]
                action['context'] = {'default_project_id': self.id}
        return action

    def action_view_budgets(self):
        budgets = self.mapped('budget_ids')
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        if len(budgets) > 0:
            action['domain'] = [('id', 'in', budgets.ids)]
            action['context'] = {'default_project_id': self.id,'default_currency_id': self.currency_id.id}
            return action
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Budget',
                'res_model': 'bim.budget',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_project_id': self.id,'default_currency_id': self.currency_id.id}
            }

    def action_view_requisitions(self):
        requsitions = self.env['bim.purchase.requisition'].search([('project_id','=',self.id)])
        action = self.env.ref('base_bim_2.action_bim_purchase_requisition').sudo().read()[0]
        action['domain'] = [('id', 'in', requsitions.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_services_required(self):
        services = self.env['bim.purchase.services'].search([('project_id','=',self.id)])
        action = self.env.ref('base_bim_2.action_bim_purchase_services').sudo().read()[0]
        action['domain'] = [('id', 'in', services.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_timesheets(self):
        timesheets = self.mapped('timesheet_ids')
        action = self.env.ref('base_bim_2.action_bim_project_timesheet').sudo().read()[0]
        if len(timesheets) > 0:
            action['domain'] = [('id', 'in', timesheets.ids)]
        else:
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'bim.project.employee.timesheet',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_projects_id': self.id}
            }
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_timesheets(self):
        timesheets = self.mapped('timesheet_ids')
        action = self.env.ref('base_bim_2.action_bim_project_timesheet').sudo().read()[0]
        if len(timesheets) > 0:
            action['domain'] = [('id', 'in', timesheets.ids)]
        else:
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'bim.project.employee.timesheet',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_projects_id': self.id}
            }
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_outsourcing(self):
        outsourcings = self.mapped('outsourcing_ids')
        action = self.env.ref('base_bim_2.action_bim_project_outsourcing').sudo().read()[0]
        action['domain'] = [('id', 'in', outsourcings.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_employees(self):
        employees = self.mapped('employee_line_ids')
        action = self.env.ref('base_bim_2.action_bim_project_employee').sudo().read()[0]
        action['domain'] = [('id', 'in', employees.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_documents(self):
        documents = self.mapped('document_ids')
        action = self.env.ref('base_bim_2.action_bim_documentation').sudo().read()[0]
        action['domain'] = [('id', 'in', documents.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_objects(self):
        bim_objects = self.mapped('objects_ids')
        action = self.env.ref('base_bim_2.action_bim_object').sudo().read()[0]
        action['domain'] = [('id', 'in', bim_objects.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_checklist(self):
        checklists = self.mapped('checklist_ids')
        action = self.env.ref('base_bim_2.bim_checklist_action').sudo().read()[0]
        action['domain'] = [('id', 'in', checklists.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_workorder(self):
        workorders = self.mapped('workorder_ids')
        action = self.env.ref('base_bim_2.action_work_orders_project').sudo().read()[0]
        action['domain'] = [('id', 'in', workorders.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_tasks(self):
        tasks = self.mapped('task_ids')
        action = self.env.ref('base_bim_2.action_bim_task').sudo().read()[0]
        action['domain'] = [('id', 'in', tasks.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_tickets(self):
        tickets = self.mapped('ticket_ids')
        action = self.env.ref('base_bim_2.action_ticket_bim').sudo().read()[0]
        action['domain'] = [('id', 'in', tickets.ids)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_view_out_invoices(self):
        invoices = []
        for inv in self.invoice_ids:
            if inv.move_type == 'out_invoice':
                invoices.append(inv.id)
        action = self.env.ref('account.action_move_out_invoice_type').sudo().read()[0]
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_in_invoices(self):
        invoices = []
        for inv in self.invoice_ids:
            if inv.move_type == 'in_invoice':
                invoices.append(inv.id)
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_outgoings(self):
        action = {'type': 'ir.actions.act_window_close'}
        if self.stock_location_id:
            pickings = self.env['stock.picking'].search([
                ('bim_project_id','=',self.id),
                ('location_dest_id.usage','=','customer'),
            ])
            pickings += self.env['stock.picking'].search([
                ('bim_project_id', '=', self.id),
                ('location_id.usage', '=', 'customer'),('returned', '=', True)
            ])
            if len(pickings) > 0:
                action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]
                action['domain'] = [('id', 'in', pickings.ids)]
        return action

    def action_view_quants(self):
        action = self.env.ref('stock.dashboard_open_quants').sudo().read()[0]
        action['domain'] = [('location_id', '=', self.stock_location_id.id)]
        action['context'] = {'search_default_productgroup': 1, 'search_default_internal_loc': 1}
        return action

    def action_view_paidstate(self):
        paidstate = self.mapped('paidstate_ids')
        action = self.env.ref('base_bim_2.action_bim_paidstate').sudo().read()[0]
        action['domain'] = [('id', 'in', paidstate.ids)]
        action['context'] = {'default_project_id': self.id}
        return action



    def update_project_cost(self):
        self.update_date_all = datetime.now()
        self.project_cost_ids.unlink()

        # Calculamos los costes de asistencia de los partners
        partner_attendance_ids = self.env['partner.attendance'].search([
                                                               ('project_id','=', self.id),
                                                               ('include_in_bim','=',True)
                                                           ])
        total_partner_cost = sum(attendance.balance for attendance in partner_attendance_ids)

        if total_partner_cost > 0:
            self.env['bim.project.cost'].create({
                'project_id': self.id,
                'type': 'partner_attendance',
                'amount': total_partner_cost
            })


        # purchase_valuation
        purchase_valuation_ids = self.env['purchase.valuation'].search([
                                                           ('project_id','=', self.id),
                                                           ('include_for_bim','=',True),
                                                           ('state','in',['done'])
                                                           ])
        purchase_valuation = sum(valuation.price_subtotal for valuation in purchase_valuation_ids)

        _logger.info('purchase_valuation_ids: %s', purchase_valuation_ids)
        _logger.info('purchase_valuation: %s', purchase_valuation)

        if purchase_valuation > 0:
            self.env['bim.project.cost'].create({
                'project_id': self.id,
                'type': 'purchase_valuation',
                'amount': purchase_valuation
            })

        # calculamos las horas presupuestada para los conceptos de tipo mano de obra
        budgeted_hours = 0
        budget_obj = self.env['bim.budget'].search([('project_id','=',self.id)])
        for budget in budget_obj:
            budgeted_hours += sum(budget.concept_ids.filtered(lambda c: c.type == 'departure').mapped('resume_hh'))
        self.budgeted_hours = budgeted_hours


        # Creando líneas para costos de Asistencia
        total = 0
        real_hours = 0
        cost_obj = self.env['bim.project.cost']
        include_vat = self.company_id.include_vat_in_indicators
        for attendance in self.project_attendance_ids:
            if attendance.employee_id and attendance.employee_id.include_for_bim:
                total += attendance.attendance_cost
                real_hours += attendance.worked_hours

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'attendance',
                'amount': total
            })

        if real_hours > 0:
            self.real_hours = real_hours


        # mantenimiento
        total = 0
        cost_obj = self.env['bim.project.cost']
        maintenance_task_ids = self.env['maintenance.task'].search([
                    ('bim_project_id','=', self.id),
                ])

        if maintenance_task_ids:
            for task in maintenance_task_ids:
                if task.include_for_bim:
                    total += task.cost

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'maintenance_tasks',
                'amount': total
            })



        # transport
        total = 0
        tms_shipment_ids = self.env['tms.shipment'].search(['|',
                    ('bim_project_destination_id','=', self.id),
                    ('bim_project_origin_id','=', self.id),
                ])

        if tms_shipment_ids:
            for shipment in tms_shipment_ids:
                if shipment.state == 'confirmed':
                    total += shipment.total

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'transport',
                'amount': total
            })


        # other.expense
        other_expense_ids = self.env['other.expense.line'].search([
                    ('project_id','=', self.id),
                    ('other_expense_id.state','=','done'),
                    ])
        if other_expense_ids:
            amount_total = sum(other_expense.total for other_expense in other_expense_ids)
            if amount_total > 0:
                cost_obj.create({
                    'project_id': self.id,
                    'type': 'other_expense',
                    'amount': amount_total
                })


        # project.estimate
        project_estimate_ids = self.env['project.estimate'].search([('project_id','=', self.id),
                                                              ('include_bim','=',True)])
        if project_estimate_ids:
            amount_total = sum(estimate.amount_total for estimate in project_estimate_ids)

            if amount_total > 0:
                cost_obj.create({
                    'project_id': self.id,
                    'type': 'project_estimate',
                    'amount': amount_total
                })




        ##Creando líneas para costos de Facturacion
        total = 0
        if self.analytic_id:
            analytic_lines = self.env['account.analytic.line'].search([('account_id','=',self.analytic_id.id),('move_line_id','!=',False),
                                                                       ('move_line_id.move_id.move_type','in',['in_invoice','in_refund']),
                                                                       ('move_line_id.move_id.include_for_bim','=',True),
                                                                       ('move_line_id.move_id.state','=','posted'),('move_line_id.display_type','=','product')])
            for line in analytic_lines:
                if line.move_line_id.move_id.move_type == 'in_invoice':
                    tmp = (line.amount - sum(tax_line.amount * line.amount / 100 for tax_line in line.move_line_id.tax_ids) if include_vat else line.amount) * -1
                    total = total + tmp
                else:
                    tmp = line.amount + sum(tax_line.amount * line.amount / 100 for tax_line in line.move_line_id.tax_ids) if include_vat else line.amount
                    total = total - tmp

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'purchase_invo',
                'amount': total
            })

        ##Creando líneas para apuntes contables
        total = 0
        moves_expenses = self.env['account.move'].search([('bim_classification','=','expense'),('state','=','posted'),('include_for_bim','=',True),('company_id','=',self.company_id.id)])
        for move in moves_expenses:
            take_it = False
            for line in move.line_ids:
                analytics = list(line.analytic_distribution.keys())
                if analytics:
                    analytic_account_id = int(analytics[0])
                    if analytic_account_id == self.analytic_id.id:
                        take_it = True
                        break
            if take_it:
                total += move.amount_total

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'other',
                'amount': total
            })

        total = 0
        for budget in self.budget_ids:
            for concept in budget.concept_ids.filtered(lambda c: c.type == 'departure'):
                for part in concept.part_ids.filtered(lambda c: c.state == 'validated'):
                    for line in part.lines_ids:
                        total += line.price_subtotal
        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'report',
                'amount': total
            })

        # aqui vamos a tomar los costos de las entregas
        _value = "1"
        bim_general_config_id = self.env['bim.general.config'].search([
            ('key', '=', 'type_cost')
        ], limit=1)

        if bim_general_config_id:
            _value = str(bim_general_config_id.value)

        _logger.info('type_cost: %s', _value)

        picking_obj = self.env['stock.picking']

        # Sumamos las salidas
        _logger.info('==================== pickings ======================')
        domain = [
                    ('bim_project_id', '=', self.id),
                    ('state', '=', 'done'),
                    ('include_for_bim', '=', True),
                    ('picking_type_id.code', 'in', ['outgoing'])
                  ]
        pickings = picking_obj.search(domain)

        _logger.info('pickings salidas %s', pickings)
        total = 0

        _logger.info('total 1>> %s', total)

        for picking in pickings:
            _logger.info('picking %s', picking.picking_type_id.code)
            if _value == '1':
                total += picking.total_cost
            else:
                total -= picking.total_cost

        _logger.info('total 2>> %s', total)



        # solo albaranes de entrada
        move_total_cost = 0
        _arr = [
            ('picking_id.include_for_bim', '=', True),
            ('bim_project_id', '=', self.id),
            ('picking_id.state', '=', 'done'),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
        ]
        stock_move_ids = self.env['stock.move'].search(_arr)
        move_total_cost = sum(move.subtotal for move in stock_move_ids)

        # solo albaranes de devolución de una entrada
        _arr_return = [
            ('picking_id.include_for_bim', '=', True),
            ('bim_project_id', '=', self.id),
            ('picking_id.state', '=', 'done'),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
            ('picking_id.returned', '=', True)
        ]
        stock_move_ids_return = self.env['stock.move'].search(_arr_return)
        move_total_cost_return = sum(move.subtotal for move in stock_move_ids_return)

        total += move_total_cost
        total -= move_total_cost_return




        # Restamos las devoluciones
        domain = [('bim_project_id', '=', self.id),
                  ('state', '=', 'done'),
                  ('include_for_bim', '=', True),
                  ('picking_type_id.code', 'in', ['incoming'])
                  ]
        pickings = picking_obj.search(domain)
        _logger.info('pickings entradas %s', pickings)

        for picking in pickings:
            if _value == '1':
                total -= picking.total_cost
            else:
                total += picking.total_cost

        _logger.info('total 3>> %s', total)

        if total != 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'delivery',
                'amount': abs(total),
            })



        #aqui metemos los saldos de apertura
        total = sum(bal.amount for bal in self.opening_balance_ids)
        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'open',
                'amount': total
            })


        if self.tool_use_total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'tool',
                'amount': self.tool_use_total
            })

        cost = sum(rent.amount_total for rent in self.project_tool_rent_ids.filtered(lambda x: x.state in ('rented','finished')))
        if cost > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'tool_rent',
                'amount': cost
            })

        return True

    def update_sale_project_cost(self):
        self.update_date_all = datetime.now()
        for line in self.sale_project_cost_ids:
            line.unlink()
        # Creando líneas para costos de Asistencia
        total = 0
        cost_obj = self.env['bim.project.sale']
        include_vat = self.company_id.include_vat_in_indicators
        if self.analytic_id:
            analytic_lines = self.env['account.analytic.line'].search(
                [('account_id', '=', self.analytic_id.id), ('move_line_id', '!=', False),
                 ('move_line_id.move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                 ('move_line_id.move_id.include_for_bim', '=', True),
                 ('move_line_id.move_id.state', '=', 'posted'),('move_line_id.display_type','=','product')])
            for line in analytic_lines:
                if line.move_line_id.move_id.move_type == 'out_refund':
                    tmp = (line.amount - sum(tax_line.amount * line.amount / 100 for tax_line in
                                             line.move_line_id.tax_ids) if include_vat else line.amount) * -1
                    total = total - tmp
                else:
                    tmp = line.amount + sum(tax_line.amount * line.amount / 100 for tax_line in
                                            line.move_line_id.tax_ids) if include_vat else line.amount
                    total = total + tmp
        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'sale_invo',
                'amount': total
            })

        total = 0
        moves_incomes = self.env['account.move'].search(
            [('bim_classification', '=', 'income'), ('state', '=', 'posted'),('include_for_bim','=',True)])
        for move in moves_incomes:
            take_it = False
            for line in move.line_ids:
                analytics = list(line.analytic_distribution.keys())
                if analytics:
                    analytic_account_id = int(analytics[0])
                    if analytic_account_id == self.analytic_id.id:
                        take_it = True
                        break
            if take_it:
                total += move.amount_total

        if total > 0:
            cost_obj.create({
                'project_id': self.id,
                'type': 'other',
                'amount': total
            })

        picking_analysis_ids = self.env['picking.analysis'].search([
                                ('project_id', '=', self.id),
                                ('include_for_bim', '=', True)])

        _logger.info('picking_analysis_ids: %s', picking_analysis_ids)
        return True


class BimProjectOutsourcing(models.Model):
    _description = "Work Subcontracts Expenses"
    _name = 'bim.project.outsourcing'
    _rec_name = 'partner_id'

    name = fields.Char('Description')
    partner_id = fields.Many2one('res.partner', 'Supplier')
    project_id = fields.Many2one('bim.project', 'Project')
    reference = fields.Char('Reference EP')
    date = fields.Date('Date', default=fields.Date.today())
    amount = fields.Monetary('Balance')
    outsourcing_amount = fields.Monetary('Total')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda r: r.env.user.company_id.currency_id)


class BimProjectEmployee(models.Model):
    _description = "Construction Employees"
    _name = 'bim.project.employee'
    _order = 'start_date asc'

    project_id = fields.Many2one('bim.project', 'Project', domain="[('company_id','=',company_id)]")
    employee_id = fields.Many2one('hr.employee', 'Employee')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    company_id = fields.Many2one(comodel_name="res.company", string="Company",
        default=lambda self: self.env.company, required=True)


class BimProjectEmployeeTimesheet(models.Model):
    _description = "Bim Project Employee Timesheet"
    _name = 'bim.project.employee.timesheet'
    _order = 'name desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id and self.task_id:
            self.project_id = self.task_id.project_id.id

    @api.model
    def default_get(self, fields):
        res = super(BimProjectEmployeeTimesheet, self).default_get(fields)
        today = date.today()
        start = today - timedelta(days=today.weekday())
        res['week_start'] = datetime.strftime(start, '%Y-%m-%d')
        res['week_end'] = datetime.strftime((start + timedelta(days=6)), '%Y-%m-%d')
        return res

    project_id = fields.Many2one('bim.project', 'Project',
                                 domain="[('company_id','=',company_id)]")
    partner_id = fields.Many2one('res.partner', 'Customer', related='project_id.customer_id', store=True)
    budget_id = fields.Many2one('bim.budget', string='Budget',
                                domain="[('project_id','=',project_id),('state_id.project_part','=',True)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="cascade", domain="[('type','=','departure')]")

    task_id = fields.Many2one('bim.task', 'Task')
    date = fields.Date('Date', default=fields.Date.today)
    week_start = fields.Date('Start Week')
    week_end = fields.Date('End Week')
    employee_id = fields.Many2one('hr.employee', 'Employee', default=lambda self: self.env.user.employee_id)
    total_hours = fields.Float('Total Hours', digits="BIM qty")
    total_extra_hours = fields.Float('Total Extra Hours', digits="BIM qty")
    week_number = fields.Integer('Week Number', compute='compute_week_number', store=True)
    work_cost = fields.Float('Total Cost', digits="BIM price")
    work_price = fields.Float('Total Price', digits="BIM price")
    extra_work_cost = fields.Float('Labor Cost HE',
                                   help="Cost of overtime labor",
                                   digits="BIM price")
    comment = fields.Text('Comments', default="")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True )
    bim_extra_hour = fields.Many2one('bim.extra.hour', 'Extra Hour')
    name = fields.Char('Code', default="New", copy=False, readonly=True)
    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', 'Certification')
    state = fields.Selection(
        [('draft', 'Draft'),
         ('ready', 'Validated'),
         ('approved', 'Approved'),
         ('done', 'Certified'),
         ('cancelled', 'Cancelled')], tracking=True, default='draft', string='Status', required=True)

    bim_project_employee_timesheet_summary = fields.Many2one('bim.project.employee.timesheet.summary', 'Summary')

    # action_cancel
    def action_cancel(self):
        self.state = 'cancelled'

    def action_validate(self):
        if self.total_hours > 0:
            self.state = 'ready'
        else:
            raise ValidationError(_("You must enter the total hours"))

    def action_approved(self):
        self.state = 'approved'

    def action_draft(self):
        self.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.project.employee.timesheet') or 'New'
        return super().create(vals_list)

    # Onchange project_id
    @api.onchange('project_id','task_id')
    def onchange_project_id(self):
        if self.project_id and self.task_id:
            self.budget_id = self.task_id.budget_id.id
            self.concept_id = self.task_id.concept_id.id

    # Onchange employee_id
    @api.onchange('employee_id','bim_extra_hour','total_hours')
    def onchange_employee_id(self):
        for record in self:
            hour_price = 0
            hour_wage = 0
            bim_client_hour = record.env['bim.client.hour'].search([
                ('partner_id', '=', record.partner_id.id)], limit=1)
            if bim_client_hour:
                hour_price = bim_client_hour.price

            if record.bim_extra_hour and bim_client_hour:
                hour_wage = record.bim_extra_hour.value
                bim_client_hour_line = record.env['bim.client.hour.line'].search([
                        ('bim_client_hour_id','=',bim_client_hour.id),
                        ('bim_extra_hour_id','=',record.bim_extra_hour.id),
                        ('name','=',record.employee_id.id)], limit=1)
                if bim_client_hour_line:
                    hour_price = bim_client_hour_line.price
            else:
                hour_wage = record.employee_id.hour_cost

            record.work_cost = hour_wage * record.total_hours
            record.work_price = hour_price * record.total_hours


    @api.depends('week_start')
    def compute_week_number(self):
        for record in self:
            if record.week_start:
                today = date.today()
                year = int(record.week_start.year)
                month = int(record.week_start.month)
                day = int(record.week_start.day)
                number_week = date(year, month, day).strftime("%V")
                record.week_number = number_week


class bim_obra_indicator(models.Model):
    _description = "Comparative indicators"
    _name = 'bim.project.indicator'

    @api.depends('projected', 'budget')
    def _compute_percent(self):
        for record in self:
            record.percent = record.budget > 0.0 and (record.projected / record.budget * 100) or 0.0

    @api.depends('real', 'projected')
    def _compute_diff(self):
        for record in self:
            record.projected = record.budget - record.real

    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    currency_id = fields.Many2one('res.currency', 'Currency', related="project_id.currency_id")
    type = fields.Selection(
        [('M', 'Material Cost'),
         ('Q', 'Equipment Cost'),
         ('H', 'Labor Cost'),
         ('S', 'Sub-Contract Cost'),
         ('HR', 'Tools Costs'),
         ('LO', 'Logistic Cost'),
         ('T', 'Total'), ],
        'Indicator Type', readonly=True)

    budget = fields.Monetary('Budget', help="Budget Amount", readonly=True)
    real = fields.Monetary('Real Certified', help="Actual value represented in the awarded budget", readonly=True)
    projected = fields.Float('Projected', help="Difference between projected and actual", compute="_compute_diff", digits="BIM price")
    percent = fields.Float('%', help="Percentage given by the real value between the estimated value", compute="_compute_percent")


class BimProjectCost(models.Model):
    _description = "Project Cost"
    _name = 'bim.project.cost'

    type = fields.Selection([('attendance','Attendance'),
                             ('project_estimate','Project Estimate'),
                             ('delivery','Cost Deliveries'),
                             ('report','Project Report'),
                             ('purchase_invo','Purchase Invoices'),
                             ('open','Opening Balance'),
                             ('partner_attendance','Partner Attendance'),
                             ('fuel','Fuel'),
                             ('transport','Transport'),
                             ('other_expense','Other Expense'),
                             ('tool_rent','Tools rent'),
                             ('tool','Tools'),
                             ('purchase_valuation','Purchase Valuation'),
                             ('maintenance_tasks','Maintenance Tasks'),
                             ('other','Other expenses')], string='Type')

    amount = fields.Monetary(string='Amount')
    project_id = fields.Many2one('bim.project')
    currency_id = fields.Many2one('res.currency', related='project_id.currency_id')


class BimProjectCost(models.Model):
    _description = "Project Sales"
    _name = 'bim.project.sale'

    type = fields.Selection([('sale_invo','Sale Invoices'),('other','Other Incomes')], string='Type')
    amount = fields.Monetary(string='Amount')
    project_id = fields.Many2one('bim.project')
    currency_id = fields.Many2one('res.currency', related='project_id.currency_id')