# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class BimMasCertification(models.Model):
    _name = 'bim.massive.certification.by.line'
    _description = 'Massive Certification'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Sequence',required=True,  default='New', copy=False)
    user_id = fields.Many2one('res.users', string='Responsable', readonly=True, index=True, tracking=True,
                              required=True,
                              default=lambda self: self.env.user)
    type = fields.Selection([('current_stage','Current Stage'),('fixed','Manual')], string='Certification Type',required=True, default='current_stage', readonly=True)
    state = fields.Selection([
    ('draft','Draft'),
    ('loaded','Loaded'),
    ('ready','Validated'),
    ('done','Certified'),
    ('cancelled','Cancelled')], tracking=True, default='draft', string='Status',required=True)
    project_id = fields.Many2one('bim.project', string='Project', required=True, domain="[('company_id','=',company_id)]")


    budget_id = fields.Many2one('bim.budget', string='Budget', required=True,
                                domain="[('project_id', '=', project_id),('state_id.allow_certification', '=', True)]")

    budget_id_code = fields.Char(string='Budget Code', related='budget_id.code', store=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True, readonly=True)
    certification_date = fields.Date(string='Certification Date', readonly=True, index=True, copy=False, default=fields.Date.context_today)
    creation_date = fields.Date(string='Creation Date',  index=True, copy=False, default=fields.Date.context_today)
    note = fields.Text(copy=False)
    certification_stage_ids = fields.Many2many('bim.certification.stage.certification', 'certification_line_rel', string='Certification', copy=False)
    measurement_ids = fields.One2many('bim.certification.measuring', 'certification_line_id', string='Measurements', copy=False)

    concept_ids = fields.Many2many('bim.certification.fixed.certification','certification_fixed_rel', string='Concepts', copy=False)

    total_fit = fields.Float(string='Ajuste')
    total_certif = fields.Float(string='Balance Certif.', compute='_compute_total_certif', store=True, digits='BIM price')
    percent_certif = fields.Float(string='(%) Certif.', compute='_compute_total_certif', store=True, digits=(10, 2))
    greater_than_100 = fields.Boolean(string='(%) >= 100', default=True)
    certif_percent_mass = fields.Float(string='(%) Cert', default=0, digits=(10, 2))
    paid_state_id = fields.Many2one('bim.paidstate', copy=False)
    invoice_state = fields.Selection([('pending','Pending'),('invoiced','Invoiced')],string='Invoice Status', default='pending', compute="_compute_invoice_state", store=True)
    acc_certif_percent_mass = fields.Float(string='(%) Total Cert', default=0, digits=(10, 2))
    load_timesheet = fields.Boolean(string='Load Timesheet', default=True)
    project_employee_sheet_ids = fields.One2many('bim.project.employee.timesheet', 'bim_massive_certification_by_line_id', string='Timesheet')
    type_calc_cert = fields.Selection([('quantity', 'Quantity'), ('percent', 'Percent')],
                                      help="Allows you to configure whether the certification is calculated by quantity or percentage",
                                      string='Type Calc', required=True, default='quantity')


    contractor_contract_progress_capture_id = fields.Many2one('contractor.contract.progress.capture', string='Progress Capture')
    only_concept_ids = fields.Many2many('bim.concepts', string='Only Concepts')
    measurement_capture_ids = fields.Many2many('measurement.capture', string='Measurements Capture')
    default_cuantity_to_cert = fields.Float(string='Cant.')
    certify_everything = fields.Boolean(string='Cert. Todo', default=False)

    date_start = fields.Date(string='Date Start', related='stage_id.date_start')
    date_stop = fields.Date(string='Date Stop', related='stage_id.date_stop')

    new_date_start = fields.Date(string='New Date Start')
    new_date_stop = fields.Date(string='New Date Stop')


    type_invoice = fields.Selection([
        ('out_invoice', 'Sale'),
        ('in_invoice', 'Purchase')
            ], string="Type Invoice",
                default='out_invoice')

    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', string='Massive Certification', copy=False)
    same_stage = fields.Boolean(string='Same Stage', default=False)
    stage_id = fields.Many2one('bim.budget.stage', "Stage")
    measurements = fields.Boolean(string='Use Measurements', default=False)

    # PLANIFICADO
    progress_plan_last = fields.Float(string='Progress Plan Last', digits='BIM price')
    progress_plan_this = fields.Float(string='Progress Plan This', digits='BIM price')
    progress_plan_acc = fields.Float(string='Progress Plan Acc', digits='BIM price')

    # EJECUTADO
    progress_exe_last = fields.Float(string='Progress Exe Last', digits='BIM price')
    progress_exe_this = fields.Float(string='Progress Exe This', digits='BIM price')
    progress_exe_acc = fields.Float(string='Progress Exe Acc', digits='BIM price')

    # DESVIACION
    progress_acc_last = fields.Float(string='Progress Acc Last', digits='BIM price')
    progress_acc_this = fields.Float(string='Progress Acc This', digits='BIM price')
    progress_acc_acc = fields.Float(string='Progress Acc Acc', digits='BIM price')

    percent_to_cert = fields.Float(string='% to Cert', default=0, digits='BIM qty')

    @api.onchange('measurement_capture_ids')
    def onchange_measurement_capture_ids(self):
        for mc in self.measurement_capture_ids:
            for line in mc.lines_ids:
                self.only_concept_ids = [(4, line.concept_id.id)]


    def action_update_progress(self):
        for record in self:
            # YYY Cant Acumulada
            for line in self.certification_stage_ids:
                # buscamos todas las lineas de certificacion que tengan este presupuesto y concepto
                bim_certification_stage_certification_ids = self.env['bim.certification.stage.certification'].search([
                    ('concept_id.budget_id', '=', self.budget_id.id),
                    ('concept_id', '=', line.concept_id.id)
                ])
                line.qty_acc = sum([x.quantity_to_cert for x in bim_certification_stage_certification_ids if x.id < line.id])

            record.progress_acc_last = record.progress_plan_last + record.progress_exe_last
            record.progress_acc_this = record.progress_plan_this + record.progress_exe_this
            record.progress_acc_acc = record.progress_plan_acc + record.progress_exe_acc

            stage = record.stage_id
            begin_date = stage.date_start
            end_date = stage.date_stop

            # suma todas las cantidades de las partidas
            bim_conceps = self.env['bim.concepts'].search([
                        ('type','=','departure'),
                        ('budget_id','=',record.budget_id.id),
                    ])

            sum_qty_total = sum([x.quantity for x in bim_conceps])

            _logger.info("1- sum_qty_total = %s" % sum_qty_total)

            certification_stage_ids_cuantity_to_cert = sum([x.quantity_to_cert for x in record.certification_stage_ids])

            _logger.info("2- certification_stage_ids_cuantity_to_cert = %s" % certification_stage_ids_cuantity_to_cert)

            record.progress_exe_this = certification_stage_ids_cuantity_to_cert / sum_qty_total * 100 if sum_qty_total > 0 else 0

            # buscame todas las certificaciones con id < a la actual
            bim_conceps_last = self.env['bim.concepts'].search([
                        ('type','=','departure'),
                        ('budget_id','=',record.budget_id.id),
                        ('acs_date_start','<',end_date),
                    ])


            # PLANIFICADO
            bim_conceps_this = self.env['bim.concepts'].search([
                        ('type','=','departure'),
                        ('budget_id','=',record.budget_id.id),
                        ('acs_date_end','>',begin_date),
                        ('acs_date_end','<=',end_date),
                    ])
            record.progress_plan_this = sum([x.quantity for x in bim_conceps_this]) / sum_qty_total * 100 if sum_qty_total > 0 else 0

            bim_conceps_last = self.env['bim.concepts'].search([
                        ('type','=','departure'),
                        ('budget_id','=',record.budget_id.id),
                        ('acs_date_end','<=',begin_date),
                    ])
            record.progress_plan_last = sum([x.quantity for x in bim_conceps_last]) / sum_qty_total * 100 if sum_qty_total > 0 else 0





            # EJECUTADO
            bim_massive_certification_by_line_ids = self.env['bim.massive.certification.by.line'].search([
                        ('budget_id','=',record.budget_id.id),
                        ('id','<',record.id),
                        ('state','=','done'),
                    ])
            progress_exe_last = 0
            for l in bim_massive_certification_by_line_ids.certification_stage_ids:
                progress_exe_last += l.quantity_to_cert

            record.progress_exe_last = progress_exe_last / sum_qty_total * 100 if sum_qty_total > 0 else 0

            record.progress_exe_acc = record.progress_exe_last + record.progress_exe_this



            record.progress_plan_acc = record.progress_plan_last + record.progress_plan_this
            # DESVIACION


            record.progress_acc_last = record.progress_exe_last - record.progress_plan_last
            record.progress_acc_this = record.progress_exe_this - record.progress_plan_this
            record.progress_acc_acc = record.progress_exe_acc - record.progress_plan_acc




    def action_to_ready(self):
        self.state = 'ready'


    def mark_all(self):
        for record in self:
            for line in record.certification_stage_ids:
                line.quantity_to_cert = line.budget_qty - line.qty_acc


    def insert_measurement(self):
        # Limpiamos los valores que tiene mediciones.
        for record in self.measurement_ids:
            line = self.env['bim.certification.stage.certification'].search([('id','=',record.bim_certification_stage_certification_id.id)])
            line.quantity_to_cert = 0

        # Limpiamos los valores que tiene mediciones.
        for record in self.measurement_ids:
            line = self.env['bim.certification.stage.certification'].search([('id','=',record.bim_certification_stage_certification_id.id)])
            line.quantity_to_cert += record.amount_subtotal



    def action_clear(self):
        for record in self:
            record.certification_stage_ids.unlink()

    def action_to_load(self):
        self.state = 'loaded'


    def action_update_prices(self):
        for line in self.certification_stage_ids:
            line._compute_sale_price()
            line._compute_amount_ImpAnt()
            line.amount_budget = line.concept_id.balance

    @api.onchange('project_id')
    def onchange_project_id(self):
        for record in self:
            record.budget_id = record.project_id.budget_ids and record.project_id.budget_ids[0] or False


    @api.onchange('type_calc_cert')
    def onchange_type_calc_cert(self):
        for record in self:
            if record.name and record.budget_id:
                record.budget_id.type_calc_cert = record.type_calc_cert

    @api.depends('paid_state_id','paid_state_id.invoice_id','paid_state_id.invoice_id.state')
    def _compute_invoice_state(self):
        for certification in self:
            certification.invoice_state = 'invoiced' if certification.paid_state_id \
            and certification.paid_state_id.invoice_id and certification.paid_state_id.invoice_id.state == \
            'posted' else 'pending'

    def action_create_paid_state(self):
        _index = False
        _index_value = 1
        certification_index_ids = self.env['certification.index'].search([('budget_id','=',self.budget_id.id)], order='id asc')
        if certification_index_ids:
            _index = True
            certification_index_id = certification_index_ids.filtered(lambda x: x.name.month == self.certification_date.month and x.name.year == self.certification_date.year)

            if not certification_index_id:
                raise UserError(_('There is no index for this month'))
            else:
                _index_value = certification_index_id.value



        if self.budget_id.type_calc == 'standard':
            certification_factor = self.budget_id.certification_factor
        else:
            certification_factor = 1


        self.paid_state_id = self.paid_state_id.create({
            'certification_ids': [self.id],
            'type': 'certification',
            'load_certifications': False,
            'project_id': self.project_id.id,
            'type_invoice': self.type_invoice,
            'bim_certification_index_id': certification_index_id.id if _index else False,
            'indicator_a': _index_value if _index else 1,
            'lines_ids':[(0,0,{
               'budget_id': self.budget_id.id,
               'name': self.budget_id.name,
               'quantity': 1,
               'price_unit': self.total_certif,
               'certification_factor': certification_factor,
               'is_loaded': True
                })]
           }).id

        self.budget_id.compute_balance_certified_residual()

    @api.constrains('acc_certif_percent_mass')
    def on_save_acc_certif_percent_mass(self):
        for record in self:
            if record.acc_certif_percent_mass > 0:
                record.certif_percent_mass = 0

    @api.onchange('acc_certif_percent_mass')
    def onchange_acc_certif_percent_mass(self):
        for record in self:
            if record.acc_certif_percent_mass >= 0:
                if record.type == 'current_stage':
                    for line in record.certification_stage_ids:
                        line.acc_certif = record.acc_certif_percent_mass
                        line.onchange_acc_certif()
                        line.onchange_percent()
                else:
                    for line in record.concept_ids:
                        line.acc_certif = record.acc_certif_percent_mass
                        line.onchange_acc_certif()
                        line.onchange_percent_cert()

    @api.constrains('certif_percent_mass')
    def on_save_certif_percent_mass(self):
        for record in self:
            if record.certif_percent_mass > 0:
                record.acc_certif_percent_mass = 0

    @api.onchange('certif_percent_mass')
    def onchange_certif_percent_mass(self):
        for record in self:
            if record.certif_percent_mass >= 0:
                if record.type == 'current_stage':
                    for line in record.certification_stage_ids:
                        line.certif_percent = record.certif_percent_mass
                        line.onchange_percent()
                else:
                    for line in record.concept_ids:
                        line.certif_percent = record.certif_percent_mass
                        line.onchange_percent_cert()

    def fix_certification_by_stage(self):
        for line in self.certification_stage_ids:
            line.amount_cert = line.concept_id.amount_compute_cert

    @api.depends('concept_ids.amount_certif','certification_stage_ids.amount_certif','total_fit','type')
    def _compute_total_certif(self):
        for record in self:
            amount = 0
            if record.type == 'current_stage':
                for line in record.certification_stage_ids:
                    amount += line.amount_certif
            else:
                for line in record.concept_ids:
                    amount += line.amount_certif

            record.total_certif = amount + record.total_fit
            record.percent_certif = record.total_certif / record.budget_id.balance * 100 if record.budget_id.balance > 0 else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.massive.certification') or 'New'

        records = super().create(vals_list)

        for res in records:
            if not res.budget_id.stage_ids and res.type == 'current_stage':
                raise UserError(_(
                    "You cannot create a certification if the Project does not have stages created. "
                    "Please generate some Project Stages and try again."
                ))
            res._validate_current_stage()

        return records

    def _validate_current_stage(self):
        for record in self:
            current_stage = record.budget_id.stage_ids.filtered_domain([('state', '=', 'process')])
            if not current_stage and record.type == 'current_stage':
                raise UserError(
                    _("It is not possible use Current Stage mode because there is not current stage in this budget."))

    def action_ready(self):
        if self.type == 'current_stage':
            if not self.stage_id:
                raise UserError(_('You must select the Stage to Certify'))
        self.state = 'ready'

    def action_cancel(self):
        self.state='cancelled'
        for timesheet in self.project_employee_sheet_ids:
            timesheet.state = 'approved'
            timesheet.bim_massive_certification_by_line_id = False

    def action_convert_to_draft(self):
        if self.measurement_capture_ids:
            for measurement_capture_id in self.measurement_capture_ids:
                measurement_capture_id.bim_massive_certification_by_line_id = False
        self.state='draft'

    def action_load_lines(self):
        for record in self:
            auto_etapa = False
            bim_general_config_id = self.env['bim.general.config'].search([
                ('key', '=', 'auto_etapa')], limit=1)
            if bim_general_config_id and bim_general_config_id.value == '1':
                auto_etapa = True

            if auto_etapa and record.new_date_start and record.new_date_stop:
                # si el presupuesto no tiene etapas o la etapa actual no coincide con las fechas de la certificacion, creamos una nueva etapa
                stage_id  = self.env['bim.budget.stage'].search([
                    ('budget_id', '=', record.budget_id.id),
                    ('state', '=', 'process'),
                    ('date_start', '=', record.new_date_start),
                    ('date_stop', '=', record.new_date_stop),
                ], limit=1)

                # creamos la etapa
                if not stage_id:

                    # _name =  'Etapa %s - %s' % (record.new_date_start, record.new_date_stop)

                    bim_budget_stage_ids = self.env['bim.budget.stage'].search([('budget_id', '=', record.budget_id.id)])
                    num_stage = len(bim_budget_stage_ids) + 1
                    _name = 'Etapa ' + str(num_stage)

                    stage_id = self.env['bim.budget.stage'].create({
                        'name': _name,
                        'date_start': record.new_date_start,
                        'date_stop': record.new_date_stop,
                        'budget_id': record.budget_id.id,
                        'state': 'process',
                    })
                record.stage_id = stage_id.id
                # el resto de las etapas que esten process las ponemos en done
                stage_ids = self.env['bim.budget.stage'].search([
                    ('budget_id', '=', record.budget_id.id),
                    ('state', '=', 'process'),
                    ('id', '!=', stage_id.id),
                ])

                for stage in stage_ids:
                    stage.state = 'approved'


        if self.type == 'current_stage':
            self.load_line_by_stage('process')
            if self.certification_stage_ids:
                self.stage_id = self.certification_stage_ids[0].stage_id.id
        else:
            self.load_line_by_fixed()

        # YYY
        for line in self.certification_stage_ids:
            # buscamos todas las lineas de certificacion que tengan este presupuesto y concepto
            bim_certification_stage_certification_ids = self.env['bim.certification.stage.certification'].search([
                ('concept_id.budget_id', '=', self.budget_id.id),
                ('concept_id', '=', line.concept_id.id)
            ])
            line.qty_acc = sum([x.quantity_to_cert for x in bim_certification_stage_certification_ids if x.id < line.id])

        if self.measurements:
            self.measurement_ids.unlink()

        if self.measurements:
            for line in self.certification_stage_ids:
                if line.concept_id.measuring_ids:
                    for measure in line.concept_id.measuring_ids:
                        vals = {
                            'concept_id': line.concept_id.id,
                            'qty': 0,
                            'length': 0,
                            'width': 0,
                            'height': 0,
                            'certification_line_id': line.id,
                            'bim_certification_stage_certification_id': line.id,
                        }
                        self.measurement_ids = [(0, 0, vals)]
        self.state = 'loaded'


    def action_validate(self):
        parent_id = False

        if self.budget_id.bloc_bim_massive_certification_by_line and self.budget_id.amount_bloc_bim_massive_certification_by_line > 0:
            # suma ImpOrig
            s_total_imp_orig = sum([x.ImpOrig for x in self.certification_stage_ids])
            if s_total_imp_orig > self.budget_id.amount_bloc_bim_massive_certification_by_line:
                raise UserError('La Certificación Supera el Monto Máximo Permitido por Bloqueo en el Presupuesto que es: %s' % self.budget_id.amount_bloc_bim_massive_certification_by_line)

        for line in self.certification_stage_ids:
            # Validamos que la cantidad a origen no sea menor a la cantidad certificada

            if line.quantity_to_cert == 0 and line.quantity_to_cert_o > 0 and line.amount_certif > 0:
                raise UserError(_('The Certified Quantity "CanAct" must be greater than 0 in the Concept %s') % line.concept_id.name)

            if line.quantity_to_cert < 0 and line.amount_certif > 0:
                raise UserError(_('The Certified Quantity "CanAct" must be greater than 0 in the Concept %s') % line.concept_id.name)

            if line.quantity_to_cert > 0 or line.quantity_to_cert_o > 0 and line.amount_certif > 0:
                if line.quantity_to_cert_o < line.quantity_to_cert:
                    raise UserError(_('The Origin Quantity "CanOrig" can not be less than the Certified Quantity "CanAct" in the Concept %s') % line.concept_id.name)


            if parent_id != line.parent_id:
                parent_id = line.parent_id

                TotalImpPres = 0
                TotalImpAnt = 0
                TotalImpOrig = 0
                TotalImpAct = 0

                for line_ in self.certification_stage_ids:
                    if line_.parent_id == parent_id:
                        TotalImpPres += line_.amount_budget
                        TotalImpAnt += line_.ImpAnt
                        TotalImpOrig += line_.ImpOrig
                        TotalImpAct += line_.amount_certif

                line.TotalImpPres = TotalImpPres
                line.TotalImpAnt = TotalImpAnt
                line.TotalImpOrig = TotalImpOrig
                line.TotalImpAct = TotalImpAct

        self.state = 'ready'


    def load_line_by_stage(self, stage):
        for record in self:
            # Delete previous lines
            for line in record.certification_stage_ids:
                bim_project_employee_timesheet_ids = self.env['bim.project.employee.timesheet'].search(
                    [('bim_massive_certification_by_line_id', '=', record.id)])

                for timesheet_ in bim_project_employee_timesheet_ids:
                    timesheet_.bim_massive_certification_by_line_id = False
                    timesheet_.state = 'approved'

            for line in record.certification_stage_ids:
                line.unlink()

            bim_general_config_id = self.env['bim.general.config'].search([
                ('key', '=', 'certification_update')
            ], limit=1)

            if bim_general_config_id and bim_general_config_id.value == '1':
                record.budget_id.update_amount()

            certification_lines = []
            error = False
            record._validate_current_stage()

            sorted_concepts = sorted(record.budget_id.concept_ids, key=lambda s: s.parent_id.id)
            if not self.greater_than_100:
                concept_list = []
                for concp in sorted_concepts:
                    if concp.percent_cert < 100:
                        concept_list.append(concp)
                sorted_concepts = concept_list
            for concept in sorted_concepts:
                if self.only_concept_ids:
                    if concept.id not in self.only_concept_ids.ids:
                        continue

                if self.bim_massive_certification_by_line_id:
                    if concept.id not in self.bim_massive_certification_by_line_id.certification_stage_ids.mapped('concept_id').ids:
                        continue

                if concept.type == 'departure' and concept.parent_id.type == 'chapter':
                    if concept.quantity_cert > 0:
                        if concept.type_cert == 'stage':
                            for cert_stage in concept.certification_stage_ids:
                                if cert_stage.stage_id.state == stage:
                                    quantity_to_cert = 0
                                    project_employee_sheet_ids = []
                                    bim_project_employee_timesheet_lines = self.env[
                                        'bim.project.employee.timesheet'].search(
                                        [('concept_id', '=', concept.id),
                                         ('bim_massive_certification_by_line_id', '=', False),
                                         ('state', '=', 'approved')])

                                    if bim_project_employee_timesheet_lines:
                                        for line in bim_project_employee_timesheet_lines:
                                            quantity_to_cert += line.total_hours
                                            line.bim_massive_certification_by_line_id = self.id
                                            line.state = 'done'
                                            project_employee_sheet_ids.append(line.id)
                                    else:
                                        quantity_to_cert = self.default_cuantity_to_cert



                                    # Insert the time sheet hours
                                    vals = {
                                        'certification_line_id': cert_stage.id,
                                        'budget_qty': concept.quantity,
                                        'amount_cert': concept.amount_compute_cert,
                                        'stage_id': cert_stage.stage_id.id,
                                        'certif_qty': cert_stage.certif_qty,
                                        'concept_id': cert_stage.concept_id.id,
                                        'amount_budget': concept.sale_amount,
                                        'parent_id': cert_stage.concept_id.parent_id.id,
                                        'percent_acc': concept.percent_cert,
                                        'quantity_to_cert': quantity_to_cert,
                                        'project_employee_sheet_ids': [(6, 0, project_employee_sheet_ids)],
                                    }
                                    certification_lines.append((0, 0, vals))
                        else:
                            error = True
                    else:
                        concept.type_cert = 'stage'
                        concept.generate_stage_list()
                        for cert_stage in concept.certification_stage_ids:
                            if cert_stage.stage_id.state == stage:
                                # Insert the time sheet hours
                                quantity_to_cert = 0
                                project_employee_sheet_ids = []
                                bim_project_employee_timesheet_lines = self.env[
                                    'bim.project.employee.timesheet'].search(
                                    [('concept_id', '=', concept.id),
                                     ('bim_massive_certification_by_line_id', '=', False),
                                     ('state', '=', 'approved')])
                                if bim_project_employee_timesheet_lines:
                                    for line in bim_project_employee_timesheet_lines:
                                        quantity_to_cert += line.total_hours
                                        line.bim_massive_certification_by_line_id = self.id
                                        line.state = 'done'
                                        project_employee_sheet_ids.append(line.id)
                                else:
                                    quantity_to_cert = self.default_cuantity_to_cert

                                if self.certify_everything:
                                    quantity_to_cert = cert_stage.budget_qty

                                # Insert the time sheet hours
                                vals = {
                                    'certification_line_id': cert_stage.id,
                                    'budget_qty': concept.quantity,
                                    'amount_cert': concept.amount_compute_cert,
                                    'stage_id': cert_stage.stage_id.id,
                                    'certif_qty': cert_stage.certif_qty,
                                    'concept_id': cert_stage.concept_id.id,
                                    'amount_budget': concept.balance,
                                    'parent_id': cert_stage.concept_id.parent_id.id,
                                    'percent_acc': concept.percent_cert,
                                    'quantity_to_cert': quantity_to_cert,
                                    'project_employee_sheet_ids': [(6, 0, project_employee_sheet_ids)],
                                }
                                certification_lines.append((0, 0, vals))

            if error and len (certification_lines) == 0:
                raise UserError(_('Certification by Stage is not possible because this Budget has all its items certified by Manual Way'))

            record.certification_stage_ids = certification_lines
            record.certification_stage_ids.onchange_qty()
            record.certification_stage_ids.onchange_percent()

            if self.measurement_capture_ids:
                for line in record.certification_stage_ids:
                    measurement_capture_line_ids = self.env['measurement.capture.line'].search([
                        ('measurement_capture_id', 'in', self.measurement_capture_ids.ids),
                        ('concept_id', '=', line.concept_id.id)
                    ])
                    quantity_to_cert = sum(measurement_capture_line_ids.mapped('qty'))
                    line.quantity_to_cert = quantity_to_cert

                for measurement_capture_id in self.measurement_capture_ids:
                    measurement_capture_id.bim_massive_certification_by_line_id = self.id

    def load_line_by_fixed(self):
        for record in self:
            error = False
            for line in record.concept_ids:
                line.unlink()

            bim_general_config_id = self.env['bim.general.config'].search([
                ('key', '=', 'certification_update')
            ], limit=1)

            if bim_general_config_id and bim_general_config_id.value == '1':
                record.budget_id.update_amount()

            certification_lines = []
            sorted_concepts = sorted(record.budget_id.concept_ids, key=lambda s: s.parent_id.id)
            if not self.greater_than_100:
                concept_list = []
                for concp in sorted_concepts:
                    if concp.percent_cert < 100:
                        concept_list.append(concp)
                sorted_concepts = concept_list
            for concept in sorted_concepts:
                if concept.type == 'departure' and concept.parent_id.type == 'chapter':
                    if concept.quantity_cert > 0:
                        if concept.type_cert == 'fixed':
                            vals = {
                                'concept_id': concept.id,
                                'balance': concept.balance,
                                'quantity_cert': concept.quantity_cert,
                                'amount_cert': concept.amount_compute_cert,
                                'quantity': concept.quantity,
                                'percent_acc': concept.percent_cert,
                            }
                            certification_lines.append((0, 0, vals))
                        else:
                            error = True
                    else:
                        concept.type_cert = 'fixed'
                        vals = {
                            'concept_id': concept.id,
                            'balance': concept.balance,
                            'quantity_cert': concept.quantity_cert,
                            'amount_cert': concept.amount_compute_cert,
                            'quantity': concept.quantity,
                            'percent_acc': concept.percent_cert,
                        }
                        certification_lines.append((0, 0, vals))
            if error and len (certification_lines) == 0:
                raise UserError(_('Manual certification is not possible because this Budget has all its items certified by Stage'))
            record.concept_ids = certification_lines

    def action_load_consume(self):
        if self.budget_id:
            self.type_invoice = self.budget_id.state_id.type_invoice

        if not self.certification_stage_ids and not self.concept_ids:
            raise UserError(_("It is necessary to load Certification Lines before loading consume!"))

        for line in self.certification_stage_ids:
            percent = line.concept_id.balance_execute_percent * 100
            if percent > line.percent_acc:
                line.acc_certif = percent
                line.onchange_acc_certif()
                line.onchange_percent()

        for line in self.concept_ids:
            percent = line.concept_id.balance_execute_percent * 100
            if percent > line.percent_acc:
                line.acc_certif = percent
                line.onchange_acc_certif()
                line.onchange_percent_cert()

    def action_massive_certification(self):
        if not self.budget_id.state_id.allow_certification:
            raise UserError(_('You can not certify a Budget that is not in the state :Allow Certification'))


        if self.total_certif <= 0:
            raise UserError(_('The Certification amount must be greater than 0'))

        if self.certification_stage_ids:
            firs_stage = self.certification_stage_ids[0].stage_id

            bim_massive_certification_by_line = self.env['bim.massive.certification.by.line'].search(
                        [('stage_id', '=', firs_stage.id),
                        ('state', '!=', 'draft'),
                        ('id', '!=', self.id)
                        ])

            auto_etapa = False
            bim_general_config_id = self.env['bim.general.config'].search([
                ('key', '=', 'auto_etapa')], limit=1)
            if bim_general_config_id and bim_general_config_id.value == '1':
                auto_etapa = True

            if not auto_etapa:
                if bim_massive_certification_by_line and not self.same_stage:
                    raise UserError(_("There is already a massive certification in this stage!"))

        if self.type =='current_stage':
            self.certify_by_stage()
        else:
            self.certify_by_fixed()
        self.state = 'done'

    def action_fix(self):
        if self.type =='current_stage':
            self.rectify_by_stage()
        else:
            self.rectify_by_fixed()
        self.state = 'ready'

    def certify_by_stage(self):
        stage = False
        for line in self.certification_stage_ids:
            line.certification_line_id.certif_qty = line.certification_line_id.certif_qty + line.quantity_to_cert
            line.certification_line_id.certif_percent = line.certification_line_id.certif_percent + line.certif_percent

            if self.budget_id.type_calc_cert != 'quantity':
                # line.certification_line_id.onchange_percent()
                line.concept_id.onchange_percent_certification()
            else:
                line.certification_line_id.onchange_qty()
                line.concept_id.onchange_qty_certification()

            if line.certif_percent > 0:
                line.concept_id._compute_check_percent_certification()
            stage = line.stage_id
        param = self.env['ir.config_parameter'].sudo()
        if stage and param.get_param('close_stage_with_certification') == "True" and stage.state == "process":
            stage.action_approve()


    def certify_by_fixed(self):
        for line in self.concept_ids:
            line.concept_id.update_budget_type()
            line.concept_id.quantity_cert = line.concept_id.quantity_cert + line.quantity_to_cert
            line.concept_id.percent_cert = line.concept_id.percent_cert + line.percent_cert
            if line.percent_cert > 0:
                line.concept_id._compute_check_percent_certification()

    def rectify_by_stage(self):
        for line in self.certification_stage_ids:
            if line.stage_id.state == 'approved':
                raise UserError(_('It is not possible to Undo this Certification because it contains an Approved Stage'))
            line.certification_line_id.certif_qty = line.certification_line_id.certif_qty - line.quantity_to_cert if (line.certification_line_id.certif_qty - line.quantity_to_cert) >= 0 else 0
            line.certification_line_id.certif_percent = line.certification_line_id.certif_percent - line.certif_percent if(line.certification_line_id.certif_percent - line.certif_percent) >= 0 else 0
            # line.certification_line_id.onchange_percent()
            line.concept_id.onchange_percent_certification()
            line.concept_id.onchange_qty_certification()
            line.quantity_to_cert = 0
            line.certif_percent = 0

    def rectify_by_fixed(self):
        for line in self.concept_ids:
            line.concept_id.quantity_cert = line.concept_id.quantity_cert - line.quantity_to_cert if (line.concept_id.quantity_cert - line.quantity_to_cert) > 0 else 0
            line.concept_id.percent_cert = line.concept_id.percent_cert - line.percent_cert if (line.concept_id.percent_cert - line.percent_cert) >= 0 else 0
            line.quantity_to_cert = 0
            line.percent_cert = 0

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_('It is not possible to delete an Applied Certification. You must first Undo it and then Delete it'))
            record.project_employee_sheet_ids.write({"bim_massive_certification_by_line_id": False, "state": "approved"})
        return super(BimMasCertification, self).unlink()


class BimCertificationFixedCertification(models.Model):
    _name = 'bim.certification.fixed.certification'
    _description = "Manual Certification"

    @api.depends('quantity_to_cert')
    def _compute_amount(self):
        for record in self:
            record.amount_certif = record.quantity_to_cert * record.sale_price
            record.percent_cert = record.quantity_to_cert / record.quantity * 100 if record.quantity else 0

    @api.onchange('percent_cert')
    def onchange_percent_cert(self):
        for record in self:
            if record.type_calc_cert == 'quantity':
                record.quantity_to_cert = record.percent_cert * record.quantity / 100 if (record.percent_cert * record.quantity) > 0 else 0
                record.acc_certif = record.percent_cert + record.percent_acc


    parent_id = fields.Many2one(string='Chapter', related='concept_id.parent_id', required=True)
    name = fields.Char(string='Name', related='concept_id.display_name', required=True)
    quantity_cert = fields.Float(string='Accumulated Cert', default=0, digits='BIM qty')
    percent_acc = fields.Float(string='(%) Accumulated', default=0, digits=(10, 2))
    qty_acc = fields.Float(string='Quant Accumulated', default=0, digits='BIM qty')
    quantity_to_cert = fields.Float(string='Quant Cert', default=0, digits='BIM qty')
    percent_cert = fields.Float(string='(%) Cert Budget', default=0, digits=(10, 2))
    concept_id = fields.Many2one('bim.concepts', "Budget Item")
    balance = fields.Float(string='Total Budget', digits='BIM price')
    amount_certif = fields.Float(string='Balance Cert', digits='BIM price', compute='_compute_amount_certif')
    amount_cert = fields.Float(string='Amount Cert', digits='BIM price')
    quantity = fields.Float(string='Quant Budget(N)', digits='BIM qty')
    acc_certif = fields.Float(string='(%) Total Certif', digits=(10, 2))


    def _compute_amount_certif(self):
        for record in self:
            record.amount_certif = record.quantity_to_cert * record.sale_price

    @api.onchange('acc_certif')
    def onchange_acc_certif(self):
        for line in self:
            if line.acc_certif > 0 and line.percent_acc > line.acc_certif:
                raise UserError(_("Current Certification for Concept %s surpasses %s") % (
                line.name, str(line.acc_certif)))
            if line.acc_certif != 0:
                line.percent_cert = abs(line.acc_certif - line.percent_acc)
            else:
                line.percent_cert = 0


class BimCertificationStageCertification(models.Model):
    _name = 'bim.certification.stage.certification'
    _description = "Stage Certification"

    @api.depends('stage_id', 'stage_id.state', 'budget_qty', 'quantity_to_cert','certif_percent','sale_price','quantity_to_cert_o')
    def _compute_amount(self):
        for record in self:
                record.ImpOrig = record.quantity_to_cert_o * record.sale_price

    certification_line_id = fields.Many2one('bim.certification.stage')
    name = fields.Date(string='Date', related='certification_line_id.name', required=True)
    certif_qty = fields.Float(string='Accumulated Cert', default=0, digits='BIM qty')
    budget_qty = fields.Float(string='Quant Budget (N)', default=0, digits='BIM qty')
    quantity_to_cert = fields.Float(string='Quant Cert (N)', default=0, digits='BIM qty')
    planned_quantity = fields.Float(string='Quant Plan (N)', default=0, digits='BIM qty', compute='_compute_planned_quantity')
    quantity_to_cert_o = fields.Float(string='Quant Origin', default=0, digits='BIM qty')
    certif_percent = fields.Float(string='(%) Cert', default=0, digits=(10, 2))
    certif_percent_error = fields.Float(string='(%) C Error', default=0, digits=(10, 2), compute='_compute_certif_percent_error')
    stage_id = fields.Many2one('bim.budget.stage', "Stage", related='certification_line_id.stage_id')
    concept_id = fields.Many2one('bim.concepts', "Budget Item", related='certification_line_id.concept_id')
    uom_id = fields.Many2one('uom.uom', string='UoM', related='certification_line_id.concept_id.uom_id', store=True)

    amount_budget = fields.Float(string='Amount Budget', digits='BIM price')
    amount_certif = fields.Float(string='Balance Cert', digits='BIM price', compute="_compute_amount_certif")
    ImpOrig = fields.Float(string='Imp. Origin', digits='BIM price', compute="_compute_amount", store=True)
    ImpAnt = fields.Float(string='Imp. Ant.', digits='BIM price', compute="_compute_amount_ImpAnt", store=True)
    sale_price = fields.Float(string='Price Cert', digits='BIM price', compute="_compute_sale_price")
    parent_id = fields.Many2one('bim.concepts', string="Chapter")
    percent_acc = fields.Float(string='(%) Accumulated', default=0, digits=(10, 2))
    qty_acc = fields.Float(string='Quant Accumulated', default=0, digits='BIM qty')
    qty_t = fields.Float(string='Quant T.', default=0, digits='BIM qty' , compute='_compute_qty')
    balance = fields.Float(string='Balance', digits='BIM price')
    amount_cert = fields.Float(string='Amount Cert', digits='BIM price')
    acc_certif = fields.Float(string='(%) Total Certif')
    project_employee_sheet_ids = fields.Many2many('bim.project.employee.timesheet', 'bim_certification_stage_certification_rel', 'certification_id', 'employee_sheet_id', string='Employee Sheets')

    # Calculamos los totales de los importes de los capitulos
    TotalImpPres = fields.Float(string='Total Imp. Pres.', digits='BIM price')
    TotalImpAnt = fields.Float(string='Total Imp. Ant.', digits='BIM price')
    TotalImpOrig = fields.Float(string='Total Imp. Orig.', digits='BIM price')
    TotalImpAct = fields.Float(string='Total Imp. Act.', digits='BIM price')


    @api.depends('stage_id', 'concept_id')
    def _compute_planned_quantity(self):
        for record in self:
            record.planned_quantity = record.concept_id._compute_planned_quantity(record.stage_id.date_start, record.stage_id.date_stop)


    @api.depends('quantity_to_cert', 'sale_price')
    def _compute_amount_certif(self):
        for record in self:
            record.amount_certif = record.quantity_to_cert * record.sale_price



    @api.depends('qty_acc', 'sale_price')
    def _compute_amount_ImpAnt(self):
        for record in self:
            record.ImpAnt = record.qty_acc * record.sale_price

    @api.depends('concept_id')
    def _compute_sale_price(self):
        for record in self:
            record.sale_price = record.concept_id.sale_price if record.concept_id.sale_price > 0 else record.concept_id.amount_fixed

    @api.onchange('qty_acc','quantity_to_cert_o')
    def onchange_qty_acc_o(self):
        for record in self:
            for record in self:
                record.quantity_to_cert = record.quantity_to_cert_o - record.qty_acc

    @api.depends('certif_qty','quantity_to_cert')
    def _compute_qty(self):
        for record in self:
            record.qty_t = record.qty_acc + record.quantity_to_cert
            record.quantity_to_cert_o = record.quantity_to_cert + record.qty_acc

    @api.depends('certif_qty')
    def _compute_certif_percent_error(self):
        for record in self:
            if record.budget_qty <= 0:
                record.certif_percent_error = (record.quantity_to_cert / 1) * 100
            else:
                record.certif_percent_error = (record.quantity_to_cert / record.budget_qty) * 100


    @api.onchange('acc_certif')
    def onchange_acc_certif(self):
        for line in self:
            if line.acc_certif > 0 and line.percent_acc > line.acc_certif:
                raise UserError(_("Current Certification for Concept %s surpasses %s")%(line.concept_id.name,str(line.acc_certif)))
            if line.acc_certif != 0:
                line.certif_percent = abs(line.acc_certif - line.percent_acc)
            else:
                line.certif_percent = 0

    @api.onchange('quantity_to_cert')
    def onchange_qty(self):
        for record in self:
            if record.concept_id.budget_id.type_calc_cert == 'quantity':
                if record.budget_qty <= 0:
                    record.certif_percent = (record.quantity_to_cert / 1) * 100
                else:
                    record.certif_percent = (record.quantity_to_cert / record.budget_qty) * 100

    @api.onchange('certif_percent')
    def onchange_percent(self):
        for record in self:
            if record.concept_id.budget_id.type_calc_cert == 'percent':
                record.quantity_to_cert = (record.budget_qty * record.certif_percent) / 100
                record.acc_certif = record.certif_percent + record.percent_acc

    def action_next(self):
        if self.stage_state == 'draft':
            self.stage_id.state = 'process'
        elif self.stage_state == 'process':
            self.stage_id.state = 'approved'

    def action_cancel(self):
        return self.stage_id.write({'state': 'cancel'})


class BimCertificationMeasuring(models.Model):
    _name = 'bim.certification.measuring'
    _description = "Bim Certification Measuring"

    certification_line_id = fields.Many2one('bim.certification.stage')
    concept_id = fields.Many2one('bim.concepts', "Departure")

    qty = fields.Float(string='Quantity', default=0, digits='BIM qty')
    length = fields.Float(string='Length', default=0, digits='BIM length')
    width = fields.Float(string='Width', default=0, digits='BIM length')
    height = fields.Float(string='Height', default=0, digits='BIM length')
    amount_subtotal = fields.Float(string='Subtotal', default=0, digits='BIM price', compute='_compute_amount_subtotal')
    bim_certification_stage_certification_id = fields.Many2one('bim.certification.stage.certification', string='Bim Certification Line', copy=False)

    def _compute_amount_subtotal(self):
        for record in self:
            if record.length > 0 and record.width > 0 and record.height > 0:
                record.amount_subtotal = record.qty * record.length * record.width * record.height
            else:
                record.amount_subtotal = record.qty

