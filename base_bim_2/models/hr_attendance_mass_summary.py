from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta
import logging
import base64
_logger = logging.getLogger(__name__)

class HrAttendanceMassSummary(models.Model):
    _name = 'hr.attendance.mass.summary'
    _description = 'Massive attendance summary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char('Name', default="New")
    project_id = fields.Many2one('bim.project', string='Project')
    customer_id = fields.Many2one('res.partner', string='Customer', related='project_id.customer_id')
    date_create = fields.Date('Date', default=fields.Date.today())
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    attendance_line_ids = fields.One2many('hr.attendance.mass.summary.line', 'attendance_id', string='Attendance')
    total_hours = fields.Float('Total Hours', compute='_compute_total_hours')
    total_price = fields.Float('Total Price', compute='_compute_total_price')

    invoice_id = fields.Many2one('account.move', string='Invoice')
    attendance_count = fields.Integer('Count', compute="_compute_attendances")
    state = fields.Selection([
        ('draft', 'New'),
        ('done', 'Done'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        tracking=True, default='draft')

    @api.depends('attendance_line_ids')
    def _compute_attendances(self):
        for record in self:
            record.attendance_count = len(record.attendance_line_ids.mapped('hr_attendance_id'))

            
    def action_create_invoice(self):
        if not self.project_id:
            raise UserError(_("You must select a project."))
        if not self.attendance_line_ids:
            raise UserError(_("You must load attendance first."))

        # Create invoice

        if self.project_id.paidstate_product:
            product = self.project_id.paidstate_product
        else:
            product = self.env.user.company_id.paidstate_product

        if not product:
            raise UserError(_("You must select a product for invoice."))

        vals = {
            'partner_id': self.project_id.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_line_ids': [
                (0, 0, {
                    'name': self.project_id.name,
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': self.total_price,
                })
            ],
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.project_id.customer_id.property_payment_term_id.id,
            'invoice_user_id': self.env.user.id,
        }

        invoice = self.env['account.move'].create(vals)
        self.invoice_id = invoice.id
        self.write({'state': 'invoiced'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_approve(self):
        for record in self:
            record.action_send_email()
            record.write({'state': 'approved'})

    def action_clear_line(self):
        # clear summary
        attendance_delete_ids = self.env['hr.attendance'].search([
            ('project_id', '=', self.project_id.id),
            ('attendance_summary_id', '=', self.id)
        ])
        for attendance in attendance_delete_ids:
            attendance.write({'attendance_summary_id': False})
        # Delete old lines
        self.attendance_line_ids.unlink()

    def action_view_attendances(self):
        att_ids = self.attendance_line_ids.mapped('hr_attendance_id').ids
        action = self.env["ir.actions.actions"]._for_xml_id("hr_attendance.hr_attendance_action")
        action['domain'] = [('id', 'in', att_ids)]
        action['context'] = {'search_default_project_id': self.project_id.id}
        return action
        
    def action_load(self):
        if not self.project_id:
            raise UserError(_("You must select a project."))

        # clear summary
        attendance_delete_ids = self.env['hr.attendance'].search([
            ('project_id', '=', self.project_id.id),
            ('attendance_summary_id', '=', self.id)
        ])
        for attendance in attendance_delete_ids:
            attendance.write({'attendance_summary_id': False})


        # Delete old lines
        self.attendance_line_ids.unlink()

        # Create new lines
        attendance_ids = self.env['hr.attendance'].search([
            ('project_id', '=', self.project_id.id),
            ('attendance_summary_id', '=', False)
        ])
        for attendance in attendance_ids:
            attendance.write({'attendance_summary_id': self.id})
            self.env['hr.attendance.mass.summary.line'].create({
                'project_id': self.project_id.id,
                'employee_id': attendance.employee_id.id,
                'check_in': attendance.check_in,
                'check_out': attendance.check_out,
                'worked_hours': attendance.worked_hours,
                'price': attendance.hour_price,
                'total': attendance.attendance_price,
                'hr_attendance_id': attendance.id,
                'attendance_id': self.id,
            })
        self.write({'state': 'done'})

    def action_send_email(self):
        subject  = 'Resumen de Asistencias'
        user = self.env.user
        company = self.env.company
        partner = self.customer_id
        if partner.email and partner.attendance_summary:
            pdf_attach = self.action_generate_pdf_attachment('base_bim_2.action_report_attendance_mass_summary')
            atts_ids = []
            if pdf_attach:
                atts_ids.append(pdf_attach.id)

            body = '''
                <b>Estimado ''' " %s</b>," % (partner.name) + '''
                <p>Este es su resumen de asistencia para un total de:<br/>
                ''' "%s" % (self.total_hours) +''' horas del proyecto.</p>

                <p>Proyecto:<br/>
                ''' "%s" % (self.project_id.name) +'''<br/>
                </p>

                <p><b>Saludos,</b> <br/>
                ''' "<b><i>%s</i></b>" % user.name +''' </p>
                '''
            mail_values = {
                'email_from': company.email or user.email,
                'email_to': partner.email,
                'subject': subject,
                'body_html': body,
                'state': 'outgoing',
                'message_type': 'email',
                'attachment_ids': [(6,0,atts_ids)],
                    }
            mail_id =self.env['mail.mail'].create(mail_values)
            mail_id.send(True)
        
    @api.depends('attendance_line_ids')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = sum(record.attendance_line_ids.mapped('worked_hours'))

    @api.depends('attendance_line_ids')
    def _compute_total_price(self):
        for record in self:
            record.total_price = sum(record.attendance_line_ids.mapped('total'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.attendance.mass.summary') or 'New'
        return super().create(vals_list)

    def cron_load_hr_attendance_mass_summary(self):
        _logger.info(':::STARTING CRON LOAD HR ATTENDANCE:::')
        # get all project from hr.attendance with out summary
        projects = self.env['hr.attendance'].search([
            ('attendance_summary_id', '=', False)
        ]).mapped('project_id')

        for project in projects:
            if project.customer_id.attendance_summary:
                # Create a new summary
                summary_id = self.create({
                    'project_id': project.id,
                    'date_create': fields.Date.today(),
                    'user_id': self.env.user.id,
                })
                # Update attendance
                summary_id.action_load()
            else:
                pass

            # Create a new summary
            summary_id = self.create({
                'project_id': project.id,
                'date_create': fields.Date.today(),
                'user_id': self.env.user.id,
            })
            # Update attendance
            summary_id.action_load()


    def action_generate_pdf_attachment(self, report_id):
        pdf = self.env['ir.actions.report']._render_qweb_pdf(report_id, self.id)[0]
        b64_pdf = base64.b64encode(pdf)
        ATTACHMENT_NAME = self.name
        return self.env['ir.attachment'].create({
            'name': ATTACHMENT_NAME,
            'type': 'binary',
            'datas': b64_pdf,
            'res_name': ATTACHMENT_NAME + '.pdf',
            'store_fname': ATTACHMENT_NAME,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/x-pdf'
        })


class HrAttendanceMassSummaryLine(models.Model):
    _name = 'hr.attendance.mass.summary.line'
    _description = 'Massive attendance summary line'
    _rec_name = 'employee_id'

    project_id = fields.Many2one('bim.project', string='Project')
    customer_id = fields.Many2one('res.partner', string='Customer', related='project_id.customer_id')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    check_in = fields.Datetime('Check In')
    check_out = fields.Datetime('Check Out')
    worked_hours = fields.Float('Worked Hours')
    price = fields.Float('Price')
    total = fields.Float('Total')

    attendance_id = fields.Many2one('hr.attendance.mass.summary', string='Attendance')
    hr_attendance_id = fields.Many2one('hr.attendance', string='HR Attendance')

