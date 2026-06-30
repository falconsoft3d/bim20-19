import base64
import io
from datetime import date, timedelta
import re
from dateutil.relativedelta import relativedelta
import logging
import random, string
import xlwt
from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError, ValidationError
_logger = logging.getLogger(__name__)
import time

try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
except (ImportError, IOError):
    plt = False
    _logger.info('Missing external dependency matplotlib.')

inconsistency = {
    '0': 'No inconsistencies were found in the Budget.',
    '1': '-Resource %s has no Product assigned (Concept Error).',
    '2': '-Product %s, assigned to Resource %s, is not of Material Resource Type (Product Error).',
    '3': '-Product %s, assigned to Resource %s, is not of Type Resource Equipment (Product Error).',
    '4': '-Product %s, assigned to Resource %s, is not of Type Resource Labor (Product Error).',
    '5': '-Product %s, assigned to Resource %s, is a Service (Product Error).',
    '6': '-Product %s, assigned to Resource %s, is Storable (Product Error).',
    '7': '-Resource %s amount is zero (0).',
    '8': '-Chapter %s has quantity greater than 1.',
    '9': '-Resource %s has Child assigned (Concept Error).',
    '10': '-UoM of Resource %s is different than UoM of related Product %s. (Parent %s)',
}


class BimBudgetState(models.Model):
    _name = 'bim.budget.state'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bim Budget State'
    _order = "sequence asc, id desc"

    name = fields.Char(required=True, translate=True)
    is_new = fields.Boolean()

    put_costs = fields.Boolean(string="Put Costs", default=True)
    include_in_amount = fields.Boolean(string="Include in amount", default=True, tracking=True)
    material_request = fields.Boolean(string="Register Material Request", default=True, tracking=True)
    project_part = fields.Boolean(string="Register Project Part", default=True, tracking=True)
    required_fields = fields.Char('Required Fields', help="Fields required to change the state of the project")

    include_in_attendance = fields.Boolean(string="Register Attendance", default=True, tracking=True)
    include_in_open_balance = fields.Boolean(string="Register Open Balance", default=True, tracking=True)
    include_in_tools = fields.Boolean(string="Register Tool Cost", default=True, tracking=True)
    convert_virtual_product = fields.Boolean(string="Convert Virtual Products", default=True, tracking=True)
    is_done = fields.Boolean()
    sequence = fields.Integer(default=16)
    user_ids = fields.Many2many('res.users', string="Users")
    allow_certification = fields.Boolean(default=True, tracking=True)
    lock_budget = fields.Boolean(default=False, tracking=True, string="Lock Budget")
    allow_supplier_invoice = fields.Boolean(string="Allow Supplier Invoice", default=True)
    allow_supplier_purchase = fields.Boolean(string="Allow Supplier Purchase", default=True)


    write_utility = fields.Boolean(string="Write Utility", default=True)

    type_invoice = fields.Selection([
        ('out_invoice', 'Sale'),
        ('in_invoice', 'Purchase')
    ], string="Type Invoice",
        help="Select the type of invoice to be generated when certifying the budget.",
        default='out_invoice')

    bim_project_state_ids = fields.Many2many('bim.project.state', 'bim_budget_state_id', string='Project States')


class BimBudget(models.Model):
    _name = 'bim.budget'
    _description = 'Budgets'
    _order = 'code desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    def create_general(self):
        # Creamos el capitulo general
        chapter_id = self.env['bim.concepts'].create({
            'name': 'General',
            'code': 'G1',
            'type': 'chapter',
            'budget_id': self.id,
        })

        if chapter_id:
            # Recorremos todos los conceptos sin padres y le ponemos este padre
            for concept in self.concept_ids.filtered(lambda c: not c.parent_id):
                concept.parent_id = chapter_id.id


    @api.constrains('code')
    def _check_main_code(self):
        for record in self:
            if self.env['bim.budget'].search_count([('code', '=', record.code)]) > 1:
                raise ValidationError("El código del presupuesto debe ser único")

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if 'project_id' in values:
            project = self.env['bim.project'].browse(values['project_id'])
            if project.cost_list_id:
                values['cost_list_id'] = project.cost_list_id.id
        return values


    def _compute_amount(self):
        for budget in self:
            balance = 0
            certified = 0

            if budget.pvp_id and budget.template_id:
                asset_id = budget.pvp_id.asset_id
                balance = self.env['bim.budget.assets'].search([('budget_id', '=', budget.id),
                ('asset_id', '=', asset_id.id)], limit=1).total
            else:
                balance =  budget.amount_total_cd

           # asset_ids buscamos el que contenta en el nombre IVA, TAX
            iva = sum(budget.asset_ids.filtered(lambda a: 'IVA' in a.asset_id.desc).mapped('total_apu'))


            if budget.certification_ids:
                certified = sum(budget.certification_ids.mapped('total_certif'))
            elif budget.chapter_certification_ids:
                certified = sum(budget.chapter_certification_ids.mapped('total_certif'))

            budget.balance = balance
            budget.certified = certified
            budget.iva = iva


            if budget.utility > 0:
                last_level_dep = budget.concept_ids.filtered(lambda r: r.type == 'departure')
                budget.sale_import = sum([x.sale_amount for x in last_level_dep])
                budget.amount_total = budget.balance + budget.iva
            else:
                if budget.type_calc_amount == 'from_departure':
                    last_level_dep = budget.concept_ids.filtered(lambda r: r.type == 'departure')
                    budget.amount_total = sum([x.sale_amount for x in last_level_dep])
                    budget.amount_total_cd = budget.amount_total
                    budget.balance = budget.amount_total
                else:
                    budget.amount_total = budget.balance + budget.iva


    @api.depends('concept_ids')
    def _compute_execute(self):
        for budget in self:
            concept_ids = budget.concept_ids.ids

            concepts = budget.concept_ids
            equipments = concepts.filtered(lambda c: c.type == 'equip')
            materials = concepts.filtered(lambda c: c.type == 'material')
            labors = concepts.filtered(lambda c: c.type == 'labor')
            functions = concepts.filtered(lambda c: c.type == 'aux')
            subcontract = concepts.filtered(lambda c: c.type == 'subcontract')

            departures = concepts.filtered(lambda c: c.type == 'departure')

            budget.amount_executed_equip = sum(e.amount_execute_equip for e in departures)
            budget.amount_executed_labor = sum(l.amount_execute_labor for l in departures)
            budget.amount_executed_material = sum(m.amount_execute_material for m in departures)
            budget.amount_executed_other = sum(f.amount_execute for f in functions)
            budget.amount_executed_subcontract = sum(s.amount_execute for s in subcontract)

    def _get_value(self, quantity, product):
        if product.cost_method == 'fifo':
            quantity = product.quantity_svl
            if float_is_zero(quantity, precision_rounding=product.uom_id.rounding):
                value = 0.0
            average_cost = product.value_svl / quantity
            value = quantity * average_cost
        else:
            value = quantity * product.standard_price
        return float(value)

    def recursive_certified(self, resource, parent, amount=None):
        amount = amount is None and resource.balance_cert or amount or 0.0
        if parent.parent_id.type == 'departure':
            amount_partial = amount * parent.quantity_cert
            return self.recursive_amount(resource, parent.parent_id, amount_partial)
        else:
            return amount * parent.quantity_cert

    def recursive_amount(self, resource, parent, amount=None):
        amount = amount is None and resource.balance or amount or 0.0
        if parent.type == 'departure':
            amount_partial = amount * parent.quantity
            return self.recursive_amount(resource, parent.parent_id, amount_partial)
        else:
            return amount * parent.quantity

    def get_total(self, resource_id):
        records = self.concept_ids.filtered(lambda c: c.product_id.id == resource_id)
        total = 0
        for rec in records:
            total += rec.recursive_amount(rec, rec.parent_id, None)
        return total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                company = self.env.company
                sequence_by_year = company.sequence_by_year

                if sequence_by_year:
                    project = self.env['bim.project'].browse(vals.get('project_id'))
                    last_budget = self.env['bim.budget'].search(
                        [('project_id', '=', project.id)],
                        order='id desc',
                        limit=1,
                    )

                    if last_budget and last_budget.code and '-V' in last_budget.code:
                        code_parts = last_budget.code.split('-V')
                        vals['code'] = f"{project.name}-V{int(code_parts[1]) + 1}"
                    else:
                        vals['code'] = f"{project.name}-V1"
                else:
                    vals['code'] = self.env['ir.sequence'].next_by_code('bim.budget') or 'New'

                vals['space_ids'] = [(0, 0, {
                    'name': vals['code'],
                    'code': 'S1',
                })]

        budgets = super().create(vals_list)

        auto_tasks = self.env['bim.task'].search([('budget_auto_create', '=', True)])
        if auto_tasks:
            task_vals_list = []
            for budget in budgets:
                for task in auto_tasks:
                    task_vals_list.append({
                        'desc': task.desc,
                        'budget_id': budget.id,
                        'project_id': budget.project_id.id,
                    })
            if task_vals_list:
                self.env['bim.task'].create(task_vals_list)

        return budgets

    def write(self, vals):
        res = super(BimBudget, self).write(vals)
        if 'type' in vals:
            for concept in self.concept_ids:
                concept.update_budget_type()
        return res

    @api.depends('project_id')
    def _compute_surface(self):
        for budget in self:
            budget.surface = 0

    @api.depends('concept_ids')
    def _get_concept_count(self):
        for budget in self:
            budget.concept_count = len(budget.concept_ids)

    @api.depends('stage_ids')
    def _get_stage_count(self):
        for budget in self:
            budget.stage_count = len(budget.stage_ids)

    @api.depends('space_ids')
    def _get_space_count(self):
        for budget in self:
            budget.space_count = len(budget.space_ids)

    @api.depends('concept_ids')
    def _compute_balance_surface(self):
        for record in self:
            concepts = record.env['bim.concepts'].search([('budget_id', '=', record.id), ('parent_id', '=', False)])
            total = 0.0
            for concept in concepts:
                total += concept.balance
            if record.surface != 0:
                balace_surface = total / record.surface
            else:
                balace_surface = 0.0
            record.balace_surface = balace_surface

    name = fields.Char('Description', required=True, index=True)
    code = fields.Char('Code', required=True, index=True, default="New")
    budget_category_id = fields.Many2one('budget.category', string='Category', tracking=True, ondelete='restrict')
    note = fields.Text('Summary', copy=True)
    balace_surface = fields.Monetary(string="Amount /m2", compute=_compute_balance_surface, help="Amount per m2")

    balance = fields.Float(string="Amount", help="General Amount of the Budget.", digits='BIM price')
    iva = fields.Float(string="Iva", help="General Amount of the Budget.", digits='BIM price')
    amount_total = fields.Float(string="Total Amount", help="Total Amount of the Budget.", digits='BIM price')
    amount_total_test = fields.Float(string="Importe Prueba", help="Total Amount of the Budget.", digits='BIM price')
    t_t = fields.Float(string="T-T", digits='BIM price')

    certified = fields.Float(string="Certified", help="Certified Budget Amount.", digits='BIM price')
    surface = fields.Float(string="Surface m2", help="Builded surface (m2).", copy=True, digits="BIM qty")
    project_id = fields.Many2one('bim.project', string='Project', tracking=True, ondelete='restrict')
    analysis_graph = fields.Binary(readonly=True)
    graph = fields.Boolean('Graph', default=False)
    customer_ids = fields.Many2many('res.partner', string='Customers', tracking=True)
    favorite = fields.Boolean('Favorite', default=False)
    template_id = fields.Many2one('bim.assets.template',
                                  copy=True,
                                  string='Template H.D.',
                                  tracking=True)
    utility = fields.Float(string='Margin', tracking=True, digits='BIM price')
    sale_import = fields.Monetary(string='Sale Import')
    contact_id = fields.Many2one('res.partner', string='Contact', tracking=True)
    user_id = fields.Many2one('res.users', string='Responsable', tracking=True, default=lambda self: self.env.user)
    indicator_ids = fields.One2many('bim.budget.indicator', 'budget_id', 'Comparative indicators')
    concept_ids = fields.One2many('bim.concepts', 'budget_id', 'Concept', tracking=True)
    stage_ids = fields.One2many('bim.budget.stage', 'budget_id', 'Stages')
    projection_ids = fields.One2many('bim.budget.stage.projection', 'budget_id', 'Projections')
    space_ids = fields.One2many('bim.budget.space', 'budget_id', 'Spaces')
    asset_ids = fields.One2many('bim.budget.assets', 'budget_id', string='Assets and Discounts')
    concept_count = fields.Integer('Concept N°', compute="_get_concept_count")
    departure_count = fields.Integer('# Departures', compute="_get_departure_count")
    stage_count = fields.Integer('Stages N°', compute="_get_stage_count")
    space_count = fields.Integer('Spaces N°', compute="_get_space_count")
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', string="Currency", required=True, copy=True)
    origin = fields.Char('Origin', copy=True)
    count_docs = fields.Integer('Quantity Documents', compute="_compute_count_docs")
    exchange_rate = fields.Float(string="Tasa Cambio", default=1.0)
    list_price_do = fields.Boolean(compute='_giveme_list_price')
    certification_ids = fields.One2many('bim.massive.certification.by.line', 'budget_id')
    bim_calendar_id = fields.Many2one('bim.calendar', string='Calendar', tracking=True )
    certification_count = fields.Integer(compute='_compute_certifification_count')
    pvp_id = fields.Many2one('bim.budget.assets', string="A.D.")
    total_main_asset = fields.Float(string="A.D. (Total)", related='pvp_id.total', store=True, digits='BIM price')
    cas_flow_ids = fields.One2many('bim.budget.cash.flow', 'budget_id', copy=False)
    advance = fields.Float(string='Advance', tracking=1, copy=False)
    advance_percent = fields.Float(string='Advance %', tracking=1, digits=(10, 2), copy=False)
    retention = fields.Float(string='Retention %', compute='_compute_retention', store=True, readonly=False,
                             tracking=True, digits=(10, 2), copy=False)
    resource_ids = fields.One2many('bim.budget.resource', 'budget_id')

    type_calc_cert = fields.Selection([('quantity', 'Quantity'), ('percent', 'Percent')],
                                      help="Allows you to configure whether the certification is calculated by quantity or percentage",
                                      string='Type Calc Certification', required=True,
                                      default=lambda self: self.env.company.type_calc_cert)

    type_calc_cert_amount = fields.Selection([
                                                ('direct_cost', 'Direct Cost'),
                                                ('total', 'Total')],
                                      string='Type Calc Certification Amount', required=True,
                                      default='total')

    type_calc_amount = fields.Selection([
                                                ('from_departure', 'Desde Partidas'),
                                                ('from_hyd', 'Desde H.D.')],
                                      required=True,
                                      default='from_hyd', string='Tipo Calc. Importe')

    error_message_bim = fields.Text('Error Message', readonly=True)
    budget_request_id = fields.Many2one('budget.request', string='Budget Request', tracking=True)
    budgeted_hours = fields.Float('HH' , help="Total de horas hombres presupuestadas")
    Kp = fields.Float('Kp', help="Kp = Precio de Venta / Costo Directo")
    hhv = fields.Float('HH Vestida', help="Horas Hombre Vestidas = ( Precios de Venta - Materiales ) / Total de horas hombres")
    tag_ids = fields.Many2many('bim.tag', string='Tags')
    write_utility = fields.Boolean(string="Write Utility", related='state_id.write_utility', store=True)
    allow_certification = fields.Boolean(related='state_id.allow_certification', store=True)
    physical_advancement_m = fields.Float('% Avance Físico M.', help="Es un campo informativo que indica el % de avance físico")
    physical_advancement_v = fields.Float('% Avance Físico V.', help="Es un campo informativo que indica el % de avance físico", compute='_compute_valuation_v')
    task_done_count = fields.Integer('Quantity Executed Tasks', compute="_compute_count_tasks")
    count_tasks = fields.Integer('Quantity Tasks', compute="_compute_count_tasks")
    task_ids = fields.One2many('bim.task', 'budget_id', 'Tasks')
    costumer_state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')], default='draft', tracking=True)


    work_database_concept_importer_ids = fields.One2many('work.database.concept.importer', 'budget_id', 'Importer')
    count_importer = fields.Integer('# Importer', compute='_compute_count_importer')
    count_pending_tasks = fields.Integer('Pending Tasks', compute="_compute_count_tasks")

    chat_bim_ids = fields.One2many('chat.bim', 'budget_id', 'Chat IA')
    count_chat_bim = fields.Integer('# Chat IA', compute='_compute_count_chat_bim')

    @api.depends('chat_bim_ids')
    def _compute_count_chat_bim(self):
        for budget in self:
            budget.count_chat_bim = len(budget.chat_bim_ids)

    def action_view_chat_bim(self):
        chats = self.mapped('chat_bim_ids')
        action = self.env.ref('base_bim_2.chat_bim_action').sudo().read()[0]
        action['domain'] = [('id', 'in', chats.ids)]
        action['context'] = {
                                'default_budget_id': self.id,
                            }

        return action

    @api.depends('work_database_concept_importer_ids')
    def _compute_count_importer(self):
        for budget in self:
            budget.count_importer = len(budget.work_database_concept_importer_ids)


    def action_view_importers(self):
        importers = self.mapped('work_database_concept_importer_ids')
        action = self.env.ref('base_bim_2.work_database_concept_importer_action').sudo().read()[0]
        action['domain'] = [('id', 'in', importers.ids)]
        action['context'] = {'default_budget_id': self.id,
                            'default_project_id': self.project_id.id
                            }

        return action

    def action_view_tasks(self):
        tasks = self.mapped('task_ids')
        action = self.env.ref('base_bim_2.action_bim_task').sudo().read()[0]
        action['domain'] = [('id', 'in', tasks.ids)]
        action['context'] = {'default_budget_id': self.id}
        return action

    @api.depends('task_ids')
    def _compute_count_tasks(self):
        for budget in self:
            budget.task_done_count = len(budget.task_ids.filtered(lambda r: r.state == 'end'))
            budget.count_tasks = len(budget.task_ids.filtered(lambda r: r.state != 'cancel'))
            budget.count_pending_tasks = len(budget.task_ids.filtered(lambda r: r.state not in ['end', 'cancel']))

    def _compute_valuation_v(self):
        for record in self:
            if record.amount_total > 0:
                record.physical_advancement_v = record.certified  / record.amount_total * 100
            else:
                record.physical_advancement_v = 0


    bloc_bim_massive_certification_by_line = fields.Boolean('Block certification', default=False, copy=False, tracking=True)
    amount_bloc_bim_massive_certification_by_line = fields.Float('Amount Block', default=0.0, copy=False, tracking=True)

    type_calc = fields.Selection([
        ('standard', 'Standard'),
        ('apu', 'Apu'),
        ('apu-hh', 'Apu HH'),
        ],
        string="type of calculation", default=lambda self: self.env.company.type_calc, required=True)

    type_calc_total_apu = fields.Selection([
        ('departures', 'Partidas'),
        ('budget', 'Presupuesto'),
    ], string="Apu Total Calc", default='departures')

    foot_bonus = fields.Float(string='Bono', tracking=1, copy=False)
    social_benefits = fields.Float(string='Beneficios Sociales', tracking=1)

    update_status = fields.Selection([
        ('0', 'Not updated'),
        ('1', 'Part 1'),
        ('2', 'Part 2'),
        ('3', 'Part 3'),
        ('4', 'Updated'),
    ], string="Update status", default='4',
        help="state of update.")

    update_state = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Update state", default='no',
        help="update for state.")

    edit_code_budget = fields.Boolean( compute="_get_edit_code_budget")

    bim_cash_flow_ids = fields.One2many('bim.cash.flow','bim_budget_id','Cash Flow')
    bim_cash_flow_count = fields.Integer('# Cash Flow', compute="_get_bim_cash_flow_count")

    # income.statement.summary
    income_statement_summary_ids = fields.One2many('income.statement.summary', 'budget_id', 'Income Statement Summary')
    income_statement_summary_count = fields.Integer('# Income Statement Summary', compute='_compute_income_statement_summary_count')

    @api.depends('income_statement_summary_ids')
    def _compute_income_statement_summary_count(self):
        for budget in self:
            budget.income_statement_summary_count = len(budget.income_statement_summary_ids)

    property_ids = fields.Many2many('real.estate.property', string='Properties')
    parent_id = fields.Many2one('bim.budget', string='Parent Budget')
    document_ids = fields.One2many('bim.documentation','budget_id','Documents')
    begin_date_annual_budget = fields.Date('Begin Date')

    type_duration = fields.Selection([
            ('date', 'Date'),
            ('performance', 'Performance'),
            ('manual', 'Manual'),
        ],
        string="Type Duration",
        default='performance',
        help="Select the type of duration to be used in the budget.",
        required=True)

    # departure_count
    def _get_departure_count(self):
        for budget in self:
            budget.departure_count = len(budget.concept_ids.filtered(lambda r: r.type == 'departure'))

    @api.onchange('bloc_bim_massive_certification_by_line')
    def onchange_bloc_bim_massive_certification_by_line(self):
        if self.bloc_bim_massive_certification_by_line:
            self.amount_bloc_bim_massive_certification_by_line = self.amount_total_cd




    def action_view_documents(self):
        documents = self.mapped('document_ids')
        action = self.env.ref('base_bim_2.action_bim_documentation').sudo().read()[0]
        action['domain'] = [('id', 'in', documents.ids)]
        action['context'] = {
                            'default_budget_id': self.id,
                            'default_project_id': self.project_id.id
                            }

        return action

    def action_view_income_statement_summary(self):
        income_statement_summary_ids = self.mapped('income_statement_summary_ids')
        action = self.env.ref('base_bim_2.action_income_statement_summary').sudo().read()[0]
        action['domain'] = [('id', 'in', income_statement_summary_ids.ids)]
        action['context'] = {
                            'default_budget_id': self.id,
                            }

        return action


    @api.depends('key','share')
    def _compute_url(self):
        for rec in self:
            param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.share_url = param_web_base_url + '/bim/docs/budgets/' + str(rec.key)

    share = fields.Boolean('Share', default=False, copy=False, tracking=True)
    share_url = fields.Char('Share Url', compute='_compute_url', store=True)
    number_open = fields.Integer('Number Open', copy=True)
    open_date = fields.Datetime('Open Date', copy=False)
    all_share = fields.Boolean('All', default=False)

    @api.depends('document_ids')
    def _compute_count_docs(self):
        for project in self:
            project.count_docs = len(project.document_ids)

    def _get_key(self):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    key = fields.Char("Key", tracking=True, default=_get_key)

    def _get_bim_cash_flow_count(self):
        for budget in self:
            budget.bim_cash_flow_count = len(budget.bim_cash_flow_ids)

    def action_view_bim_cash_flow(self):
        action = self.env.ref('base_bim_2.action_bim_cash_flow').sudo().read()[0]
        action['domain'] = [('bim_budget_id', '=', self.id)]
        action['context'] = {
                             'default_default_bim_budget_id': self.id,
                             'default_bim_project_id': self.project_id.id
                             }
        return action


    def _get_edit_code_budget(self):
        for record in self:
            record.edit_code_budget =  self.env.user.company_id.edit_code_budget

    @api.onchange('advance')
    def onchange_advance_cal_percent(self):
        if self.balance > 0:
            self.advance_percent = self.advance * 100 / self.balance
        else:
            self.advance_percent = 0

    @api.onchange('advance_percent')
    def onchange_advance_percent_cal_advance(self):
        self.advance = self.advance_percent * self.balance / 100

    def _compute_retention(self):
        for budget in self:
            budget.retention = budget.project_id.retention

    def action_calculate_cash_flow(self):
        if not self.stage_ids:
            raise UserError(_("You need to generate some stages before updating Cash Flow!"))

        if not self.planning_method:
            raise UserError(_("You need to choose planning method calculate cash flow!"))
        self.compute_budget_updates()
        self.cas_flow_ids.unlink()
        self.cas_flow_ids.create(self._prepare_cash_flow_vals('start', self.advance))
        for stage in self.stage_ids:
            self.cas_flow_ids.create(self._prepare_cash_flow_vals('middle', self.advance / len(self.stage_ids), stage))
        self.cas_flow_ids.create(self._prepare_cash_flow_vals('end', 0))
        pending_advance = self.advance
        for flow in self.cas_flow_ids:
            if flow.flow_position == 'start':
                flow.accumulated = pending_advance
            else:
                flow.accumulated = pending_advance + flow.partial_cash_flow
                pending_advance += flow.partial_cash_flow

    @api.constrains('retention', 'advance')
    def _recalculate_on_save(self):
        for budget in self.filtered_domain([('advance', '!=', 0)]):
            budget.action_calculate_cash_flow()

    def _prepare_cash_flow_vals(self, flow_position, advance, stage_id=False):
        return {
            'flow_position': flow_position,
            'budget_id': self.id,
            'advance': advance,
            'stage_id': stage_id.id if stage_id else False,
            'egress': stage_id.planning if stage_id else 0,
        }

    def _compute_certifification_count(self):
        for record in self:
            record.certification_count = len(record.certification_ids)

    def action_view_certifications(self):
        certifications = self.mapped('certification_ids')
        action = self.env.ref('base_bim_2.bim_massive_certification_by_line_action').sudo().read()[0]
        context = {'default_budget_id': self.id, 'default_project_id': self.project_id.id}
        if not self.state_id.allow_certification:
            context = {'create': 0, 'default_project_id': self.project_id.id}
        if certifications:
            action['domain'] = [('budget_id', '=', self.id)]
            action['context'] = context
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'New Mass Certification',
                'res_model': 'bim.massive.certification.by.line',
                'view_mode': 'form',
                'target': 'current',
                'context': context
            }
        return action

    def _giveme_list_price(self):
        if self.env.company.type_work == 'pricelist':
            self.list_price_do = True
        else:
            self.list_price_do = False

    pricelist_id = fields.Many2one('product.pricelist', string='Price list',
                                   default=lambda s: s.env['product.pricelist'].search([], limit=1),
                                   check_company=True,
                                   domain="['|',('company_id','=',False),('company_id','=',company_id)]")

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    date_start = fields.Date('Start Date', required=True, copy=True, default=fields.Date.today)
    date_end = fields.Date('End Date', copy=True, default=fields.Date.today)
    date_from = fields.Date('Scheduled start date', compute='_compute_dates')
    date_to = fields.Date('Scheduled end date', compute='_compute_dates')
    do_compute = fields.Boolean('Calculate', default=True)
    # use_programmed = fields.Boolean('Usar fechas programadas')  # En caso de querer usar el check, pero creo que se debería borrar...
    obs = fields.Text('Notes', copy=True)
    header_notes = fields.Text('Header Notes', copy=True)
    incidents = fields.Text('Incidences', copy=False)
    order_mode = fields.Selection([
        ('sequence', 'By Sequence'),
        ('code', 'By Codes')],
        'Generate precedents',
        required=True, default='sequence', copy=True)
    type = fields.Selection([
        ('budget', 'Budget'),
        ('certification', 'Certification'),
        ('execution', 'Execution'),
        ('gantt', 'Programming')],
        string='Tipo', default='budget', tracking=True, copy=True)

    type_contract = fields.Selection([
        ('contract', 'Contract'),
        ('increases', 'Increases'),
        ('extras', 'Extras'),
        ('reduction', 'Reduction'),
        ('studies', 'Studies'),
        ('final', 'Final')],
        string='Type Contract', default='contract', required=True)

    state_id = fields.Many2one(
        'bim.budget.state', string='State', index=True, tracking=True,
        compute='_compute_state_id', readonly=False, store=True,
        copy=False, ondelete='restrict', default=lambda s: s.env['bim.budget.state'].search([], limit=1))

    planning_method = fields.Selection([
        ('uniform', 'Uniform distribution'),
        ('dates', 'Gantt planning'),
    ], 'Planning', default='uniform', required=True, tracking=True)
    stage_analysis = fields.Many2one('bim.budget.stage', string='Stage',
                                     domain="[('state','in',['process','approved']),('budget_id','=',id)]")
    stage_cost_var = fields.Float('Cost Variation (CV)', related='stage_analysis.cost_variation', digits='BIM price')
    stage_cost_performance = fields.Float('Cost Perform (CPI)', related='stage_analysis.stage_cost_perform',
                                          digits='BIM price')
    stage_advance_var = fields.Float('Advance Variation (SV)', related='stage_analysis.advance_variation',
                                     digits='BIM price')
    stage_advance_performance = fields.Float('Advance Perform (SPI)', related='stage_analysis.stage_advance_perform',
                                             digits=(10, 2))
    cost_var_analysis = fields.Text('CV Analysis', readonly=True)
    cost_perf_analysis = fields.Text('CPI Analysis', readonly=True)
    advance_var_analysis = fields.Text('SV Analysis', readonly=True)
    advance_perf_analysis = fields.Text('SPI Analysis', readonly=True)
    summary_cv = fields.Text('CV Summary', readonly=True)
    summary_sv = fields.Text('SV Summary', readonly=True)
    projection_type = fields.Selection([('optimistic', 'Optimistic'),
                                        ('realistic', 'Realistic'),
                                        ('pessimistic', 'Pessimistic')],
                                       string='Projection Type', default='optimistic',
                                       required=True)
    projection_conclusion = fields.Text('Summary VAC', readonly=True)
    projection_decoration = fields.Float(default=0)
    budget_history_ids = fields.One2many('bim.budget.history', 'budget_id')
    history_description = fields.Char(copy=False, string='Last Version', readonly=True)
    history_count = fields.Integer(compute='_compute_history_count', store=True, copy=False)
    usd_exchange = fields.Boolean(default=False, tracking=1)
    resource_template_ids = fields.Many2many('bim.resource.template', string='Resource Template', tracking=True)
    resource_template_id = fields.Many2one('bim.resource.template', string='Default Resource Template', tracking=True)


    @api.depends('budget_history_ids')
    def _compute_history_count(self):
        for budget in self:
            budget.history_count = len(budget.budget_history_ids)

    @api.onchange('stage_analysis')
    def update_stage_analysis(self):
        cv_analysis = ''
        sv_analysis = ''
        cpi_analysis = ''
        spi_analysis = ''
        summ_cv = ''
        summ_sv = ''
        if self.stage_analysis:
            if self.stage_cost_var > 0:
                cv_analysis = _(
                    'The project is under budget, expenses have been less than expected.\nPossible causes:\n Good price negotiation.\n Cost control.\n Savings due to poor quality of workmanship or materials.\nMeasures:\n Identify the origin of the causes of savings\n Keeping up with the work')
                summ_cv = _('Under budget')
            elif self.stage_cost_var == 0:
                cv_analysis = _(
                    'The project is right on budget, expenses have been exactly what was expected.\nMeasures:\n Keeping up with the work')
                summ_cv = _('According to budget')
            elif self.stage_cost_var < 0:
                cv_analysis = _(
                    'Project is over budget, expenses have been more than expected.\nPossible causes:\n Productivity did not reach the estimated value\n Setbacks that have created expenses, project changes, rains, strikes, etc.\nMeasures:\n Identify the source of losses\n Take steps to eradicate losses')
                summ_cv = _('Over budget')
            if self.stage_advance_var > 0:
                sv_analysis = _(
                    'The project is advanced, it has been executed more than planned in the planning.\nPossible causes:\n Actual productivity exceeded estimate\n Excessively fast and poor quality execution\nMeasures:\n Identify the origin of the causes of savings\n Keeping up with the work')
                summ_sv = _('Project advanced')
            elif self.stage_advance_var == 0:
                sv_analysis = _(
                    'The project is on time, exactly what was planned in the planning has been executed.\nMeasures:\n Keeping up with the work')
                summ_sv = _('Project on time')
            elif self.stage_advance_var < 0:
                sv_analysis = _(
                    'The project is delayed, less than planned has been executed.\nPossible causes:\n The real productivity did not reach the estimated.\n Setbacks that have delayed work, project changes, rains, strikes, etc.\nMeasures:\n Identify the source of arrears\n Take steps to eradicate arrears')
                summ_sv = _('Project delayed')
            if self.stage_cost_performance > 1:
                cpi_analysis = _('The actual cost is less than the budget, the project is being cheaper')
            elif self.stage_cost_performance == 1:
                cpi_analysis = _('So far the cost has been exactly the amount in the budget')
            elif self.stage_cost_performance < 1:
                cpi_analysis = _('The cost is being more than expected according to the budget')
            if self.stage_advance_performance > 1:
                spi_analysis = _('It has been executed more than expected, the project is advanced')
            elif self.stage_advance_performance == 1:
                spi_analysis = _('Progress is according to plan')
            elif self.stage_advance_performance < 1:
                spi_analysis = _('It has been executed less than expected, the project is behind schedule.')
        self.cost_var_analysis = cv_analysis
        self.advance_var_analysis = sv_analysis
        self.cost_perf_analysis = cpi_analysis
        self.advance_perf_analysis = spi_analysis
        self.summary_cv = summ_cv
        self.summary_sv = summ_sv

    def update_certifications(self):
        for stage in self.stage_ids:
            certif = 0
            fixed = 0
            stages = 0
            measure = 0
            if stage.state == 'process' or stage.state == 'approved':
                self.env.cr.execute(
                    "SELECT SUM(amount_certif) AS cert_stage FROM bim_concepts INNER JOIN bim_certification_stage ON bim_concepts.id = bim_certification_stage.concept_id WHERE bim_certification_stage.stage_id = {} AND bim_concepts.type <> 'chapter' AND bim_concepts.budget_id = {}".format(
                        stage.id, self.id))
                if self.env.cr.rowcount:
                    stage_cert = self.env.cr.dictfetchall()
                    temp_stage = stage_cert[0]['cert_stage']
                    if temp_stage:
                        stages = temp_stage

                self.env.cr.execute(
                    "SELECT SUM(subtotal) AS subtotal FROM (SELECT bim_concepts.amount_compute_cert as price, bim_concept_measuring.amount_subtotal as amount, bim_concepts.amount_compute_cert * bim_concept_measuring.amount_subtotal as subtotal FROM bim_concepts INNER JOIN bim_concept_measuring ON bim_concepts.id = bim_concept_measuring.concept_id WHERE bim_concept_measuring.stage_id = {} AND bim_concepts.budget_id = {}) INFORM".format(
                        stage.id, self.id))
                if self.env.cr.rowcount:
                    measure_cert = self.env.cr.dictfetchall()
                    temp_measure = measure_cert[0]['subtotal']
                    if temp_measure:
                        measure = temp_measure

                if stage == self.stage_ids[0]:
                    self.env.cr.execute(
                        "SELECT sum(balance_cert) AS amount_fixed FROM bim_concepts WHERE type_cert = 'fixed' AND budget_id = {}".format(
                            self.id))
                    if self.env.cr.rowcount:
                        fixed_cert = self.env.cr.dictfetchall()
                        temp_fixed = fixed_cert[0]['amount_fixed']
                        if temp_fixed:
                            fixed = temp_fixed
                        certif = stages + measure + fixed
                    self.stage_ids[0].certification = certif
                else:
                    certif = stages + measure

            if self.type_calc == 'standard':
                stage.certification = certif * self.certification_factor
            else:
                stage.certification = certif

    def update_planning(self):
        if self.planning_method == 'uniform':
            for stage in self.stage_ids:
                if self.stage_count > 0:
                    stage.planning = self.balance / self.stage_count
        elif self.planning_method == 'dates':
            for stage in self.stage_ids:
                if not stage.date_start or not stage.date_stop:
                    continue
                start = stage.date_start
                stop = stage.date_stop
                total = 0
                # Estos son los conceptos en la raiz, dentro del periodo de la etapa
                for concept in self.concept_ids:
                    # Me quedo con los conceptos que tengan fecha y que solo sean de la raiz, y que tengan importe
                    if not concept.acs_date_start or not concept.acs_date_end or concept.parent_id or not concept.balance:
                        continue
                    concept_start = concept.acs_date_start.date()
                    concept_stop = concept.acs_date_end.date()
                    # Y ahora solo me quedo con aquellos que sean del periodo
                    if concept_start > stop or concept_stop < start:
                        continue
                    # Calculamos cuanto dura este concepto en días
                    days = (concept_stop - concept_start).days + 1
                    if not days:
                        # Si de casualidad no hay días de diferencia, nos vamos..
                        continue
                    balance_per_day = concept.balance / days
                    stage_start = start if start > concept_start else concept_start
                    stage_stop = stop if stop < concept_stop else concept_stop
                    stage_duration = relativedelta(stage_stop, stage_start).days + 1
                    total += balance_per_day * stage_duration
                stage.planning = total
        else:
            self.stage_ids.write({'planning': 0})

    def update_execution(self):
        vat = self.company_id.include_vat_in_indicators
        first_stage_date = self.stage_ids[0].date_start
        last_stage_date = self.stage_ids[-1].date_stop
        for stage in self.stage_ids:
            opening = 0
            temp_invoice = 0
            temp_refund = 0
            temp_out_mat = 0
            temp_dev_mat = 0
            start_out_mat = 0
            end_out_mat = 0
            start_dev_mat = 0
            end_dev_mat = 0
            start_in_inv = 0
            end_in_inv = 0
            start_in_ref = 0
            end_in_ref = 0
            part = 0
            start_parts = 0
            end_parts = 0
            tools = 0

            # [1] : Partes
            self.env.cr.execute(
                "SELECT bim_part.date AS check_date, bim_part_line.product_uom_qty * bim_part_line.price_unit AS amount FROM bim_part INNER JOIN bim_part_line ON bim_part.id = bim_part_line.part_id "
                "WHERE bim_part.state IN ('validated') AND bim_part.budget_id = {}".format(self.id))
            if self.env.cr.rowcount:
                temp_part = self.env.cr.dictfetchall()
                for parts in temp_part:
                    if parts['check_date'] < first_stage_date:
                        start_parts += parts['amount']
                    elif parts['check_date'] > last_stage_date:
                        end_parts += parts['amount']
                    elif parts['check_date'] >= stage.date_start and parts['check_date'] < stage.date_stop:
                        part += parts['amount']

            # [2] : Asistencias
            self.env.cr.execute(
                "SELECT attendance_cost as amount, check_in as start FROM hr_attendance WHERE budget_id = {}".format(
                    self.id))
            attendance = 0
            start_attend = 0
            end_attend = 0
            if self.env.cr.rowcount:
                temp_attendance = self.env.cr.dictfetchall()
                for attend in temp_attendance:
                    tmp = attend['start']
                    date_to_compare = date(tmp.year, tmp.month, tmp.day)
                    if date_to_compare < first_stage_date:
                        start_attend += attend['amount']
                    elif date_to_compare > last_stage_date:
                        end_attend += attend['amount']
                    elif date_to_compare >= stage.date_start and date_to_compare < stage.date_stop:
                        attendance += attend['amount']


            # [3] : Picking
            self.env.cr.execute(
                "SELECT total_cost AS amount_out, date_done AS date FROM stock_picking INNER JOIN stock_picking_type ON stock_picking.picking_type_id = stock_picking_type.id "
                "WHERE include_for_bim = True AND bim_budget_id = {} AND state = 'done' AND stock_picking.returned = 'false'".format(
                    self.id))
            if self.env.cr.rowcount:
                amount_store_out = self.env.cr.dictfetchall()
                for amount_out in amount_store_out:
                    tmp = amount_out['date']
                    date_to_compare = date(tmp.year, tmp.month, tmp.day)
                    if date_to_compare < first_stage_date:
                        start_out_mat += amount_out['amount_out']
                    elif date_to_compare > last_stage_date:
                        end_out_mat += amount_out['amount_out']
                    elif date_to_compare >= stage.date_start and date_to_compare < stage.date_stop:
                        temp_out_mat += amount_out['amount_out']

            # [4] : Picking
            self.env.cr.execute(
                "SELECT total_cost AS amount_dev, date_done AS date FROM stock_picking INNER JOIN stock_picking_type ON stock_picking.picking_type_id = stock_picking_type.id "
                "WHERE include_for_bim = True AND bim_budget_id = {} AND state = 'done' AND stock_picking.returned = 'true'".format(
                    self.id))
            if self.env.cr.rowcount:
                amount_store_dev = self.env.cr.dictfetchall()
                for amount_dev in amount_store_dev:
                    tmp = amount_dev['date']
                    date_to_compare = date(tmp.year, tmp.month, tmp.day)
                    if date_to_compare < first_stage_date:
                        start_dev_mat += amount_dev['amount_dev']
                    elif date_to_compare > last_stage_date:
                        end_dev_mat += amount_dev['amount_dev']
                    elif date_to_compare >= stage.date_start and date_to_compare < stage.date_stop:
                        temp_dev_mat += amount_dev['amount_dev']
            store = temp_out_mat - temp_dev_mat
            store_start = start_out_mat - start_dev_mat
            store_end = end_out_mat - end_dev_mat

            # [5] : invoice
            self.env.cr.execute(
                "SELECT account_move_line.debit AS debit, account_move_line.amount_currency AS amount_currency, account_move_line.price_total AS price_total, account_move.invoice_date AS date_inv, account_move_line.price_subtotal AS subtotal FROM account_move_line INNER JOIN account_move "
                "ON account_move_line.move_id = account_move.id WHERE account_move.state = 'posted' AND account_move_line.budget_id = {} "
                "AND account_move.move_type = 'in_invoice' AND account_move.include_for_bim = True".format(self.id))
            if self.env.cr.rowcount:
                amount_out_inv = self.env.cr.dictfetchall()
                for amount in amount_out_inv:
                    temp_amount = amount['debit']
                    if amount['date_inv'] < first_stage_date:
                        start_in_inv += temp_amount
                    elif amount['date_inv'] > last_stage_date:
                        end_in_inv += temp_amount
                    elif amount['date_inv'] >= stage.date_start and amount['date_inv'] < stage.date_stop:
                        temp_invoice += temp_amount

            # [6] : Refund
            self.env.cr.execute(
                "SELECT account_move_line.debit AS credit, account_move_line.amount_currency AS amount_currency, account_move_line.price_total AS price_total, account_move.invoice_date AS date_ref, account_move_line.price_subtotal AS subtotal FROM account_move_line INNER JOIN account_move "
                "ON account_move_line.move_id = account_move.id WHERE account_move.state = 'posted' AND account_move_line.budget_id = {} "
                "AND account_move.move_type = 'in_refund' AND account_move.include_for_bim = True".format(self.id))
            if self.env.cr.rowcount:
                amount_in_refund = self.env.cr.dictfetchall()
                for amount in amount_in_refund:
                    temp_amount = amount['credit']
                    if amount['date_ref'] < first_stage_date:
                        start_in_ref += temp_amount
                    elif amount['date_ref'] > last_stage_date:
                        end_in_ref += temp_amount
                    elif amount['date_ref'] >= stage.date_start and amount['date_ref'] < stage.date_stop:
                        temp_refund += temp_amount
            invoice = temp_invoice - temp_refund
            invoice_start = start_in_inv - start_in_ref
            invoice_end = end_in_inv - end_in_ref

            # [7] : bim.tool.rent
            execute_equip = 0
            rent_obj = self.env['bim.tool.rent']
            name_ = stage.name
            rent_obj_search = rent_obj.search([
                ('budget_id', '=', self.id),
                ('state', 'in', ['rented', 'finished']),
                ('date_from', '>=', stage.date_start),
                ('date_from', '<=', stage.date_stop)
            ])
            if rent_obj_search:
                for line in rent_obj_search.rent_line_ids:
                    execute_equip += line.price_total

            tools = execute_equip


            if stage == self.stage_ids[0]:
                self.env.cr.execute(
                    "SELECT SUM(amount) as opening FROM bim_opening_balance WHERE budget_id = {}".format(self.id))
                if self.env.cr.rowcount:
                    open_amount = self.env.cr.dictfetchall()
                    temp_open = open_amount[0]['opening']
                    if temp_open:
                        opening = temp_open
                    total = tools + part + start_parts + attendance + start_attend + store + store_start + invoice + invoice_start + opening
                    self.stage_ids[0].executed = total
            elif stage == self.stage_ids[-1]:
                total = tools + part + end_parts + attendance + end_attend + store + store_end + invoice + invoice_end
                self.stage_ids[-1].executed = total
            else:
                total = tools + part + attendance + store + invoice
                stage.executed = total

    def update_variations(self):
        cpi = 0
        spi = 0
        sum_EV = 0
        sum_AC = 0
        sum_PV = 0
        for stage in self.stage_ids:
            sum_EV += stage.certification
            sum_AC += stage.executed
            sum_PV += stage.planning
            cv = stage.certification - stage.executed
            sv = stage.certification - stage.planning
            if sum_AC > 0 or sum_AC < 0:
                cpi = sum_EV / sum_AC
            if sum_PV > 0 or sum_PV < 0:
                spi = sum_EV / sum_PV
            stage.stage_cost_perform = cpi
            stage.stage_advance_perform = spi
            stage.cost_variation = cv
            stage.advance_variation = sv

    def compute_budget_updates(self):
        if not self.stage_ids:
            raise UserError(_("This budget has not stages. Please generate them first!"))
        try:
            # TODO NOW
            _logger.info("Actualizar")
            self.update_planning()
            self.update_certifications()
            self.update_execution()
            self.update_variations()
            if self.graph:
                self.update_budget_graph()
            self.update_projection()

        except Exception as e:
            _logger.error("Error al actualizar")
            _logger.error(e)

    @api.onchange('projection_type', 'currency_id')
    def update_projection(self):
        eac = 0
        vac = 0
        tcpi = 0
        etc = 0
        sum_AC = 0
        sum_EV = 0
        projection = self.env['bim.budget.stage.projection']
        for stage in self.stage_ids:
            sum_AC += stage.executed
            sum_EV += stage.certification
            if self.projection_type == 'optimistic':
                eac = sum_AC + (self.balance - sum_EV)
            elif self.projection_type == 'realistic':
                if stage.stage_cost_perform > 0 or stage.stage_cost_perform < 0:
                    eac = sum_AC + ((self.balance - sum_EV) / stage.stage_cost_perform)
                else:
                    eac = sum_AC
            elif self.projection_type == 'pessimistic':
                if stage.stage_advance_perform == 0 or stage.stage_cost_perform == 0:
                    eac = sum_AC
                else:
                    eac = sum_AC + ((self.balance - sum_EV) / (stage.stage_advance_perform * stage.stage_cost_perform))
            vac = self.balance - eac
            tcpi = (self.balance - sum_EV) / (self.balance - sum_AC) if (self.balance - sum_AC) else 0
            etc = eac - sum_AC
            if stage == self.stage_ids[-1]:
                self.projection_decoration = vac
                if vac > 0:
                    self.projection_conclusion = _(
                        'The projected cost is less than the total budget: \nSaving {} {}').format(
                        self.currency_id.symbol, round(vac, 2))
                if vac == 0:
                    self.projection_conclusion = _('The expected cost is equal to the budget: \nExact budget')
                if vac < 0:
                    self.projection_conclusion = _(
                        'The projected cost is higher than the budget: \nLosses {} {}').format(self.currency_id.symbol,
                                                                                               round(vac, 2))
            found = False
            for projection_line in self.projection_ids.filtered_domain([('stage_id', '=', stage.ids[0])]):
                projection_line.budget_at_end = self.balance
                projection_line.estimate_at_end = eac
                projection_line.estimate_up_to_end = etc
                projection_line.variation_at_end = vac
                projection_line.work_to_be_done = round(tcpi, 2)
                found = True
            if not found:
                vals = {
                    'budget_id': self.id,
                    'stage_id': stage.ids[0],
                    'budget_at_end': self.balance,
                    'estimate_at_end': eac,
                    'estimate_up_to_end': etc,
                    'variation_at_end': vac,
                    'work_to_be_done': round(tcpi, 2),
                }
                projection.create(vals)

    def update_budget_graph(self):
        if not plt:
            return

        field_monetary = self.env['ir.qweb.field.monetary']

        @ticker.FuncFormatter
        def format_monetary(amount, pos):
            value = field_monetary.value_to_html(amount, {'display_currency': self.currency_id})
            value = re.sub('<[^<]+?>', '', value)
            return value

        for record in self:
            stages = []
            cert_vals = []
            exc_vals = []
            pln_vals = []
            cert_count = exc_count = pln_count = 0
            for stage in record.stage_ids:
                stages.append(stage.name)
                cert_vals.append(stage.certification + cert_count)
                exc_vals.append(stage.executed + exc_count)
                pln_vals.append(stage.planning + pln_count)
                cert_count += stage.certification
                exc_count += stage.executed
                pln_count += stage.planning
            fig = plt.figure(figsize=(15, 5))
            ax = fig.add_subplot(111)
            ax.yaxis.set_major_formatter(format_monetary)
            ax.plot(stages, pln_vals, color='blue', marker='.', label=_('Planned'))
            ax.plot(stages, cert_vals, color='green', marker='.', label=_('Certified'))
            ax.plot(stages, exc_vals, color='red', marker='.', label=_('Real'))
            plt.title(_('Budget analysis'), fontsize=14)
            plt.legend(loc='lower center', ncol=len(stages), bbox_to_anchor=(0.5, -0.2))
            plt.grid(True)
            figfile = io.BytesIO()
            plt.savefig(figfile, format='png', bbox_inches='tight', pad_inches=0)
            plt.clf()
            plt.cla()
            plt.close()
            figfile.seek(0)
            record.analysis_graph = base64.b64encode(figfile.getvalue())

    def _compute_state_id(self):
        state_obj = self.env['bim.budget.state']
        for budget in self:
            if not budget.state_id:
                budget.state_id = state_obj.search([('is_new', '=', True)], limit=1).id

    gantt_type = fields.Selection([ ('manual', 'Manual'),
                                    ('begin', 'Calculated Start'),
                                    ('end', 'Calculated End'),
                                    ('time', 'Calculated Duration')], 'Programming', default='manual', required=True)
    detailed_retification_ids = fields.One2many('bim.product.rectify.detailed', 'budget_id', readonly=False)

    amount_total_equip = fields.Float('Total equipment', digits='BIM price')
    amount_total_labor = fields.Float('Total labor', digits='BIM price')
    amount_total_material = fields.Float('Total material', digits='BIM price')
    amount_total_other = fields.Float('Total others', digits='BIM price')
    amount_total_subcontract = fields.Float('Total subcontract', digits='BIM price')
    amount_total_cd = fields.Float('Total direct costs', digits='BIM price')

    amount_certified_equip = fields.Float('Certified equipment',  digits='BIM price')
    amount_certified_labor = fields.Float('Certified labor', digits='BIM price')
    amount_certified_material = fields.Float('Certified material',  digits='BIM price')
    amount_certified_other = fields.Float('Certified other', digits='BIM price')
    amount_certified_subcontract = fields.Float('Certified subcontract', digits='BIM price')

    amount_executed_equip = fields.Float('Executed equipment', compute="_compute_execute", digits='BIM price')
    amount_executed_labor = fields.Float('Executed labor', compute="_compute_execute", digits='BIM price')
    amount_executed_material = fields.Float('Executed material', compute="_compute_execute", digits='BIM price')
    amount_executed_other = fields.Float('Executed other', compute="_compute_execute", digits='BIM price')
    amount_executed_subcontract = fields.Float('Executed subcontract', compute="_compute_execute", digits='BIM price')

    product_rectify_ids = fields.One2many('bim.product.rectify', 'budget_id', 'Product rectifications')
    balance_certified_residual = fields.Float(string='To invoice', compute='compute_balance_certified_residual',
                                              store=True, digits='BIM price')
    certification_factor = fields.Float(default=1)
    cost_list_id = fields.Many2one('bim.cost.list')
    use_cost_list = fields.Boolean(compute='_giveme_cost_list')
    bim_certificate_chapters = fields.Boolean(compute='_compute_bim_certificate_chapters')
    chapter_certification_ids = fields.One2many('bim.massive.chapter.certification', 'budget_id')
    chapter_certification_count = fields.Integer(compute='_compute_chapter_certification_count')

    limit_certification = fields.Boolean(default=lambda self: self.env.company.limit_certification)
    state_virtual_product = fields.Boolean(compute='compute_state_virtual_product')
    limit_certification_percent = fields.Integer(default=lambda self: self.env.company.limit_certification_percent)
    k_factor = fields.Float(readonly=True, compute='update_budget_k_factor', string='Factor K')


    

    def cron_update_budget_resource_usd_currency(self):
        _logger.info(':::STARTING BUDGET USD CURRENCY UPDATE')
        budgets = self.search([('usd_exchange', '=', True)])
        if budgets:
            exchange_rate = self.env['res.currency.rate'].search(
                ['|', ('currency_id.name', '=', 'USD'), ('currency_id.symbol', '=', '$'),
                 ('rate', '!=', 0)], order='name desc', limit=1)
            _logger.info(':::UPDATING %s BUDGETS' % str(len(budgets)))

            for budget in budgets:
                resources = budget.concept_ids.filtered(lambda self: self.type in ['material', 'labor', 'equip'] and
                                                                     self.product_id != False and self.product_id.cost_usd)
                if resources and exchange_rate:
                    products = resources.mapped('product_id')
                    for product in products:
                        product.product_tmpl_id.onchange_cost_usd()
                    for resource in resources:
                        resource.amount_fixed = resource.product_id.standard_price
        _logger.info(':::FINISHING BUDGET USD CURRENCY UPDATE')

    def _compute_chapter_certification_count(self):
        for record in self:
            record.chapter_certification_count = len(record.chapter_certification_ids)

    def _compute_bim_certificate_chapters(self):
        self.bim_certificate_chapters = self.company_id.bim_certificate_chapters

    def _giveme_cost_list(self):
        if self.env.company.type_work == 'costlist':
            self.use_cost_list = True
        else:
            self.use_cost_list = False

    def action_view_chapter_certifications(self):
        certifications = self.mapped('chapter_certification_ids')
        action = self.env.ref('base_bim_2.bim_massive_chapter_certification_action').sudo().read()[0]
        context = {'default_budget_id': self.id, 'default_project_id': self.project_id.id}
        if not self.state_id.allow_certification:
            context = {'create': 0, 'default_project_id': self.project_id.id}
        if certifications:
            action['domain'] = [('budget_id', '=', self.id)]
            action['context'] = context
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'New Mass Certification',
                'res_model': 'bim.massive.chapter.certification',
                'view_mode': 'form',
                'target': 'current',
                'context': context
            }
        return action

    @api.depends('state_id')
    def compute_state_virtual_product(self):
        for record in self:
            record.state_virtual_product = True if record.state_id and record.state_id.convert_virtual_product else False

    @api.onchange('balance')
    def onchange_certification_factor(self):
        for record in self:
            if record.type_calc_cert_amount == 'total':
                record.certification_factor = record.balance / record.amount_total_cd if record.amount_total_cd else 1
            else:
                record.certification_factor = 1


    @api.depends('concept_ids.balance_cert')
    def compute_balance_certified_residual(self):
        for record in self:
            record._compute_amount()
            amount = 0
            cancel = 0
            in_payment_state = self.env['bim.paidstate.line'].search(
                [('budget_id', '=', record.id), ('is_loaded', '=', True)])
            for paidstate in in_payment_state:
                amount += paidstate.amount
                if paidstate.paidstate_id.state == 'cancel':
                    cancel += paidstate.amount
            record.balance_certified_residual = record.certified - amount + cancel

    def action_print_budget_notes(self):
        for budget in self:
            budget.print_budget_notes()

    def print_budget_notes(self):
        return self.env.ref('base_bim_2.notes_report_budget').report_action(self)

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            self.customer_ids = [(6, 0, [self.project_id.customer_id.id])]

            if not self.name:
                self.name = self.project_id.nombre

            self.currency_id = self.project_id.currency_id.id
            if self.project_id.customer_id.property_product_pricelist:
                self.pricelist_id = self.project_id.customer_id.property_product_pricelist.id

    @api.onchange('template_id')
    def onchange_template_id(self):
        if self.template_id:
            self.pvp_id = False
            self.asset_ids = [(5,)]
            last_asset_id = self._create_assets(self.template_id)
            if last_asset_id:
                self.pvp_id = last_asset_id
        else:
            self.pvp_id = False
            self.asset_ids = [(5,)]

    @api.onchange('state_id')
    def onchange_state_id(self):
        if self.state_id.user_ids and self.env.user.id not in self.state_id.user_ids.ids:
            users = ""
            for user in self.state_id.user_ids:
                users += user.display_name + ", "
            raise UserError(
                _("Only users {} can set current Budget to state {}").format(users[:-2], self.state_id.name))

        if self.state_id.bim_project_state_ids:
            if self.state_id.id not in self.state_id.bim_project_state_ids.ids:
                raise UserError(
                    _("The state {} is not allowed for this budget").format(self.state_id.name))

        if self.state_id.required_fields:
            fields = self.state_id.required_fields.split(',')
            for field in fields:
                if not getattr(self, field):
                    raise UserError(_("Field {} is required").format(field))

    @api.depends('concept_ids')
    def _compute_dates(self):
        today = fields.Datetime.today()
        for record in self:
            concept_ids = record.concept_ids.filtered(lambda c: c.type in ['departure'] and (c.acs_date_start or c.acs_date_end))

            record.date_from = min([c.acs_date_start for c in concept_ids if c.acs_date_start], default=record.date_start or today)
            record.date_to = max([c.acs_date_end for c in concept_ids if c.acs_date_end], default=record.date_end or today)

    def set_estimated_dates(self):
        for record in self:
            record.date_start = record.date_from
            record.date_end = record.date_to

    def convert_product_virtual(self):
        product_convert = self.env['product.product']  # product_convert = self.env['product.template']
        concepts_virtual_products = self.concept_ids.filtered(
            lambda concp: concp.product_id
                          and concp.virtual_product_id
                          and concp.type in ['material', 'labor', 'equip']
                          and concp.product_id.resource_type == 'P' or concp.product_id.resource_type == 'V'
                          and not concp.virtual_product_id.convert_pp)

        if concepts_virtual_products:
            for concept in concepts_virtual_products:
                virtual_product = concept.virtual_product_id

                if not virtual_product.product_id:
                    product_data = {
                        "name": virtual_product.name,
                        "default_code": virtual_product.reference,
                        "barcode": virtual_product.barcode,
                        "list_price": virtual_product.sales_price,
                        "standard_price": virtual_product.purchase_price,
                        "type": "product",
                    }
                    new_product = product_convert.sudo().create(product_data)
                    virtual_product.product_id = new_product.id
                else:
                    new_product = virtual_product.product_id

                virtual_product.convert_pp = True
                concept.product_id = new_product.id
                concept.virtual_product_id = False
                concept.show_virtual_product = False
        return

    def action_budget_so(self):
        self.ensure_one()
        vals = {
            'budget_id': self.id,
            'bim_project_id': self.project_id.id,
            'partner_id': self.project_id.customer_id.id,
            'currency_id': self.currency_id.id,
            'project_id': False,
        }
        paidstate_product = self.project_id.paidstate_product if self.project_id.paidstate_product else self.env.company.paidstate_product
        if paidstate_product:
            lines = [
                (0, 0, {
                    'product_id': paidstate_product.id,
                    'name': paidstate_product.name,
                    'product_uom_qty': 1,
                    'product_uom': paidstate_product.uom_id.id,
                    'price_unit': self.balance,
                    'tax_id': [(6, 0, paidstate_product.taxes_id.ids)],
                    'project_id': False,
                })
            ]
            vals['order_line'] = lines
        if vals and paidstate_product:
            so_id = self.env['sale.order'].create(vals)

            if so_id:
                self.sale_order_id = so_id.id

            # si el modulo bim_crm esta instalado
            if self.env['ir.module.module'].search([('name', '=', 'bim_crm'), ('state', '=', 'installed')]):
                opportunity_id = self.project_id.opportunity_id
                if opportunity_id:
                    so_id.opportunity_id = opportunity_id.id

            return {
                'name': _('Sale Order'),
                'view_mode': 'form',
                'res_model': 'sale.order',
                'res_id': so_id.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
        else:
            raise UserError(_('No product defined for paidstate'))

    def action_budget_send(self):
        _logger.info(':::BEGIN BUDGET SEND')
        self.ensure_one()
        wizard = self.env['bim.budget.report.wizard']
        wizard = wizard.create({
            'display_type': 'full',
            'summary_type': 'departure',
            'total_type': 'normal',
            'filter_type': 'space',
            'budget_id': self.id,
            'project_id': self.project_id.id,
            'text': True,
            'filter_ok': False,
        })
        pdf = self.env['ir.actions.report']._render_qweb_pdf("base_bim_2.bim_budget_full", wizard.id)[0]
        b64_pdf = base64.b64encode(pdf).decode()
        ATTACHMENT_NAME = self.name
        attach_report = self.env['ir.attachment'].create({
            'name': ATTACHMENT_NAME,
            'type': 'binary',
            'datas': b64_pdf,
            'store_fname': ATTACHMENT_NAME,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        template_id = self.env.ref('base_bim_2.email_template_budget').id
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        template.attachment_ids = [(6, 0, [attach_report.id])]
        if template.lang:
            lang = template._render_template(template.lang, 'bim.budget', self.ids)
        ctx = {
            'default_model': 'bim.budget',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
        }

        _logger.info(':::END BUDGET SEND')
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_view_budget(self):
        action = self.env.ref('base_bim_2.action_bim_budget').sudo().read()[0]
        action['views'] = [(False, "form")]
        action['res_id'] = self.id
        self.onchange_template_id()
        self.update_amount()
        return action

    def action_view_concepts(self):
        action = self.env.ref('base_bim_2.action_bim_concepts').sudo().read()[0]
        action['domain'] = [('budget_id', '=', self.id), ('parent_id', '=', False)]
        action['context'] = {'default_budget_id': self.id, 'budget_type': self.type}
        return action

    # quiero poner un filtro para que solo muestre los de tipo partida pero que se pueda quitar el filtro
    # ('type', '=', 'departure')

    def action_view_departures(self):
        action = self.env.ref('base_bim_2.action_bim_conceptsr').sudo().read()[0]
        action['domain'] = [('budget_id', '=', self.id)]
        return action

    def action_view_stages(self):
        stages = self.mapped('stage_ids')
        action = self.env.ref('base_bim_2.action_bim_budget_stage').sudo().read()[0]
        if len(stages) > 0:
            action['domain'] = [('id', 'in', stages.ids), ('budget_id', '=', self.id)]
            action['context'] = {'default_budget_id': self.id}
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'New Stage',
                'res_model': 'bim.budget.stage',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_budget_id': self.id}
            }
        return action

    def action_view_spaces(self):
        spaces = self.mapped('space_ids')
        action = self.env.ref('base_bim_2.action_bim_budget_space').sudo().read()[0]
        if len(spaces) > 0:
            action['domain'] = [('id', 'in', spaces.ids), ('budget_id', '=', self.id)]
            action['context'] = {'default_budget_id': self.id}
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'New',
                'res_model': 'bim.budget.space',
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_budget_id': self.id}
            }
        return action

    def print_certification(self):
        return self.env.ref('base_bim_2.bim_budget_certification').report_action(self)

    def name_get(self):
        reads = self.read(['name', 'code'])
        res = []
        for record in reads:
            name = record['name']
            if record['code']:
                name = "[" + record['code'] + '] ' + name
            res.append((record['id'], name))
        return res

    def _create_assets(self, template):
        _logger.info('===== Creando H/D ====')
        assets = []
        assets_obj = self.env['bim.budget.assets']
        seq = 0
        budget_id = self.id
        _budget_id_str = str(budget_id)
        if 'NewId' in _budget_id_str:
            budget_id = _budget_id_str.replace('<NewId origin=', '').replace('>', '').replace('NewId_', '')

        # Primero crear todas las líneas y guardar mapeo
        template_to_budget_map = {}
        last_asset_line = None
        for tmpl_line in template.line_ids:
            seq += 1
            vals = {
                'budget_id': budget_id,
                'asset_id': tmpl_line.asset_id.id if tmpl_line.asset_id else seq,
                'value': tmpl_line.value,
                'sequence': tmpl_line.sequence,
            }

            asset_line = assets_obj.create(vals)
            assets.append(asset_line.id)
            template_to_budget_map[tmpl_line.id] = asset_line.id
            last_asset_line = asset_line

        # Segundo paso: copiar los affect_ids usando el mapeo
        for tmpl_line in template.line_ids:
            if tmpl_line.affect_ids:
                budget_line_id = template_to_budget_map.get(tmpl_line.id)
                if budget_line_id:
                    budget_line = assets_obj.browse(budget_line_id)
                    arr_affect = []
                    for affect in tmpl_line.affect_ids:
                        budget_affect_id = template_to_budget_map.get(affect.id)
                        if budget_affect_id:
                            arr_affect.append(budget_affect_id)
                    if arr_affect:
                        budget_line.affect_ids = [(6, 0, arr_affect)]

        # Verificar si hay un asset principal
        main_asset_id = None
        for asset in self.asset_ids.filtered_domain([('main_asset', '=', True)]):
            main_asset_id = asset.id
            break

        # Retornar el ID del último asset o el principal si existe
        if main_asset_id:
            return main_asset_id
        elif last_asset_line:
            return last_asset_line.id
        return False


    # TODO : AJSUTES EN H/D
    def budget_update_assets(self):
        for budget in self:
            # Inicializamos valores en un diccionario
            _values = {key: 0 for key in ['mo', 'mat', 'eq', 'other', 'total_admin', 'utility', 'financing', 'subcontract']}
            last_level_dep = budget.concept_ids.filtered(lambda r: r.type == 'departure')

            for concept in last_level_dep:
                if concept.performance > 0:
                    performance = concept.performance
                else:
                    performance = 1
                _values['mo'] += concept.apu_total_all_labor * concept.quantity / performance
                _values['eq'] += concept.apu_total_equipment * concept.quantity / performance

                _values['mat'] += concept.apu_total_materials * concept.quantity
                _values['other'] += concept.apu_total_transport * concept.quantity


                _values['total_admin'] += concept.apu_administration * concept.quantity
                _values['utility'] += concept.apu_utility * concept.quantity

                _values['financing'] += concept.apu_financing * concept.quantity
                _values['subcontract'] += concept.apu_total_all_subcontract * concept.quantity


            if budget.type_calc_amount == 'from_departure':
                __total_admin =sum([x.apu_administration_t for x in last_level_dep])
                __utility = sum([x.apu_utility_t for x in last_level_dep])
                _values['total_admin'] = __total_admin
                _values['utility'] = __utility
            else:
                _logger.info('B >> Calculamos Total Admin y Utility')

            for asset in budget.asset_ids:
                if budget.type_calc not in ['apu', 'apu-hh']:
                    asset.total_apu = asset.total
                else:
                    # Mapeo de tipos de activo
                    asset_map = {
                        'H': 'mo',
                        'M': 'mat',
                        'Q': 'eq',
                        'S': 'subcontract',
                    }
                    desc_map = {
                        'Otros': 'other',
                        'Admin': 'total_admin',
                        'Utilidad': 'utility',
                        'Finan': 'financing'
                    }

                    # Asignamos el total_apu según tipo de activo o descripción
                    if asset.asset_id.type in asset_map:
                        asset.total_apu = eval(asset_map[asset.asset_id.type], _values)
                    else:
                        asset.total_apu = asset.total

                    budget.amount_total_labor = _values['mo']
            budget.update_assets_total()


    def exe_update_assets(self):
        # Actualizamos los afectos
        for line in self.asset_ids:
            asset_id = line.asset_id
            _logger.info('asset_id: %s' % asset_id.desc)

            template_id = self.template_id
            # buscamos en la liena de la plantilla este activo
            tmpl_line = template_id.line_ids.filtered(lambda r: r.asset_id == asset_id)
            if tmpl_line:
                _logger.info('tmpl_line: %s' % tmpl_line)
                line.value = tmpl_line.value
                line.sequence = tmpl_line.sequence
                line.affect_ids = [(5,)]
                arr_afect = []
                for affect in tmpl_line.affect_ids:
                    arr_afect.append(affect.asset_id.id)
                line.affect_ids = [(6, 0, arr_afect)]


    def delete_indicators(self):
        indicator_obj = self.env['bim.budget.indicator']
        for budget in self:
            if budget.indicator_ids:
                budget.indicator_ids.unlink()
        return True

    def compute_indicators(self):
        # HH
        budgeted_hours = 0
        for concept in self.concept_ids:
            if concept.type == 'labor':
                budgeted_hours += concept.quantity * concept.parent_id.quantity
        self.budgeted_hours = budgeted_hours
        # Kp
        if self.amount_total_cd > 0:
            self.Kp = self.balance / self.amount_total_cd

        # HH Vestida
        if self.budgeted_hours > 0:
            self.hhv = ( self.balance  - self.amount_total_material) / self.budgeted_hours


        list_vals = ['M', 'Q', 'H', 'C', 'S']
        indicator_obj = self.env['bim.budget.indicator']
        # eliminamos los que no esten en la lista

        for budget in self:
            if not budget.indicator_ids:
                for type in list_vals:
                    indicator_obj.create({'budget_id': budget.id, 'type': type})


    def update_amount_recursivo_0(self):
        _logger.info('[01] Begin - update_amount_recursivo_1')
        validate = self.env.context.get('validate', False)

        for budget in self:
            budget.error_message_bim = ""
            _logger.info('[02] Validamos')

            budget.onchange_certification_factor()

            # Filtramos y ordenamos los conceptos una sola vez
            concept_types = ['labor', 'equip', 'material', 'aux', 'subcontract']
            secuence = {'departure': 10, 'labor': 1, 'equip': 1, 'material': 1, 'subcontract' : 1 ,'aux': 2}

            last_level = budget.concept_ids.filtered(lambda r: r.type in concept_types).sorted(
                key=lambda r: secuence[r.type]
            )
            last_level_dep = budget.concept_ids.filtered(lambda r: r.type == 'departure')

            _logger.info('[03a] Updating last_level amounts')
            for rec in last_level:
                rec.update_amount()

            _logger.info('[031] Updating last_level_dep amounts')
            for rec in last_level_dep:
                rec.update_amount()

            _logger.info('[04] Updating parent levels')
            parents = last_level_dep.mapped('parent_id')
            while parents:
                for parent in parents:
                    parent.update_amount()
                parents = parents.mapped('parent_id')

            # budget.budget_update_assets()
        _logger.info('[100] End - update_amount_recursivo_1')




    def update_amount_recursivo_1(self):
        _logger.info('[01] Begin - update_amount_recursivo_1')
        validate = self.env.context.get('validate', False)

        for budget in self:
            budget.error_message_bim = ""
            _logger.info('[02] Validamos')

            budget.onchange_certification_factor()
            last_level = budget.concept_ids.filtered(
                lambda r: r.type in ['labor', 'equip', 'material', 'aux'])

            last_level_dep = budget.concept_ids.filtered(
                lambda r: r.type in ['departure'])

            secuence = {}
            secuence['departure'] = 10
            secuence['labor'] = 1
            secuence['equip'] = 1
            secuence['material'] = 1
            secuence['aux'] = 2

            last_level = last_level.sorted(key=lambda r: secuence[r.type])


            _logger.info('[03a] last_level')
            for res in last_level:
                res.update_amount()


            _logger.info('[031] last_level')
            for res in last_level_dep:
                res.update_amount()


            _logger.info('[04] last_level update_amount')
            _logger.info('last_level_dep: ' + str(len(last_level_dep)))


            for res in last_level_dep:
                parent = res.parent_id
                while parent:
                    parent.update_amount()
                    if parent.parent_id:
                        parent = parent.parent_id
                    else:
                        parent = False


            # budget.budget_update_assets()
        _logger.info('[100] End - update_amount_recursivo_1')


    def update_amount_rapido_2(self):
        _logger.info('[01] Begin - update_amount_rapido_2')
        validate = self.env.context.get('validate', False)

        for budget in self:
            budget.error_message_bim = ""
            _logger.info('[02] Validamos')

            budget.onchange_certification_factor()
            last_level = budget.concept_ids.filtered(
                lambda r: r.type in ['labor', 'equip', 'material', 'aux'])

            last_level_dep = budget.concept_ids.filtered(
                lambda r: r.type in ['departure'])

            secuence = {}
            secuence['departure'] = 10
            secuence['labor'] = 1
            secuence['equip'] = 1
            secuence['material'] = 1
            secuence['aux'] = 2

            last_level = last_level.sorted(key=lambda r: secuence[r.type])

            _logger.info('[03a] last_level')
            for res in last_level:
                res.update_amount()
                if res.parent_id.type == 'chapter':
                    budget.error_message_bim = 'You have resources associated with chapters, add departure between them.'
            if budget.update_state == 'yes' and budget.update_status == '4':
                budget.update_status = '1'
                return


            _logger.info('[031] last_level')
            for res in last_level_dep:
                res.update_amount()

            _logger.info('[04] last_level update_amount')
            # Actualizamos los capitulos
            _logger.info('[051] actualizamos los capitulos')

            # ordeno de codigo mas grande a menor 1.1.1 1.1 1
            chapter_ids = budget.concept_ids.filtered(
                lambda r: r.type in ['chapter']).sorted(key=lambda r: r.code, reverse=True)

            for chapter in chapter_ids:
                chapter.update_amount()

            if budget.update_state == 'yes' and budget.update_status == '2':
                budget.update_status = '3'
                return

            # budget.budget_update_assets()

            _logger.info('[09] - End')
        _logger.info('[100] End - update_amount_rapido_2')


    def update_amount_by_step3(self):
        _logger.info('[01] Begin - update_amount_by_step3')
        validate = self.env.context.get('validate', False)

        for budget in self:
            budget.error_message_bim = ""
            _logger.info('[02] Validamos')

            budget.onchange_certification_factor()
            last_level = budget.concept_ids.filtered(
                lambda r: r.type in ['labor', 'equip', 'material', 'aux'])

            last_level_dep = budget.concept_ids.filtered(
                lambda r: r.type in ['departure'])

            secuence = {}
            secuence['departure'] = 10
            secuence['labor'] = 1
            secuence['equip'] = 1
            secuence['material'] = 1
            secuence['aux'] = 2

            last_level = last_level.sorted(key=lambda r: secuence[r.type])

            _count = 0
            if budget.update_state == 'no' or ( budget.update_state == 'yes' and budget.update_status == '4' ):
                _logger.info('[03a] last_level')
                for res in last_level:
                    _count += 1
                    res.update_amount()
                    if res.parent_id.type == 'chapter':
                        budget.error_message_bim = 'You have resources associated with chapters, add departure between them.'
                if budget.update_state == 'yes' and budget.update_status == '4':
                    budget.update_status = '1'
                    return

            _count_2 = 0
            _logger.info('[031] last_level')
            if budget.update_state == 'no' or ( budget.update_state == 'yes' and budget.update_status == '1' ):
                _logger.info('[031a] last_level')
                for res in last_level_dep:
                    _count_2 += 1
                    # _logger.info('Contador 2: ' + str(_count_2))
                    res.update_amount()
                if budget.update_state == 'yes' and budget.update_status == '1':
                    budget.update_status = '2'
                    return


            _logger.info('[04] last_level update_amount')
            _count_3 = 0
            if budget.update_state == 'no' or ( budget.update_state == 'yes' and budget.update_status == '2' ):
                _logger.info('last_level_dep: ' + str(len(last_level_dep)))


                for res in last_level_dep:
                    parent = res.parent_id
                    while parent:
                        parent.update_amount()
                        if parent.parent_id:
                            parent = parent.parent_id
                        else:
                            parent = False

                if budget.update_state == 'yes' and budget.update_status == '2':
                    budget.update_status = '3'
                    return

            # budget.budget_update_assets()
            _logger.info('[09] - End')

        _logger.info('[100] End - update_amount_by_step3')


    def cron_update_cost_test(self):
        _logger.info(':::BEGIN BUDGET UPDATE COST TEST')
        budgets = self.search([('amount_total_test' , '>', 0)])
        count_bud = len(budgets)
        count = 0
        for budget in budgets:
            count += 1
            _logger.info('%s - %s ::: BUDGET: %s' % (count, count_bud, budget.name))
            budget.update_amount()

            if budget.amount_total_test != budget.amount_total:
                _logger.info(':::ERROR BUDGET: %s' % budget.name)
                budget.t_t = budget.amount_total_test - budget.amount_total
            else:
                budget.t_t = 0

        _logger.info(':::END BUDGET UPDATE COST TEST')


    def cron_update_cost(self, max_concepts=0):
        _logger.info(':::BEGIN BUDGET UPDATE COST')
        budgets = self.search([('concept_ids', '!=', False)])
        count_bud = len(budgets)
        count = 0
        for budget in budgets:
            count += 1
            _logger.info('%s - %s ::: BUDGET: %s' % (count, count_bud, budget.name))
            if max_concepts > 0:
                if len(budget.concept_ids) > max_concepts:
                    continue
            budget.update_amount()
        _logger.info(':::END BUDGET UPDATE COST')

    def update_amount(self):
        tipo_redondeo = self.type_calc_amount

        start_time = time.time()


        self = self.with_context(tracking_disable=True)

        bim_general_config_id = self.env['bim.general.config'].search([
            ('key', '=', 'type_model_calc')], limit=1)

        direct_cost_rounding_type =  self.env['bim.general.config'].search([
            ('key', '=', 'direct_cost_rounding_type')], limit=1)

        use_direct_cost_rounding = False
        if direct_cost_rounding_type:
            use_direct_cost_rounding = direct_cost_rounding_type.value
        else:
            use_direct_cost_rounding = False

        # cuento los segundos que tarda en ejecutar
        _modelo = ''
        if bim_general_config_id:
            if bim_general_config_id.value == '0':
                _modelo = 'Recursivo / Optimizado 0'
                self.update_amount_recursivo_0()
            elif bim_general_config_id.value == '1':
                self.update_amount_recursivo_1()
            elif bim_general_config_id.value == '2':
                _modelo = 'Rápido 2'
                self.update_amount_rapido_2()
            elif bim_general_config_id.value == '3':
                _modelo = 'Por Paso 3'
                self.update_amount_by_step3()
        else:
            self.update_amount_recursivo_1()

        budget_ids = tuple(self.ids)
        if not budget_ids:
            return

        # Forzar que los cambios del ORM se escriban en BD antes de las consultas SQL directas
        self.env.flush_all()

        # Totales por partidas
        self.env.cr.execute("""
            SELECT
                budget_id,
                COALESCE(SUM(equip_amount_count), 0) AS amount_total_equip,
                COALESCE(SUM(labor_amount_count), 0) AS amount_total_labor,
                COALESCE(SUM(material_amount_count), 0) AS amount_total_material,
                COALESCE(SUM(subcontract_amount_counts), 0) AS amount_total_subcontract,
                COALESCE(SUM(aux_amount_count), 0) AS amount_total_other,
                COALESCE(SUM(sale_amount), 0) AS amount_total_by_departure
            FROM bim_concepts
            WHERE budget_id IN %s
              AND type = 'departure'
            GROUP BY budget_id
        """, (budget_ids,))

        departure_totals = {
            row[0]: {
                'amount_total_equip': row[1],
                'amount_total_labor': row[2],
                'amount_total_material': row[3],
                'amount_total_subcontract': row[4],
                'amount_total_other': row[5],
                'amount_total_by_departure': row[6],
            }
            for row in self.env.cr.fetchall()
        }

        # Certificados por tipo
        self.env.cr.execute("""
            SELECT
                budget_id,
                type,
                COALESCE(SUM(balance_cert), 0) AS total_certified
            FROM bim_concepts
            WHERE budget_id IN %s
              AND type IN ('equip', 'labor', 'material', 'aux', 'subcontract')
            GROUP BY budget_id, type
        """, (budget_ids,))

        certified_totals = {}
        for budget_id, concept_type, total_certified in self.env.cr.fetchall():
            certified_totals.setdefault(budget_id, {})
            certified_totals[budget_id][concept_type] = total_certified

        for budget in self:
            totals = departure_totals.get(budget.id, {})
            certs = certified_totals.get(budget.id, {})

            budget.amount_total_equip = totals.get('amount_total_equip', 0.0)
            budget.amount_total_labor = totals.get('amount_total_labor', 0.0)
            budget.amount_total_material = totals.get('amount_total_material', 0.0)
            budget.amount_total_subcontract = totals.get('amount_total_subcontract', 0.0)
            budget.amount_total_other = totals.get('amount_total_other', 0.0)


            if budget.type_calc_amount != 'from_departure':
                budget.amount_total_cd = (
                        budget.amount_total_equip
                        + budget.amount_total_labor
                        + budget.amount_total_material
                        + budget.amount_total_subcontract
                        + budget.amount_total_other
                )
            else:
                budget.amount_total_cd = totals.get('amount_total_by_departure', 0.0)

            budget.amount_certified_equip = certs.get('equip', 0.0)
            budget.amount_certified_labor = certs.get('labor', 0.0)
            budget.amount_certified_material = certs.get('material', 0.0)
            budget.amount_certified_other = certs.get('aux', 0.0)
            budget.amount_certified_subcontract = certs.get('subcontract', 0.0)

            budget.budget_update_assets()
            budget._compute_amount()


            elapsed_time = time.time() - start_time
            _logger.info('>>> Tiempo de Cálculo: ' + str(round(elapsed_time, 4)) + ' seconds')
            budget.message_post(body='Importe Total: ' + str(round(budget.amount_total,
                                                                   2)) + ', Calculado con el modelo: ' + _modelo + ', Tipo de Redondeo: ' + tipo_redondeo + ', Tiempo de Cálculo: ' + str(
                round(elapsed_time, 4)) + ' segundos.')

    def action_update_budget(self):
        for rec in self:
            _logger.info(':::::::::::::::::::::::::::action_update_budget::::::::::::::::::::')
            _logger.info('Presupuesto: %s' % rec.name)
            _logger.info(':::::::::::::::::::::::::::action_update_budget::::::::::::::::::::')
            rec.update_amount()
            # commit
            self.env.cr.commit()

    def action_update_budget_test(self):
        for rec in self:
            _logger.info(':::::::::::::::::::::::::::action_update_budget test::::::::::::::::::::')
            _logger.info('Presupuesto: %s' % rec.name)
            _logger.info(':::::::::::::::::::::::::::action_update_budget test ::::::::::::::::::::')
            rec.update_amount()
            if rec.amount_total_test != rec.amount_total:
                _logger.info(':::ERROR BUDGET: %s' % rec.name)
                rec.t_t = rec.amount_total_test - rec.amount_total
            else:
                rec.t_t = 0





    @api.depends('balance', 'total_main_asset')
    def update_budget_k_factor(self):
        base_budget_history = self.budget_history_ids.filtered_domain([('history_base', '=', True)])
        if not base_budget_history:
            self.k_factor = 0
        else:
            base_budget_history = base_budget_history[0]
            base_total_labor = base_budget_history.amount_total_labor
            base_total_equip = base_budget_history.amount_total_equip
            base_total_material = base_budget_history.amount_total_material
            base_total_other = base_budget_history.amount_total_other
            base_total_assets = base_budget_history.total_assets - base_budget_history.balance if base_budget_history.total_assets > base_budget_history.balance else 0
            base_balance_total = base_total_assets + base_budget_history.balance

            labor_factor = base_total_labor / base_balance_total if base_balance_total > 0 else 0
            equip_factor = base_total_equip / base_balance_total if base_balance_total > 0 else 0
            material_factor = base_total_material / base_balance_total if base_balance_total > 0 else 0
            other_factor = base_total_other / base_balance_total if base_balance_total > 0 else 0
            total_assets_factor = base_total_assets / base_balance_total if base_balance_total > 0 else 0

            sub_formula_labor = labor_factor * self.amount_total_labor / base_total_labor if base_total_labor > 0 else 0
            sub_formula_equip = equip_factor * self.amount_total_equip / base_total_equip if base_total_equip > 0 else 0
            sub_formula_material = material_factor * self.amount_total_material / base_total_material if base_total_material > 0 else 0
            sub_formula_other = other_factor * self.amount_total_other / base_total_other if base_total_other > 0 else 0
            sub_formula_assets = total_assets_factor * (self.total_main_asset - self.balance) / base_total_assets if (
                        base_total_assets > 0 and self.total_main_asset > 0) else 0
            self.k_factor = sub_formula_labor + sub_formula_equip + sub_formula_material + sub_formula_other + sub_formula_assets


    def paste_all(self):
        for budget in self:
            chapters = budget.concept_ids.filtered(lambda r: r.type in ['departure'])
            copied_bim_concept_id = self.env.user.copied_bim_concept_id

            if not copied_bim_concept_id:
                raise UserError(_("You must copy a departure first"))

            if copied_bim_concept_id and budget.id == copied_bim_concept_id.budget_id.id:
                for chapter in chapters:
                    if copied_bim_concept_id.type in ['departure', 'chapter']:
                        raise UserError(_("You can not paste departures or chapters"))
                    else:
                        self.env.user.recursive_create(copied_bim_concept_id, chapter, budget)
                        print(chapter.name)

            self.env.user.copied_bim_concept_id = False

    def update_assets_total(self):
        _logger.info("budget.amount_total: %s" % self.amount_total)
        for asset in self.asset_ids:
            asset._compute_total()



    def incident_review(self):
        for budget in self:
            incidents = []
            chapters = budget.concept_ids.filtered(lambda r: r.type in ['chapter'])
            resources = budget.concept_ids.filtered(lambda r: r.type in ['labor', 'equip', 'material'])
            for res in resources:
                if not res.product_id:
                    incidents.append(_(inconsistency['1']) % res.display_name)
                if res.child_ids:
                    incidents.append(_(inconsistency['9']) % res.display_name)
                if res.balance == 0:
                    incidents.append(_(inconsistency['7']) % res.display_name)
                if res.type == 'labor' and res.product_id and res.product_id.resource_type != 'H':
                    incidents.append(_(inconsistency['4']) % (res.product_id.display_name, res.display_name))
                if res.type == 'equip' and res.product_id and res.product_id.resource_type != 'Q':
                    incidents.append(_(inconsistency['3']) % (res.product_id.display_name, res.display_name))
                if res.type == 'material' and res.product_id and res.product_id.resource_type != 'M':
                    incidents.append(_(inconsistency['2']) % (res.product_id.display_name, res.display_name))
                if res.type == 'material' and res.product_id and res.product_id.type == 'service':
                    incidents.append(_(inconsistency['5']) % (res.product_id.display_name, res.display_name))
                if res.type == 'labor' and res.product_id and res.product_id.type == 'product':
                    incidents.append(_(inconsistency['6']) % (res.product_id.display_name, res.display_name))
                if res.uom_id and res.product_id and res.uom_id != res.product_id.uom_id:
                    incidents.append(_(inconsistency['10']) % (
                    res.display_name, res.product_id.display_name, res.parent_id.display_name))

            for cap in chapters:
                if cap.quantity > 1:
                    incidents.append(_(inconsistency['8']) % (cap.display_name))

            if not incidents:
                incidents.append(_(inconsistency['0']))
            budget.incidents = '\n'.join(incidents)

    def create_stage(self, date_start, date_end, interval=1):  # 3 Trimestral, 2 Bimensual, 6 Semestral
        stage_obj = self.env['bim.budget.stage']
        for budget in self:
            bstart = date_start
            bend = date_end
            if not bend:
                raise UserError(_('To create the stages you must enter an end date'))

            if bend <= bstart:
                raise UserError(_('To create the stages, you must enter an End date greater than the Start date'))

            stage = 1
            stage_count = self.env['bim.budget.stage'].search_count([('budget_id', '=', budget.id)])
            if stage_count > 0:
                stage = stage_count + 1

            while bstart < bend:
                if interval == 15:
                    next_date = bstart + relativedelta(days=interval)
                elif interval == 7:
                    next_date = bstart + relativedelta(days=interval)
                else:
                    next_date = bstart + relativedelta(months=interval, days=-1)

                if next_date > bend:
                    next_date = bend

                lang = self.env.context.get('lang')
                if not lang:
                    lang = self.env.user.lang

                if lang == 'es_ES':
                    _sname = 'Etapa %s' % str(stage)
                else:
                    _sname = 'Stage %s' % str(stage)

                stage_obj.create({
                    'name': _sname,
                    'code': str(stage),  # .zfill(3)
                    'date_start': bstart,
                    'date_stop': next_date,
                    'budget_id': budget.id,
                    'state': 'process' if stage == 1 else 'draft',
                })
                stage += 1
                if interval == 15:
                    bstart = bstart + relativedelta(days=interval)
                elif interval == 7:
                    bstart = bstart + relativedelta(days=interval)
                else:
                    bstart = bstart + relativedelta(months=interval)
        return True

    def create_measures(self, measure_ids, concept):
        meobj = self.env['bim.concept.measuring']
        for record in measure_ids:
            data_me = record.copy_data()[0]
            data_me['space_id'] = False  # vacios ya que se generan luego
            data_me['concept_id'] = concept.id
            meobj.create(data_me)

    def recursive_create(self, child_ids, budget, parent, cobj):
        for record in child_ids:
            data_rec = record.copy_data()[0]
            data_rec['budget_id'] = budget.id
            data_rec['parent_id'] = parent.id
            next_level = cobj.create(data_rec)
            if record.measuring_ids:
                self.create_measures(record.measuring_ids, next_level)
            if record.child_ids:
                self.recursive_create(record.child_ids, budget, next_level, cobj)

    def rectify_products(self):
        def get_origin_name(concept):
            if not concept.parent_id:
                return concept.display_name.replace(";", ".")
            return get_origin_name(concept.parent_id) + ' - ' + concept.display_name.replace(";", ".")

        # if not self.env.user.has_group('base_bim_2.group_rectify_products'):
        #     raise ValidationError(_('You do not have permissions to rectify products.'))

        types = dict(self.env['bim.concepts']._fields['type'].selection)
        products_by_code = {}
        product_obj = self.env['product.product']
        changes = []
        not_created = []
        not_changed = []
        for concept in self.concept_ids:
            if concept.type in ['chapter', 'departure']:
                continue
            if not concept.product_id or not concept.code:
                not_changed.append((get_origin_name(concept), types.get(concept.type, ''),
                                    concept.product_id.default_code or '', '', concept.uom_id.name or '', ''))
                continue
            if concept.code != concept.product_id.default_code:
                product = products_by_code.get(concept.code)
                if not product:
                    product = product_obj.search([('default_code', '=', concept.code)], limit=1)
                    if product:
                        products_by_code[concept.code] = product
                if product:
                    changes.append((get_origin_name(concept), types.get(concept.type, ''),
                                    concept.product_id.default_code or '', product.default_code or '',
                                    concept.uom_id.name or '', product.uom_id.name or ''))
                    concept.product_id = product
                else:
                    not_created.append(concept.display_name)
                    not_changed.append((get_origin_name(concept), types.get(concept.type, ''),
                                        concept.product_id.default_code or '', product.default_code or '',
                                        concept.uom_id.name or '', product.uom_id.name or ''))
        if not changes and not_created:
            raise ValidationError(
                _('The following concepts were not rectified because the product does not exist:\n%s' % '\n'.join(
                    not_created)))
        elif not changes:
            raise ValidationError(_('There are no products to rectify'))

        workbook = xlwt.Workbook()
        head = xlwt.easyxf('align: wrap yes, horiz center; font: bold on;')
        head2 = xlwt.easyxf('align: wrap no; font: bold on;')
        sheet = workbook.add_sheet('Rectifications')
        # header
        sheet.write_merge(0, 0, 0, 5, 'Rectifications {self.display_name}', head)
        sheet.write(1, 0, 'Resource', head2)
        sheet.write(1, 1, 'Budget Concept', head2)
        sheet.write(1, 2, 'BIM Code', head2)
        sheet.write(1, 3, 'Code to be replaced', head2)
        sheet.write(1, 4, 'Unit in budget', head2)
        sheet.write(1, 5, 'Unit in product', head2)
        for i, line in enumerate(changes, 2):
            for j, data in enumerate(line):
                sheet.write(i, j, data)
        for i, line in enumerate(not_changed, len(changes) + 2):
            for j, data in enumerate(line):
                sheet.write(i, j, data)

        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)

        now = fields.Datetime.now()
        self.product_rectify_ids.create({
            'budget_id': self.id,
            'csv_file': base64.b64encode(stream.getvalue()),
            'filename': 'Rectifications {now.strftime("%d-%m-%y %H:%M")} por {self.env.user.display_name}.xls',
        })
        return True

    def copy(self, default=None):
        cobj = self.env['bim.concepts']
        sobj = self.env['bim.budget.space']
        default = dict(default or {})

        # Generar nombre con versionado V1, V2, V3, etc.
        original_name = self.name or ''
        pattern = r'^(.*)\s+V(\d+)$'
        match = re.match(pattern, original_name)

        if match:
            # Ya tiene versión, incrementar
            base_name = match.group(1)
            version = int(match.group(2))
            new_name = f"{base_name} V{version + 1}"
        else:
            # No tiene versión, agregar V1
            new_name = f"{original_name} V1"

        default.update(
            code="New",
            name=new_name,
            do_compute=True,
            template_id=self.template_id.id if self.template_id else False,
        )
        new_copy = super(BimBudget, self).copy(default)

        # Carga de Concepts
        for cap in self.concept_ids.filtered(lambda b: not b.parent_id):
            data_cap = cap.copy_data()[0]
            data_cap['budget_id'] = new_copy.id
            new_cap = cobj.create(data_cap)
            if cap.child_ids:
                self.recursive_create(cap.child_ids, new_copy, new_cap, cobj)

        # Copia de Haberes y descuentos
        if self.asset_ids:
            assets_obj = self.env['bim.budget.assets']
            old_to_new_asset_map = {}

            # Primer paso: copiar todos los assets
            for old_asset in self.asset_ids:
                new_asset_vals = {
                    'budget_id': new_copy.id,
                    'asset_id': old_asset.asset_id.id,
                    'value': old_asset.value,
                    'sequence': old_asset.sequence,
                    'to_invoice': old_asset.to_invoice,
                    'main_asset': old_asset.main_asset,
                }
                new_asset = assets_obj.create(new_asset_vals)
                old_to_new_asset_map[old_asset.id] = new_asset.id

            # Segundo paso: copiar las relaciones affect_ids
            for old_asset in self.asset_ids:
                if old_asset.affect_ids:
                    new_asset_id = old_to_new_asset_map.get(old_asset.id)
                    if new_asset_id:
                        new_asset = assets_obj.browse(new_asset_id)
                        arr_affect = []
                        for affect in old_asset.affect_ids:
                            new_affect_id = old_to_new_asset_map.get(affect.id)
                            if new_affect_id:
                                arr_affect.append(new_affect_id)
                        if arr_affect:
                            new_asset.affect_ids = [(6, 0, arr_affect)]

            # Copiar el pvp_id si existe
            if self.pvp_id and self.pvp_id.id in old_to_new_asset_map:
                new_pvp_id = old_to_new_asset_map.get(self.pvp_id.id)
                new_copy.pvp_id = new_pvp_id

        # Generacion de Indicadores
        if self.indicator_ids:
            new_copy.compute_indicators()

        # Generacion de Etapas
        if self.stage_ids:
            pass
            # new_copy.create_stage()

        # completar Spaces
        if self.space_ids:
            new_copy.space_ids = [(5,)]
            for space in self.space_ids:
                data_space = space.copy_data()[0]
                data_space['budget_id'] = new_copy.id
                sobj.create(data_space)

        # Asociar Spaces en mediciones
        space_obj = self.env['bim.budget.space']
        departures = new_copy.concept_ids.filtered(lambda x: x.type == 'departure')
        for dep in departures:
            for m in dep.measuring_ids:
                if not m.space_id:
                    space = space_obj.search([('budget_id', '=', new_copy.id), ('name', '=', m.name)], limit=1)
                    m.space_id = space and space.id or False

        return new_copy

    def unlink(self):
        for record in self:
            if record.type == 'certification':
                raise ValidationError(_('You cannot delete budgets in certification.'))
        self.concept_ids.filtered(lambda c: not c.parent_id).unlink()
        return super().unlink()

    def import_gantt(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gantt Import',
            'res_model': 'bim.gantt.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_budget_id': self.id},
        }

    def export_gantt(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gantt Export',
            'res_model': 'bim.gantt.export',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_budget_id': self.id},
        }

    def import_bim_file(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('BIM File Import'),
            'res_model': 'bim.file.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_budget_id': self.id},
        }

    def concept_quantiy_to_cero(self):
        for record in self:
            for concept in record.concept_ids:
                if concept.type == 'departure':
                    concept.quantity = 0
                    for measure in concept.measuring_ids:
                        measure.unlink()
            record.message_post(
                body=_("Amounts in Items Zeroed and Measurements Eliminated by:  %s") % record.env.user.name)

    def load_product_budget_details(self):
        # if not self.env.user.has_group('base_bim_2.group_rectify_products'):
        #     raise ValidationError(_('You are not allow to rectify products.'))

        for line in self.detailed_retification_ids:
            line.unlink()

        product_obj = self.env['product.product']
        detail_rect_obj = self.env['bim.product.rectify.detailed']
        different_product_codes = []
        tmp_list = []
        same_product_codes = []
        for concept in self.concept_ids.filtered(lambda c: c.type in ['labor', 'equip', 'material']):
            tuple = concept.code + concept.name
            if tuple not in tmp_list:
                if concept.code == concept.product_id.default_code:
                    tmp_list.append(tuple)
                    same_product_codes.append([concept.type, concept.product_id])
                else:
                    tmp_list.append(tuple)
                    product = product_obj.search([('default_code', '=', concept.code)])
                    if product:
                        product_id = product
                    else:
                        product_id = concept.product_id
                    different_product_codes.append([concept.type, concept.code, concept.name, product_id])

        for tuple in different_product_codes:
            type = 'M'
            if tuple[0] == 'labor':
                type = 'H'
            elif tuple[0] == 'equip':
                type = 'Q'
            detail_rect_obj.create({
                'budget_id': self.id,
                'type': type,
                'bim_product_code': tuple[1],
                'bim_product_name': tuple[2],
                'odoo_product_id': tuple[3].id
            })

        for tuple in same_product_codes:
            type = 'M'
            if tuple[0] == 'labor':
                type = 'H'
            elif tuple[0] == 'equip':
                type = 'Q'
            detail_rect_obj.create({
                'budget_id': self.id,
                'type': type,
                'bim_product_code': tuple[1].default_code,
                'bim_product_name': tuple[1].name,
                'odoo_product_id': tuple[1].id
            })
        self.rectify_products_from_details()

        return True

    def rectify_products_from_details(self):
        for record in self:
            for line in record.detailed_retification_ids:
                concepts = record.concept_ids.filtered(
                    lambda c: c.type in ['labor', 'equip', 'material'] and c.code == line.bim_product_code)
                for concept in concepts:
                    concept.product_id = line.odoo_product_id.id

    def action_view_budget_history(self):
        action = self.env.ref('base_bim_2.action_bim_budget_history').sudo().read()[0]
        action['context'] = {'default_budget_id': self.id}
        action['domain'] = [('budget_id', '=', self.id)]
        return action

    def action_calculate_budget_resources(self):
        _logger.info(':::BEGIN CALCULATE BUDGET RESOURCES')
        for budget in self:
            concepts = budget.concept_ids
            uom_ids = concepts.mapped('uom_id.id')
            uom_ids.append(False)
            domain = ['material', 'equip', 'labor', 'subcontract']
            resources = concepts.filtered(lambda c: c.type in domain)
            BudgetResource = budget.env['bim.budget.resource']

            # Limpiamos las requested_qty = 0
            budget.resource_ids.filtered_domain([('requested_qty', '=', 0)]).unlink()

            for uom in uom_ids:
                uom_resources = resources.filtered_domain([('uom_id', '=', uom)])
                products = uom_resources.mapped('product_id')
                for product in products:
                    quantity = budget.get_product_budgets_quantity(resources, product, uom)
                    possible_budget_resource = budget.resource_ids.filtered_domain(
                        [('product_id', '=', product.id), ('uom_id', '=', uom)])

                    if possible_budget_resource:
                        possible_budget_resource.budget_qty = quantity
                    else:
                        val = {
                            'product_id': product.id,
                            'budget_qty': quantity,
                            'uom_id': uom,
                            'budget_id': budget.id,
                        }
                        _logger.info('Creating Budget Resource: %s' % val)
                        BudgetResource.create(val)

    def get_product_budgets_quantity(self, concepts, product, uom):
        total_qty = 0
        for rec in concepts:
            if rec.quantity > 0 and rec.parent_id.quantity > 0 and rec.uom_id.id == uom and rec.product_id == product:
                total_qty += self.recursive_quantity(rec, rec.parent_id, None)
        return total_qty

    def recursive_quantity(self, resource, parent, qty=None):
        re = resource.name

        if resource.product_id.tool_ok:
            qty = qty is None and resource.available or qty
        else:
            qty = qty is None and resource.quantity or qty

        if parent.type == 'departure':
            qty_partial = qty * parent.quantity
            return self.recursive_quantity(resource, parent.parent_id, qty_partial)
        else:
            _qty = qty * parent.quantity
            return _qty


class BimBudgetStage(models.Model):
    _name = 'bim.budget.stage'
    _description = "Budget Stages"
    _order = 'date_start asc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    def action_start(self):
        no_do = False
        for line in self.budget_id.stage_ids.filtered_domain([('id', '!=', self.id)]):
            if line.state == 'process':
                no_do = line

        if no_do:
            no_do.write({'state': 'approved'})
            """raise UserError(
                _('There is a stage in budget %s in Current state that you have to Approve.') % no_do.budget_id.display_name)"""

        self.write({'state': 'process'})
        return self.update_concept()

    def action_approve(self):
        self.write({'state': 'approved'})
        pending = self.search([('state', '=', 'draft'), ('budget_id', '=', self.budget_id.id)])
        list_date = [line.date_start for line in pending.filtered_domain([('date_start', '!=', False)])]
        min_date = list_date and min(list_date) or False
        if min_date:
            value = self.search(
                [('state', '=', 'draft'), ('date_start', '=', min_date), ('budget_id', '=', self.budget_id.id)])
            value.action_start()

        return self.update_concept()

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return self.update_concept()

    def action_draft(self):
        self.write({'state': 'draft'})
        return self.update_concept()

    def name_get(self):
        result = []
        for stage in self:
            if stage.state == 'draft':
                state = _('Pending')
            elif stage.state == 'process':
                state = _('Current')
            elif stage.state == 'approved':
                state = _('Approved')
            else:
                state = _('Cancelled')
            name = stage.name + ' - ' + state
            result.append((stage.id, name))
        return result

    name = fields.Char("Name")
    code = fields.Char("Code")
    date_start = fields.Date('Start Date', copy=False)
    date_stop = fields.Date('End Date', required=True, copy=False)
    budget_id = fields.Many2one('bim.budget', "Budget", ondelete='cascade')
    project_id = fields.Many2one('bim.project', related='budget_id.project_id')
    state = fields.Selection([
        ('draft', 'Pending'),
        ('process', 'Current'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled')],
        string='Status', default='draft', copy=False, tracking=True)
    taken = fields.Boolean(default=False)
    user_id = fields.Many2one('res.users', string='Responsible', tracking=True, default=lambda self: self.env.user)
    certification = fields.Float('Certification (EV)', readonly=True, store=True, digits='BIM price')
    executed = fields.Float('Real Cost (AC)', readonly=True, store=True, digits='BIM price')
    planning = fields.Float('Planning (PV)', readonly=True, store=True, digits='BIM price')
    cost_variation = fields.Float('Cost Variation (CV)', readonly=True, store=True, digits='BIM price')
    advance_variation = fields.Float('Advance Variation (SV)', readonly=True, store=True, digits='BIM price')
    stage_cost_perform = fields.Float('Cost Perform (CPI)', readonly=True, store=True, digits='BIM price')
    stage_advance_perform = fields.Float('Advance Perform (SPI)', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related="budget_id.currency_id")
    projection_stage_ids = fields.One2many('bim.budget.stage.projection', 'stage_id', 'Projections')
    company_id = fields.Many2one('res.company', related='budget_id.company_id', string='Company', store=True)

    def update_concept(self):
        ''' Este metodo ACTUALIZA los Concepts que esten certificados
        (((Por Medicion o Por etapas))), ajustando los valores segun el
        cambio de state de la Etapa relacionada'''
        concepts = self.budget_id.concept_ids
        stage_concepts = concepts.filtered(lambda c: c.type_cert == 'stage')
        measure_concepts = concepts.filtered(lambda c: c.type_cert == 'measure')

        if stage_concepts:
            for concept in stage_concepts:
                concept._compute_stage()
                concept.onchange_stage()
                concept.onchange_qty_certification()

        if measure_concepts:
            for concept in measure_concepts:
                concept._compute_measure()
                concept.onchange_qty()
                concept.onchange_qty_certification()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        projection_vals = []
        for res in records:
            for concept in res.budget_id.concept_ids.filtered_domain([('type_cert', '=', 'stage')]):
                concept.update_stage_list(res)

            projection_vals.append({
                'budget_id': res.budget_id.id,
                'stage_id': res.id,
            })

        if projection_vals:
            self.env['bim.budget.stage.projection'].create(projection_vals)

        return records

    def unlink(self):
        for record in self:
            if record.state == 'approved':
                raise UserError(_("It is not possible to delete an Approved Stage"))
            for concept in record.budget_id.concept_ids:
                if concept.type == "departure":
                    if concept.type_cert == 'stage':
                        certifications = concept.certification_stage_ids.filtered_domain(
                            [('stage_id', '=', record.id), ('amount_certif', '!=', 0)])
                        if certifications:
                            raise UserError(_("It is not possible to delete and Stage with Certified Quantities"))
                    elif concept.type_cert == 'measure':
                        certifications = concept.measuring_ids.filtered_domain(
                            [('stage_id', '=', record.id), ('amount_subtotal', '!=', 0)])
                        if certifications:
                            raise UserError(_("It is not possible to delete and Stage with Certified Quantities"))
        return super().unlink()


    """
    @api.onchange('date_stop')
    def onchange_date_stop(self):
        if self.date_stop and self.budget_id and (
                self.date_stop < self.budget_id.date_start or self.date_stop > self.budget_id.date_end):
            raise UserError(
                _("It is not possible to create Stage with Date out of Budget Dates Range from {} to {}").format(
                    self.budget_id.date_start, self.budget_id.date_end))
                    """

    @api.constrains('date_stop')
    def auto_save_date_start(self):
        for stage in self:
            if not stage.date_start:
                split_stage = stage.search([('date_start', '<=', stage.date_stop), ('date_stop', '>=', stage.date_stop),
                                            ('budget_id', '=', stage.budget_id.id)], limit=1)
                if split_stage:
                    raise UserError(
                        _("It is necessary to change date end in stage {} to complete this new stage creation").format(
                            split_stage.name))
                last_stage = stage.search([('budget_id', '=', stage.budget_id.id), ('date_stop', '<=', stage.date_stop),
                                           ('id', '!=', stage.id)], order='date_stop desc', limit=1)
                if last_stage:
                    stage.date_start = last_stage.date_stop + timedelta(days=1)
                else:
                    stage.date_start = stage.budget_id.date_start


class BimBudgetSpace(models.Model):
    _name = 'bim.budget.space'
    _description = "Budget Spaces"
    _order = 'id asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _get_code(self):
        budget_id = self._context.get('default_budget_id')
        budget = self.env['bim.budget'].browse(budget_id)
        return 'S' + str(len(budget.space_ids) + 1)

    name = fields.Char("Name")
    code = fields.Char("Code", default=_get_code)
    budget_id = fields.Many2one('bim.budget', "Budget", ondelete="cascade")
    object_id = fields.Many2one('bim.object', "Object")
    project_id = fields.Many2one('bim.project', "Project", related='budget_id.project_id')
    note = fields.Text('Summary', default="")
    purchase_req_ids = fields.One2many('bim.purchase.requisition', 'space_id', 'Materials Request')
    purchase_req_count = fields.Integer('Request N°', compute="_compute_purchase_req_count")
    edit_code_space = fields.Boolean( compute="_get_edit_code_space")
    company_id = fields.Many2one('res.company', related='budget_id.company_id', string='Company', store=True)

    def _get_edit_code_space(self):
        for record in self:
            record.edit_code_space =  self.env.user.company_id.edit_code_space

    @api.depends('purchase_req_ids')
    def _compute_purchase_req_count(self):
        for space in self:
            space.purchase_req_count = len(space.purchase_req_ids)

    def action_view_purchase_requisition(self):
        purchases = self.mapped('purchase_req_ids')
        action = self.env.ref('base_bim_2.action_bim_purchase_requisition').sudo().read()[0]
        if len(purchases) > 0:
            action['domain'] = [('id', 'in', purchases.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def name_get(self):
        reads = self.read(['name', 'code'])
        res = []
        for record in reads:
            name = record['name']
            if record['code']:
                name = "[" + record['code'] + '] ' + name
            res.append((record['id'], name))
        return res


class BimBudgetAssets(models.Model):
    _name = 'bim.budget.assets'
    _description = 'Credit or budget discount'
    _rec_name = 'asset_id'
    _order = 'sequence'

    sequence = fields.Integer('Sequence')
    asset_id = fields.Many2one('bim.assets', "Credit or Discount", ondelete='cascade')
    value = fields.Float('Valor', digits="BIM qty HD")
    budget_id = fields.Many2one('bim.budget', "Budget", ondelete='cascade')
    currency_id = fields.Many2one('res.currency', 'Currency', related="budget_id.currency_id")
    total = fields.Float(compute='_compute_total', store=True, digits="BIM price")
    total_apu = fields.Float(digits="BIM price", string='Total (APU)')
    to_invoice = fields.Boolean('To Invoice', default=True)
    affect_ids = fields.Many2many(
        string='Affects',
        comodel_name='bim.budget.assets',
        relation='budget_assets_afect_rel',
        column1='parent_id',
        column2='child_id',
    )
    main_asset = fields.Boolean()
    aux_budget_id = fields.Many2one('bim.budget', 'Aux Budget', ondelete="cascade")

    @api.depends('value', 'asset_id', 'affect_ids', 'budget_id.amount_total_material', 'budget_id.amount_total_labor',
                 'budget_id.amount_total_equip', 'budget_id.amount_total_other')

    def _compute_total(self):
        _logger.info(':::BEGIN COMPUTE ASSETS TOTAL')
        amounts = {budget: 0 for budget in self.budget_id}
        amounts[self.budget_id.browse()] = 0
        for record in self:
            budget = record.budget_id
            if record.asset_id.type == 'M':
                value = budget.amount_total_material
            elif record.asset_id.type == 'H':
                value = budget.amount_total_labor
            elif record.asset_id.type == 'Q':
                value = budget.amount_total_equip
            elif record.asset_id.type == 'S':
                value = budget.amount_total_subcontract
            elif record.asset_id.type == 'T':
                value = budget.amount_total_material + budget.amount_total_labor + budget.amount_total_equip + budget.amount_total_other + budget.amount_total_subcontract
            elif record.asset_id.type == 'N':
                value = amounts[budget]
            elif record.asset_id.type == 'O':
                if record.aux_budget_id:
                    value = record.aux_budget_id.balance * (record.value / 100)
                else:
                    value = record.value
            else:
                value = 0.0

            if record.affect_ids:
                total_af = sum(af.total for af in record.affect_ids)
                value = total_af * (record.value / 100)
                # _logger.info('Value 2: %s', value)

            if record.asset_id.type in ['O', 'T']:
                amounts[budget] += value

            if record.budget_id.type_calc == 'apu' and record.asset_id:
                if record.budget_id.type_calc_total_apu == 'departures':
                    # Busco los valores desde el presupuesto por
                    if record.budget_id.pvp_id:
                        # Total de Costo directo
                        if record.asset_id.type == 'T':
                            value = record.budget_id.amount_total_cd

                    if 'Utili' in record.asset_id.desc:
                        value = sum(budget.concept_ids.filtered_domain(
                            [('type', 'in', ['departure'])]).mapped('apu_utility_t'))

                    if 'Administra' in record.asset_id.desc:
                        value = sum(budget.concept_ids.filtered_domain(
                            [('type', 'in', ['departure'])]).mapped('apu_administration_t'))

                    # Total del Presupuesto FFF
                    if record.asset_id.id == record.budget_id.pvp_id.id:
                            value = sum(budget.concept_ids.filtered_domain(
                                [('type', 'in', ['departure'])]).mapped('balance'))
                            budget.amount_total = value

            else:
                if record.budget_id.type_calc_total_apu == 'departures':
                    value = sum(budget.concept_ids.filtered_domain(
                        [('type', 'in', ['departure'])]).mapped('balance'))
                    budget.amount_total = value
                else:
                    budget.amount_total = budget.amount_total_cd + budget.amount_total_other + budget.amount_total_subcontract


            record.total = value


class BimBudgetIndicator(models.Model):
    _description = "Comparative indicators"
    _name = 'bim.budget.indicator'

    @api.depends('amount_projected', 'amount_budget')
    def _compute_percent(self):
        for record in self:
            record.percent = record.amount_budget > 0.0 and (record.amount_projected / record.amount_budget) or 0.0

    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")
    currency_id = fields.Many2one('res.currency', 'Currency', related="budget_id.currency_id")
    amount_budget = fields.Monetary('Amount Budget', help="Budgeted Value", compute="_compute_total")
    amount_executed = fields.Monetary('Real Executed', help="Warehouse Outlets + Parts", compute="_compute_total")
    amount_projected = fields.Monetary('Actual Projected', help="Difference between the Budget and the Real executed",
                                       compute="_compute_total")
    amount_certified = fields.Monetary('Certified', help="Certified value", compute="_compute_total")
    amount_proj_cert = fields.Float('Certified Projected', help="Difference between Budget and Certificate",
                                    compute="_compute_total", digits='BIM price')
    percent = fields.Float('Percentage', help="Percentage given by the real value between the estimated value",
                           compute="_compute_percent")
    type = fields.Selection(
        [('M', 'Materials Cost'),
         ('Q', 'Equipment Cost'),
         ('H', 'Labor Cost'),
         ('S', 'Other Cost'),
         ('C', 'Costos de Subcontratos'),
         ],
        'Indicator Type', readonly=True)

    # YYY
    @api.depends('budget_id', 'type')
    def _compute_total(self):
        amount = 0
        for record in self:
            budget = record.budget_id
            if record.type == 'M':
                diff_proj_cert = budget.amount_total_material - budget.amount_certified_material
                record.amount_budget = budget.amount_total_material
                record.amount_certified = budget.amount_certified_material + diff_proj_cert if (
                            diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else budget.amount_certified_material
                record.amount_proj_cert = 0.0 if (diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else diff_proj_cert
                record.amount_executed = budget.amount_executed_material
                record.amount_projected = budget.amount_total_material - budget.amount_executed_material
            elif record.type == 'H':
                diff_proj_cert = budget.amount_total_labor - budget.amount_certified_labor
                record.amount_budget = budget.amount_total_labor
                record.amount_certified = budget.amount_certified_labor + diff_proj_cert if (
                            diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else budget.amount_certified_labor
                record.amount_proj_cert = 0.0 if (diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else diff_proj_cert
                record.amount_executed = budget.amount_executed_labor
                record.amount_projected = budget.amount_total_labor - budget.amount_executed_labor
            elif record.type == 'Q':
                diff_proj_cert = budget.amount_total_equip - budget.amount_certified_equip
                record.amount_budget = budget.amount_total_equip
                record.amount_certified = budget.amount_certified_equip + diff_proj_cert if (
                            diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else budget.amount_certified_equip
                record.amount_proj_cert = 0.0 if (diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else diff_proj_cert
                record.amount_executed = budget.amount_executed_equip
                record.amount_projected = budget.amount_total_equip - budget.amount_executed_equip

            elif record.type == 'C':
                diff_proj_cert = budget.amount_total_subcontract - budget.amount_certified_subcontract
                record.amount_budget = budget.amount_total_subcontract
                record.amount_certified = budget.amount_certified_subcontract + diff_proj_cert if (
                            diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else budget.amount_certified_subcontract
                record.amount_proj_cert = 0.0 if (diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else diff_proj_cert
                record.amount_executed = budget.amount_executed_subcontract
                record.amount_projected = budget.amount_total_subcontract - budget.amount_executed_subcontract

            elif record.type == 'O':
                diff_proj_cert = budget.amount_total_other - budget.amount_certified_other
                record.amount_budget = budget.amount_total_other
                record.amount_certified = budget.amount_certified_other + diff_proj_cert if (
                            diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else budget.amount_certified_other
                record.amount_proj_cert = 0.0 if (diff_proj_cert > 0.0 and diff_proj_cert <= 1.0) else diff_proj_cert
                record.amount_executed = budget.amount_executed_other
                record.amount_projected = budget.amount_total_other - budget.amount_executed_other

            else:
                record.amount_budget = 0
                record.amount_certified = 0
                record.amount_proj_cert = 0
                record.amount_executed = 0
                record.amount_projected = 0


class BimProductRectify(models.Model):
    _name = 'bim.product.rectify'
    _description = 'Rectification of products in budget'
    _order = 'id desc'
    _rec_name = 'filename'

    budget_id = fields.Many2one('bim.budget', 'Bugdet', ondelete='cascade')
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user)
    date = fields.Datetime('Date', default=fields.Datetime.now)
    csv_file = fields.Binary('File', required=True)
    filename = fields.Char('File Name')


class BimProductRectifyDetailed(models.Model):
    _name = 'bim.product.rectify.detailed'
    _description = 'Detailed product rectification'

    budget_id = fields.Many2one('bim.budget', readonly=True)
    bim_product_code = fields.Char(string='BIM Code', required=True, readonly=True)
    type = fields.Selection([
        ('H', 'LABOR'),
        ('Q', 'EQUIPMENT'),
        ('M', 'MATERIAL')
    ], string="Type", required=True, readonly=True)
    bim_product_name = fields.Char(string='BIM Name', required=True, readonly=True)
    odoo_product_id = fields.Many2one('product.product', string='Product in Odoo', required=True,
                                      domain="[('resource_type','=',type)]")
    odoo_product_code = fields.Char(string='Odoo BIM Code', related='odoo_product_id.default_code', readonly=True)


class BimBudgetStageProjection(models.Model):
    _name = 'bim.budget.stage.projection'
    _description = 'Budget Projection By Stage'
    _order = 'stage_start_date asc'

    budget_id = fields.Many2one('bim.budget', readonly=True, ondelete='cascade')
    stage_id = fields.Many2one('bim.budget.stage', domain="[('budget_id', '=', id)]", store=True, ondelete='cascade')
    stage_start_date = fields.Date('Start Date', related='stage_id.date_start', store=True)
    stage_state = fields.Selection(string='State', related='stage_id.state', store=True)
    budget_at_end = fields.Float('BAC', readonly=True, store=True, digits="BIM price")
    estimate_at_end = fields.Float('EAC', readonly=True, store=True, digits="BIM price")
    estimate_up_to_end = fields.Float('ETC', readonly=True, store=True, digits="BIM price")
    variation_at_end = fields.Float('VAC', readonly=True, store=True, digits="BIM price")
    work_to_be_done = fields.Float('TCPI', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related="budget_id.currency_id")