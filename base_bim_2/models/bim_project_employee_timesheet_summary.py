from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta
import logging
_logger = logging.getLogger(__name__)

class BimProjectEmployeeTimesheetSummary(models.Model):
    _name = 'bim.project.employee.timesheet.summary'
    _description = 'Bim Project Employee Timesheet Summary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char('Name', default="New")
    customer_id = fields.Many2one('res.partner', string='Customer')
    date_create = fields.Date('Date', default=fields.Date.today())
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    invoice_id = fields.Many2one('account.move', string='Invoice')
    state = fields.Selection([
        ('draft', 'New'),
        ('done', 'Done'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        tracking=True, default='draft')

    timesheet_line_ids = fields.One2many('bim.project.employee.timesheet.summary.line', 'summary_id',
                                         string='Timesheet')

    total_hours = fields.Float('Total Hours', compute='_compute_total_hours')
    total_cost = fields.Float('Total Cost', compute='_compute_total_cost')
    total_price = fields.Float('Total Price', compute='_compute_total_price')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    @api.depends('timesheet_line_ids')
    def _compute_total_price(self):
        for record in self:
            record.total_price = sum(record.timesheet_line_ids.mapped('work_price'))

    @api.depends('timesheet_line_ids')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.timesheet_line_ids.mapped('work_cost'))


    @api.depends('timesheet_line_ids')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = sum(record.timesheet_line_ids.mapped('total_hours'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.project.employee.timesheet.summary') or 'New'
        return super().create(vals_list)

    def action_clear(self):
        for line in self.timesheet_line_ids:
            line.bim_project_employee_timesheet.bim_project_employee_timesheet_summary = False
            line.unlink()

    def action_create_invoice(self):
        if not self.customer_id:
            raise UserError(_("You must select a Partner."))
        if not self.timesheet_line_ids:
            raise UserError(_("You must load attendance first."))
        if self.total_price <= 0:
            raise UserError(_("You must have a total price greater than 0."))

        # Create invoice
        if self.project_id.paidstate_product:
            product = self.project_id.paidstate_product
        else:
            product = self.env.user.company_id.paidstate_product

        if not product:
            raise UserError(_("You must select a product for invoice."))

        vals = {
            'partner_id': self.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_line_ids': [
                (0, 0, {
                    'name': self.name,
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': self.total_price,
                })
            ],
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.customer_id.property_payment_term_id.id,
            'invoice_user_id': self.env.user.id,
        }

        invoice = self.env['account.move'].create(vals)
        self.invoice_id = invoice.id

        self.write({'state': 'invoiced'})


    def action_load(self):
        for line in self.timesheet_line_ids:
            line.bim_project_employee_timesheet.bim_project_employee_timesheet_summary = False
            line.unlink()

        time_sheets = self.env['bim.project.employee.timesheet'].search([
            ('partner_id', '=', self.customer_id.id),
            ('bim_project_employee_timesheet_summary', '=', False),
            ('state', '!=', 'draft')])

        if time_sheets:
            for sheet in time_sheets:
                vals = {
                    'bim_project_employee_timesheet': sheet.id,
                    'summary_id': self.id,
                }
                self.env['bim.project.employee.timesheet.summary.line'].create(vals)
                sheet.bim_project_employee_timesheet_summary = self.id

        self.write({'state': 'done'})

    def action_create_invoice(self):
        if not self.timesheet_line_ids:
            raise UserError(_("You must load timesheet lines first."))

        lines = []
        for line in self.timesheet_line_ids:
            product = line.project_id.paidstate_product and line.project_id.paidstate_product or self.env.company.paidstate_product
            if not product:
                raise UserError(_("You must select a product for invoice."))
            lines.append([0,0,{
                'name': line.project_id.name,
                'product_id': product.id,
                'price_unit': line.work_price,
                'quantity': 1,
            }])

        vals = {
            'partner_id': self.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_line_ids': lines,
            'invoice_origin': self.name,
            'invoice_user_id': self.user_id.id,
        }

        invoice = self.env['account.move'].create(vals)
        self.invoice_id = invoice.id
        self.write({'state': 'invoiced'})
        
    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_approve(self):
        self.write({'state': 'approved'})


    def action_email_send(self):
        self.ensure_one()
        lang = self.env.context.get('lang')
        mail_template = self.env.ref('base_bim_2.email_template_timesheet_summary')
       
        ctx = {
            'default_model': 'bim.project.employee.timesheet.summary',
            'default_res_id': self.id,
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'force_email': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
        
    def cron_load_timesheet_summary(self):
        _logger.info('cron_load_timesheet_summary')

        # get all timesheet without summary in state != draft
        timesheets = self.env['bim.project.employee.timesheet'].search([
            ('bim_project_employee_timesheet_summary', '=', False),
            ('state', '!=', 'draft')
        ]).mapped('partner_id')

        for timesheet in timesheets:
            # Create a new summary
            summary_id = self.create({
                'customer_id': timesheet.id,
            })
            # Update attendance
            summary_id.action_load()


class BimProjectEmployeeTimesheetSummaryLine(models.Model):
    _name = 'bim.project.employee.timesheet.summary.line'
    _description = 'Bim Project Employee Time sheet Summary Line'
    _rec_name = 'project_id'

    bim_project_employee_timesheet = fields.Many2one('bim.project.employee.timesheet',
                                                     string='Employee Timesheet')
    project_id = fields.Many2one('bim.project', 'Project', related='bim_project_employee_timesheet.project_id', store=True)
    budget_id = fields.Many2one('bim.budget', string='Budget'
                                , related='bim_project_employee_timesheet.budget_id', store=True)
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="cascade"
                                    , related='bim_project_employee_timesheet.concept_id', store=True)

    task_id = fields.Many2one('bim.task', 'Task')
    date = fields.Date('Date',
                        related='bim_project_employee_timesheet.date', store=True)

    total_hours = fields.Float('Total Hours', digits="BIM qty"
                               , related='bim_project_employee_timesheet.total_hours', store=True)

    summary_id = fields.Many2one('bim.project.employee.timesheet.summary', string='Timesheet Summary')

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                    related='bim_project_employee_timesheet.employee_id', store=True)

    bim_extra_hour = fields.Many2one('bim.extra.hour', 'Extra Hour',
                                     related='bim_project_employee_timesheet.bim_extra_hour', store=True)

    work_cost = fields.Float('Total Cost', digits="BIM price",
                             related='bim_project_employee_timesheet.work_cost', store=True)

    work_price = fields.Float('Total Price', digits="BIM price",
                                related='bim_project_employee_timesheet.work_price', store=True)
