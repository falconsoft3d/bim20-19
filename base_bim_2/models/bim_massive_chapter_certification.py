# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimMasCertification(models.Model):
    _name = 'bim.massive.chapter.certification'
    _description = 'Massive Certification'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Sequence',required=True,  default='New', copy=False)
    user_id = fields.Many2one('res.users', string='Responsible', readonly=True, index=True, tracking=True,
                              required=True,
                              default=lambda self: self.env.user)
    type = fields.Selection([('current_stage','Current Stage'),('fixed','Manual')], string='Certification Type',required=True, default='current_stage', readonly=True)
    state = fields.Selection([('draft','Draft'),('ready','Validated'),('done','Certified'),('cancelled','Cancelled')], tracking=True, default='draft', string='Status',required=True)
    project_id = fields.Many2one('bim.project', string='Project', required=True, domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True, domain="[('project_id', '=', project_id),('state_id.allow_certification', '=', True)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True, readonly=True)
    certification_date = fields.Date(string='Certification Date', readonly=True, index=True, copy=False, default=fields.Date.context_today)
    creation_date = fields.Date(string='Creation Date', readonly=True, index=True, copy=False, default=fields.Date.context_today)
    note = fields.Text(copy=False)
    certification_stage_ids = fields.Many2many('bim.chapter.stage.certification', 'certification_chapters_rel', string='Certification', copy=False)
    concept_ids = fields.Many2many('bim.chapter.fixed.certification','certification_chapter_fixed_rel', string='Measurement', copy=False)
    total_certif = fields.Float(string='Balance Certif.', compute='_compute_total_certif', store=True, digits='BIM price')
    percent_certif = fields.Float(string='(%) Certif.', compute='_compute_total_certif', store=True)
    greater_than_100 = fields.Boolean(string='(%) >= 100', default=True)
    certif_percent_mass = fields.Float(string='(%) Cert', default=0)
    paid_state_id = fields.Many2one('bim.paidstate',copy=False)
    invoice_state = fields.Selection([('pending', 'Pending'), ('invoiced', 'Invoiced')], string='Invoice Status',
                                     default='pending', compute="_compute_invoice_state", store=True)
    acc_certif_percent_mass = fields.Float(string='(%) Total Cert', default=0)

    @api.constrains('acc_certif_percent_mass')
    def on_save_acc_certif_percent_mass(self):
        for record in self:
            if record.acc_certif_percent_mass > 0:
                record.certif_percent_mass = 0

    @api.onchange('acc_certif_percent_mass')
    def onchange_acc_certif_percent_mass(self):
        for record in self:
            if record.acc_certif_percent_mass >= 0:
                for line in record.certification_stage_ids:
                    line.acc_certif = record.acc_certif_percent_mass
                    line.onchange_acc_certif()
                for line in record.concept_ids:
                    line.acc_certif = record.acc_certif_percent_mass
                    line.onchange_acc_certif()

    @api.constrains('certif_percent_mass')
    def on_save_certif_percent_mass(self):
        for record in self:
            if record.certif_percent_mass > 0:
                record.acc_certif_percent_mass = 0

    @api.onchange('certif_percent_mass')
    def onchange_certif_percent_mass(self):
        for record in self:
            if record.certif_percent_mass >= 0:
                for line in record.certification_stage_ids:
                    line.certif_percent = record.certif_percent_mass
                    line.acc_certif = line.certif_percent + line.percent_acc
                for line in record.concept_ids:
                    line.certif_percent = record.certif_percent_mass
                    line.acc_certif = line.certif_percent + line.percent_acc

    @api.depends('paid_state_id', 'paid_state_id.invoice_id', 'paid_state_id.invoice_id.state')
    def _compute_invoice_state(self):
        for certification in self:
            certification.invoice_state = 'invoiced' if certification.paid_state_id \
                                                        and certification.paid_state_id.invoice_id and certification.paid_state_id.invoice_id.state == \
                                                        'posted' else 'pending'

    def action_create_paid_state(self):
        self.paid_state_id = self.paid_state_id.create({
            'chapter_certification_ids': [self.id],
            'type': 'certification',
            'load_certifications': False,
            'project_id': self.project_id.id,
            'lines_ids':[(0,0,{
               'budget_id': self.budget_id.id,
               'name': self.budget_id.name,
               'quantity': 1,
               'price_unit': self.total_certif,
               'certification_factor': self.budget_id.certification_factor,
               'is_loaded': True
                })]
           }).id
        self.budget_id.compute_balance_certified_residual()

    def fix_certification_by_stage(self):
        for line in self.certification_stage_ids:
            line.amount_cert = line.concept_id.amount_compute_cert

    @api.depends('concept_ids.amount_certif','certification_stage_ids.amount_certif')
    def _compute_total_certif(self):
        for record in self:
            amount = 0
            if record.type == 'current_stage':
                for line in record.certification_stage_ids:
                    amount += line.amount_certif
            else:
                for line in record.concept_ids:
                    amount += line.amount_certif
            record.total_certif = amount
            record.percent_certif = record.total_certif / record.budget_id.balance * 100 if record.budget_id.balance > 0 else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.massive.chapter.certification'
                ) or 'New'

        records = super().create(vals_list)

        for res in records:
            if not res.budget_id.stage_ids and res.type == 'current_stage':
                raise UserError(_(
                    "You cannot create a certification if the Project does not have stages created. "
                    "Please generate some Project Stages and try again."
                ))

            if res.type == 'current_stage':
                res._validate_current_stage()

        return records

    def _validate_current_stage(self):
        for record in self:
            current_stage = record.budget_id.stage_ids.filtered_domain([('state', '=', 'process')])
            if not current_stage and record.type == 'current_stage':
                raise UserError(
                    _("It is not possible use Current Stage mode because there is not current stage in this budget."))
            return current_stage[0].id

    def action_ready(self):
        if self.type == 'current_stage':
            if not self.stage_id:
                raise UserError(_('You must select the Stage to Certify'))
        self.state = 'ready'

    def action_cancel(self):
        self.state='cancelled'

    def action_convert_to_draft(self):
        self.state='draft'

    def action_load_lines(self):
        if self.type == 'current_stage':
            self.load_line_by_stage()
        else:
            self.load_line_by_fixed()
        self.state = 'ready'

    def load_line_by_stage(self):
        for record in self:
            for line in record.certification_stage_ids:
                line.unlink()
            record.budget_id.update_amount()
            certification_lines = []
            current_stage = record._validate_current_stage()
            budget_chapters = record.budget_id.concept_ids.filtered_domain([('type','=','chapter')])
            sorted_concepts = sorted(budget_chapters, key=lambda s: s.parent_id.id)
            if not self.greater_than_100:
                concept_list = []
                for concp in sorted_concepts:
                    if concp.percent_cert < 100:
                        concept_list.append(concp)
                sorted_concepts = concept_list
            sorted_list = []
            for chapter in sorted_concepts:
                if not chapter.parent_id:
                    sorted_list.append(chapter)
                else:
                    position = 0
                    pos_end = 0
                    found = False
                    for element in sorted_list:
                        if element == chapter.parent_id:
                            found = True
                            break
                        position += 1
                    if found:
                        for element in sorted_list[position:]:
                            if element == chapter.parent_id or element.parent_id == chapter.parent_id:
                                pass
                            else:
                                break
                            pos_end += 1
                        sorted_list.insert(position+pos_end,chapter)

                    if not found:
                        sorted_list.append(chapter)

            sorted_concepts = sorted_list
            for chapter in sorted_concepts:
                    vals = {
                        'budget_qty': chapter.quantity,
                        'stage_id': current_stage,
                        'amount_budget': chapter.balance,
                        'parent_id': chapter.id,
                        'certification_line_ids': [],
                        'percent_acc': chapter.percent_cert,
                    }
                    certification_stage_ids = []
                    certification_stage_ids = record._get_recursive_child_certification_ids(chapter, certification_stage_ids, current_stage)
                    vals.update({'certification_line_ids': certification_stage_ids})
                    if len(certification_stage_ids) > 0:
                        certification_lines.append((0, 0, vals))

            if len(certification_lines) == 0:
                raise UserError(_('Certification by Stage is not possible'))
            record.certification_stage_ids = certification_lines

    def _get_recursive_child_certification_ids(self, chapter, certification_stage_ids, current_stage):
        for child in chapter.child_ids.filtered_domain([('type', 'in', ['departure', 'chapter'])]):
            if child.type == 'chapter':
                self._get_recursive_child_certification_ids(child, certification_stage_ids, current_stage)
            elif child.type == 'departure':
                if (child.type_cert != 'stage' and child.quantity_cert == 0):
                    child.type_cert = 'stage'
                if child.type_cert == 'stage':
                    if not child.certification_stage_ids:
                        child.generate_stage_list()
                    for cert_stage in child.certification_stage_ids:
                        if cert_stage.stage_id.id == current_stage:
                            certification_stage_ids.append(cert_stage.id)
        return certification_stage_ids

    def _get_recursive_certifiable_child_ids(self, chapter, certifiable_child_ids):
        for child in chapter.child_ids.filtered_domain([('type', 'in', ['departure', 'chapter'])]):
            if child.type == 'chapter':
                self._get_recursive_certifiable_child_ids(child, certifiable_child_ids)
            elif child.type == 'departure':
                if (child.type_cert != 'fixed' and child.quantity_cert == 0):
                    child.type_cert = 'fixed'
                if child.type_cert == 'fixed':
                    certifiable_child_ids.append(child.id)
        return certifiable_child_ids

    def load_line_by_fixed(self):
        for record in self:
            for line in record.concept_ids:
                line.unlink()
            record.budget_id.update_amount()
            certification_lines = []
            budget_chapters = record.budget_id.concept_ids.filtered_domain([('type','=','chapter')])
            sorted_concepts = sorted(budget_chapters, key=lambda s: s.parent_id.id)
            if not self.greater_than_100:
                concept_list = []
                for concp in sorted_concepts:
                    if concp.percent_cert < 100:
                        concept_list.append(concp)
                sorted_concepts = concept_list
            sorted_list = []
            for chapter in sorted_concepts:
                if not chapter.parent_id:
                    sorted_list.append(chapter)
                else:
                    position = 0
                    pos_end = 0
                    found = False
                    for element in sorted_list:
                        if element == chapter.parent_id:
                            found = True
                            break
                        position += 1
                    if found:
                        for element in sorted_list[position:]:
                            if element == chapter.parent_id or element.parent_id == chapter.parent_id:
                                pass
                            else:
                                break
                            pos_end += 1
                        sorted_list.insert(position+pos_end,chapter)

                    if not found:
                        sorted_list.append(chapter)

            sorted_concepts = sorted_list

            for chapter in sorted_concepts:
                    vals = {
                        'budget_qty': chapter.quantity,
                        'amount_budget': chapter.balance,
                        'parent_id': chapter.id,
                        'certifiable_child_ids': [],
                        'percent_acc': chapter.percent_cert,
                    }
                    certifiable_child_ids = []
                    certifiable_child_ids = record._get_recursive_certifiable_child_ids(chapter, certifiable_child_ids)
                    vals.update({'certifiable_child_ids': certifiable_child_ids})
                    if len(certifiable_child_ids) > 0:
                        certification_lines.append((0, 0, vals))

            if len(certification_lines) == 0:
                raise UserError(_('Certification by Fixed is not possible'))
            record.concept_ids = certification_lines

    def action_massive_certification(self):
        if self.type =='current_stage':
            self.certify_by_stage()
        else:
            self.certify_by_fixed()
        self.state = 'done'

    def action_load_consume(self):
        if not self.certification_stage_ids and not self.concept_ids:
            raise UserError(_("It is necessary to load Certification Lines before loading consume!"))
        for line in self.certification_stage_ids:
            percent = line.parent_id.balance_execute_percent * 100
            if percent > line.percent_acc:
                line.acc_certif = percent
                line.onchange_acc_certif()
                line.onchange_certif_percent()

        for line in self.concept_ids:
            percent = line.parent_id.balance_execute_percent * 100
            if percent > line.percent_acc:
                line.acc_certif = percent
                line.onchange_acc_certif()
                line.onchange_certif_percent()

    def action_fix(self):
        if self.type =='current_stage':
            self.rectify_by_stage()
        else:
            self.rectify_by_fixed()
        self.state = 'ready'

    def certify_by_stage(self):
        stage = False
        for line in self.certification_stage_ids.filtered_domain([('certif_percent','!=',0)]):
            for cert_line in line.certification_line_ids:
                cert_line.certif_percent += line.certif_percent
                cert_line.onchange_percent()
                cert_line.concept_id.onchange_percent_certification()
                cert_line.concept_id.onchange_qty_certification()
                if not cert_line.concept_id._check_percent_certification():
                    raise UserError(_("Chapter {} can not be certificated because at least Concept {} surpasses its Budget Certification Limit. You can remove it and continue.").format(line.parent_id.display_name,cert_line.concept_id.display_name))
            stage = line.stage_id
        param = self.env['ir.config_parameter'].sudo()
        if stage and param.get_param('close_stage_with_certification') == "True" and stage.state == "process":
            stage.action_approve()

    def certify_by_fixed(self):
        for line in self.concept_ids.filtered_domain([('certif_percent','!=',0)]):
            for certifiable in line.certifiable_child_ids:
                certifiable.update_budget_type()
                certifiable.quantity_cert += certifiable.quantity * line.certif_percent / 100
                certifiable.percent_cert += line.certif_percent
                if not certifiable._check_percent_certification():
                    raise UserError(
                        _("Chapter {} can not be certificated because at least Concept {} surpasses its Budget Certification Limit. You can remove it and continue.").format(
                            line.parent_id.display_name, certifiable.display_name))

    def rectify_by_stage(self):
        for line in self.certification_stage_ids.filtered_domain([('certif_percent','!=',0)]):
            if line.stage_id.state == 'approved':
                raise UserError(_('It is not possible to Undo this Certification because it contains an Approved Stage'))
            for cert_line in line.certification_line_ids:
                cert_line.certif_percent = cert_line.certif_percent - line.certif_percent if(cert_line.certif_percent - line.certif_percent) >= 0 else 0
                cert_line.onchange_percent()
                cert_line.concept_id.onchange_percent_certification()
                cert_line.concept_id.onchange_qty_certification()
            line.certif_percent = 0

    def rectify_by_fixed(self):
        for line in self.concept_ids:
            for certifiable in line.certifiable_child_ids:
                quantity_cert = certifiable.quantity * line.certif_percent / 100
                certifiable.quantity_cert = certifiable.quantity_cert - quantity_cert if (certifiable.quantity_cert - quantity_cert) > 0 else 0
                certifiable.percent_cert = certifiable.percent_cert - line.certif_percent if (certifiable.percent_cert - line.certif_percent) >= 0 else 0
                certifiable.update_budget_type()
            line.certif_percent = 0

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_('It is not possible to delete an Applied Certification. You must first Undo it and then Delete it'))
        return super(BimMasCertification, self).unlink()


class BimCertificationFixedCertification(models.Model):
    _name = 'bim.chapter.fixed.certification'
    _description = "Manual Certification"

    budget_qty = fields.Float(string='Quant Budget (N)', default=0, digits='BIM qty')
    amount_budget = fields.Float(string='Total Budget', digits='BIM price')
    parent_id = fields.Many2one('bim.concepts', string="Chapter")
    percent_acc = fields.Float(string='(%) Accumulated', default=0)
    amount_certif = fields.Float(string='Balance Cert', digits='BIM price', compute="_compute_amount", store=True)
    certif_percent = fields.Float(string='(%) Cert', default=0)
    certifiable_child_ids = fields.Many2many('bim.concepts', string="Certifiable childs")
    acc_certif = fields.Float(string='(%) Total Certif')

    @api.onchange('acc_certif')
    def onchange_acc_certif(self):
        for line in self:
            if line.acc_certif > 0 and line.percent_acc > line.acc_certif:
                raise UserError(_("Current Certification for Chapter %s surpasses %s") % (
                line.parent_id.name, str(line.acc_certif)))
            if line.acc_certif != 0:
                line.certif_percent = abs(line.acc_certif - line.percent_acc)
            else:
                line.certif_percent = 0

    @api.onchange('certif_percent')
    def onchange_certif_percent(self):
        for line in self:
            line.acc_certif = line.certif_percent + line.percent_acc

    @api.depends('certif_percent')
    def _compute_amount(self):
        for record in self:
            if record.amount_budget > 0 and record.certif_percent > 0:
                amount_cert_total = 0
                for line in record.certifiable_child_ids:
                    if line.balance > 0:
                        amount_cert_total += line.balance * record.certif_percent / 100
                record.amount_certif = amount_cert_total
            else:
                record.amount_certif = 0


class BimCertificationStageCertification(models.Model):
    _name = 'bim.chapter.stage.certification'
    _description = "Stage Certification"

    @api.depends('stage_id', 'stage_id.state', 'budget_qty', 'certif_percent')
    def _compute_amount(self):
        for record in self:
            if record.amount_budget > 0 and record.certif_percent > 0:
                amount_cert_total = 0
                for line in record.certification_line_ids:
                    if line.concept_id.balance > 0:
                        amount_cert_total += line.concept_id.balance * record.certif_percent / 100
                record.amount_certif = amount_cert_total
            else:
                record.amount_certif = 0


    budget_qty = fields.Float(string='Quant Budget (N)', default=0, digits='BIM qty')
    stage_id = fields.Many2one('bim.budget.stage', "Stage", required=True)
    amount_budget = fields.Float(string='Total Budget', digits='BIM price')
    parent_id = fields.Many2one('bim.concepts', string="Chapter")
    percent_acc = fields.Float(string='(%) Accumulated', default=0)
    amount_certif = fields.Float(string='Balance Cert', digits='BIM price', compute="_compute_amount", store=True)
    certif_percent = fields.Float(string='(%) Cert', default=0)
    certification_line_ids = fields.Many2many('bim.certification.stage')
    concept_ids = fields.Many2many('bim.concepts', compute='_compute_bim_concepts', string="Certifiable childs")
    acc_certif = fields.Float(string='(%) Total Certif')

    @api.onchange('acc_certif')
    def onchange_acc_certif(self):
        for line in self:
            if line.acc_certif > 0 and line.percent_acc > line.acc_certif:
                raise UserError(_("Current Certification for Chapter %s surpasses %s") % (
                line.parent_id.name, str(line.acc_certif)))
            if line.acc_certif != 0:
                line.certif_percent = abs(line.acc_certif - line.percent_acc)
            else:
                line.certif_percent = 0

    @api.onchange('certif_percent')
    def onchange_certif_percent(self):
        for line in self:
            line.acc_certif = line.certif_percent + line.percent_acc

    def _compute_bim_concepts(self):
        for rec in self:
            concepts = []
            for line in rec.certification_line_ids:
                concepts.append(line.concept_id.id)
            rec.concept_ids = concepts

    def action_next(self):
        if self.stage_state == 'draft':
            self.stage_id.state = 'process'
        elif self.stage_state == 'process':
            self.stage_id.state = 'approved'

    def action_cancel(self):
        return self.stage_id.write({'state': 'cancel'})

