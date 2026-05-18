# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError
from datetime import timedelta
from datetime import date
import logging
_logger = logging.getLogger(__name__)


STATE = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('done', 'Done'),
    ('cancel', 'Cancelled')]

TYPE = [
    ('deliver', 'Deliver'),
    ('withdraw', 'Withdraw'),
    ('deprecation', 'Deprecation'),
    ('transfer', 'Transfer')]

RO_STATES = {'done': [('readonly', True)], 'approved': [('readonly', True)], 'cancel': [('readonly', True)], 'requested': [('readonly', True)]}


class EmployeeTools(models.Model):
    _name = 'employee.tools'
    _description = 'Employee Tools'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Reference', required=True, copy=False, readonly=True,
                       index=True, default='New')
    date = fields.Date('Date', default=fields.Date.today, required=True)
    user_id = fields.Many2one('res.users', string='User', tracking=True, readonly=True, default=lambda self: self.env.user)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    picking_id = fields.Many2one('stock.picking', string='Picking', readonly=True, copy=False)
    notes = fields.Text('Notes', default="")
    state = fields.Selection(STATE, string='State', index=True, readonly=True, tracking=True, default='draft',
                             copy=False)
    tool_ids = fields.One2many('employee.tools.line', 'operation_id', string='Tools', copy=True)
    company_id = fields.Many2one(comodel_name="res.company", string='Company', default=lambda self: self.env.company,
                                 required=True, readonly=True)
    type = fields.Selection(TYPE, string='Type', index=True, default='deliver', copy=False, required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('bim.project', 'Project', ondelete="restrict", copy=True,
                                 domain="[('company_id','=',company_id)]")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="restrict", copy=True,
                                domain="[('project_id','=',project_id)]")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="restrict", copy=True,
                                 domain="[('budget_id','=',budget_id),('type','=','departure')]")
    amount_total = fields.Float(compute='compute_amount_total', store=True)
    motive_id = fields.Many2one('bim.tool.deprecation')
    location_id = fields.Many2one('stock.location', domain="[('company_id','=',company_id),('usage','=','internal')]")
    location_dest_id = fields.Many2one('stock.location', domain="[('company_id','=',company_id),('usage','=','internal')]")




    def _get_default_location(self):
        LocationObj = self.env['stock.location']
        internal_location =  LocationObj.search([('company_id','=',self.env.company.id),('usage','=','internal')],
                                                limit=1, order='id').id or False
        if self.type == 'deliver':
            self.location_id = internal_location
            self.location_dest_id = LocationObj.search([('usage','=','customer')],limit=1, order='id').id or False

        elif self.type == 'withdraw':
            self.location_dest_id = internal_location
            self.location_id = LocationObj.search([('usage', '=', 'supplier')], limit=1, order='id').id or False

        else:
            self.location_dest_id = False
            self.location_id = False

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id:
            if self.employee_id.epi_location_id:
                self.location_id = self.employee_id.epi_location_id.id

    @api.onchange('type')
    def onchange_project_id(self):
        LocationObj = self.env['stock.location']
        if self.project_id and self.project_id.stock_location_id:
            if self.type == 'deliver':
                self.location_id = self.project_id.stock_location_id.id
                self.location_dest_id = LocationObj.search([('usage', '=', 'customer')], limit=1,
                                                                             order='id').id or False
            elif self.type == 'withdraw':
                self.location_dest_id = self.project_id.stock_location_id.id
                self.location_id = LocationObj.search([('usage','=','supplier')],limit=1, order='id').id or False

        else:
            self._get_default_location()

    def action_send_email(self):
        """."""
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference(
                'hr_deliver_products', 'email_template_deliver_products2')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(
                'mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'deliver.products',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def _create_picking(self, picking_type, location_id, location_dest):
        # log
        _logger.info('BEGIN _create_picking')


        moves = []

        for line in self.tool_ids:
            if line.product_id.type in [
                    'consu', 'product']:
                moves.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_id.uom_id.id,
                    'name': line.product_id.name,
                    'quantity': line.qty,
                    'location_id': location_id.id,
                    'location_dest_id': location_dest.id,
                }))

        if moves:
            values = {
                'picking_type_id': picking_type,
                'origin': self.name,
                'move_ids': moves,
                'location_id': location_id.id,
                'location_dest_id': location_dest.id,
                'partner_id': self.employee_id.user_partner_id.id,
                'company_id': self.env.user.company_id.id,
                'scheduled_date': self.date.strftime('%Y-%m-%d'),
                'bim_project_id': self.project_id.id,
                'bim_concept_id': self.concept_id.id,
                'bim_budget_id': self.budget_id.id,
            }
            picking = self.env['stock.picking'].create(values)
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()
            self.picking_id = picking.id

        _logger.info('END _create_picking')

    def action_cancel(self):
        self.state = 'cancel'

    def action_approve(self):
        if not self.tool_ids:
            raise UserError(_('You need to add some tools!'))
        self.state = 'approved'

    def get_picking_type(self):
        picking_type = self.env['stock.picking.type']
        if self.project_id and self.project_id.warehouse_id:
            if self.type == 'deliver':
                picking_type = self.project_id.warehouse_id.out_type_id.id or False
            elif self.type == 'withdraw':
                picking_type = self.project_id.warehouse_id.in_type_id.id or False
        else:
            if self.type == 'deliver':
                picking_type = picking_type.search([('company_id','=',self.company_id.id),('code','=','outgoing')],limit=1).id or False
            elif self.type == 'withdraw':
                picking_type = picking_type.search([('company_id','=',self.company_id.id),('code','=','incoming')],limit=1).id or False
        if not picking_type:
            raise UserError(_("There is not Operation Type configured for this Picking"))
        return picking_type

    def action_create_picking(self):
        params = self.env['ir.config_parameter'].sudo()
        tools_inventory_movement = params.get_param('tools.inventory.movement')
        if self.type not in ('transfer','deprecation') and tools_inventory_movement == 'True':
            picking_type = self.get_picking_type()
            partner_id = self.employee_id.user_partner_id

            if not partner_id:
                partner_id = self.env['res.partner'].search([('name','=',self.employee_id.name)], limit=1)

            if not partner_id:
                raise UserError(_('Employee %s does not have any related address.'%self.employee_id.display_name))


            location =  self.location_dest_id

            self._create_picking(picking_type,self.location_id, location)
        self.state = 'done'

    def action_return_draft(self):
        self.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('employee.tools') or 'New'
        return super().create(vals_list)

    @api.depends('tool_ids','tool_ids.subtotal')
    def compute_amount_total(self):
        for record in self:
            record.amount_total = sum(line.subtotal for line in self.tool_ids)


class EmployeeToolsLine(models.Model):
    _name = 'employee.tools.line'
    _description = "Employee Tools Line"
    _rec_name = 'product_id'
    _order = 'id desc'

    product_id = fields.Many2one('product.product', string='Product', required=True, domain="[('tool_ok','=',True)]")
    qty = fields.Float('Quantity', default=1)
    cost = fields.Float('Cost')
    subtotal = fields.Float('Subtotal', compute='compute_total_cost', store=True)
    operation_id = fields.Many2one('employee.tools', string="Operation",ondelete='cascade')
    note = fields.Char('Notes')
    state = fields.Selection(related='operation_id.state', store=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', related='operation_id.company_id')
    currency_id = fields.Many2one('res.currency', related='operation_id.currency_id')
    employee_id = fields.Many2one('hr.employee', related='operation_id.employee_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', related='operation_id.employee_id.user_partner_id', store=True, readonly=True)
    date = fields.Date(related='operation_id.date', store=True, readonly=True)
    type = fields.Selection(related='operation_id.type', store=True, readonly=True)
    user_id = fields.Many2one('res.users', related='operation_id.user_id', store=True, readonly=True)
    stock_product = fields.Float(related='product_id.qty_available', readonly=True)
    categ_id = fields.Many2one('product.category', related='product_id.product_tmpl_id.categ_id', store=True, readonly=True)
    date_due = fields.Date()
    date_due_readonly = fields.Boolean()

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.cost = self.with_company(self.company_id).product_id.standard_price
        if self.product_id and self.product_id.deprecation_days:
            self.date_due = self.date + timedelta(days=self.product_id.deprecation_days)
            self.date_due_readonly = True

    @api.onchange('qty', 'cost')
    def compute_total_cost(self):
        for record in self:
            record.subtotal = record.qty * record.cost
