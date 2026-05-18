# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class PartnerAttendanceContract(models.Model):
    _description = "Partner Attendance Contract"
    _name = 'partner.attendance.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'


    name = fields.Char(string='Code', required=True,
    readonly=True, copy=False, index=True,
    default=lambda self: self.env['ir.sequence'].next_by_code('partner.attendance.contract'))

    partner_id = fields.Many2one('res.partner', 'Provider', ondelete="cascade", required=True)
    project_id = fields.Many2one('bim.project', 'Project', required=True, help="The project associated with the partner's attendance contract.")
    hourly_rate = fields.Float('Hourly Rate', required=True, help="Rate per hour for the partner's attendance.")


    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)

    date_start = fields.Date('Start Date', required=True, default=fields.Date.today, help="The date when the contract starts.")
    date_end = fields.Date('End Date', required=True, default=fields.Date.today, help="The date when the contract ends. If not set, the contract is considered ongoing.")

    lines_ids = fields.One2many('partner.attendance.contract.line', 'contract_id', string='Contract Lines', copy=True, help="Lines defining the attendance contract details for each partner.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft',
    tracking=True,
    required=True, help="The current status of the attendance contract.")


    hours_of_rest = fields.Float('Hours of Rest', default=0.0, help="The number of hours of rest included in the contract. This is used to calculate the balance for the partner's attendance.")
    fixed_cost = fields.Float('Fixed Cost', default=0.0, help="A fixed cost associated with the contract, if applicable. This can be used to cover additional expenses or fees related to the partner's attendance.")

    @api.onchange('state')
    def onchange_state(self):
        for rec in self:
            if rec.state == 'active':
                domain = [
                    ('state', '=', 'active'),
                    ('partner_id', '=', rec.partner_id.id),
                    ('project_id', '=', rec.project_id.id),
                ]

                # Solo excluye el contrato actual si ya existe en BD
                if rec.id and isinstance(rec.id, int):
                    domain.append(('id', '!=', rec.id))

                domain += [
                    ('date_start', '<=', rec.date_end),
                    ('date_end', '>=', rec.date_start),
                ]

                existing_contracts = self.env['partner.attendance.contract'].search(domain, limit=1)
                if existing_contracts:
                    raise ValidationError(_(
                        "Ya existe otro contrato activo con el mismo cliente y proyecto cuyas fechas se solapan. "
                        "Revise el contrato: %s" % existing_contracts.display_name
                    ))

class PartnerAttendanceContractLine(models.Model):
    _description = "Partner Attendance Contract Line"
    _name = 'partner.attendance.contract.line'

    contract_id = fields.Many2one('partner.attendance.contract', 'Contract', ondelete="cascade", required=True)
    partner_id = fields.Many2one('res.partner', 'Partner Employee', required=True, help="The partner associated with this attendance contract line.")
    parent_id = fields.Many2one('res.partner', related='contract_id.partner_id', string='Parent Partner', help="The parent company of the partner, if applicable.")

    hourly_rate = fields.Float('Hourly Rate', required=True, help="Rate per hour for the partner's attendance.")
    currency_id = fields.Many2one('res.currency', string='Currency',  default=lambda self: self.env.company.currency_id, help="The currency in which the hourly rate is defined.")
    state = fields.Selection(related='contract_id.state', string='Status', readonly=True, help="The status of the attendance contract to which this line belongs.")