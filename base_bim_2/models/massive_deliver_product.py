# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError
from datetime import timedelta
from datetime import date

STATE = [
    ('draft', 'Draft'),
    ('requested', 'Requested'),
    ('approved', 'Approved'),
    ('done', 'Done'),
    ('cancel', 'Cancelled')]

TYPE = [
    ('delivery', 'Delivery'),
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer')]

RO_STATES = {'done': [('readonly', True)], 'approved': [('readonly', True)]}



class DeliverProducts(models.Model):
    """Deliver Products."""

    _name = 'massive.deliver.products'
    _description = 'Massive Deliver Products'
    _inherit = "mail.thread"
    _order = 'id desc'

    name = fields.Char(
        'Reference',
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))

    entry_date = fields.Date('Date', default=fields.Date.today)

    user_id = fields.Many2one(
        'res.users', string='User', tracking=True,
        default=lambda self: self.env.user)

    employee_ids = fields.Many2many(
        'hr.employee', string='Employees', tracking=True)

    picking_ids = fields.Many2many(
        'stock.picking', string='Pickings', readonly=True)

    obs = fields.Text('Observations')

    state = fields.Selection(
        STATE, string='Status', index=True, readonly=True,
        tracking=True, default='draft', copy=False)

    product_ids = fields.One2many(
        'massive.product.line.list', 'product_deliver_id', string='Product list')

    type = fields.Selection(
        TYPE, string='Tipo', index=True, default='delivery', copy=False)
    company_id = fields.Many2one(comodel_name="res.company", string='Company', default=lambda self: self.env.company,
                                 required=True)

    def action_create_picking(self,location_id, location_dest, employee):
        """."""
        picking_ids = []
        moves = []

        for line in self.product_ids:
            if not line.product_id.is_activo and line.product_id.type in [
                    'consu', 'product']:
                moves.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_id.uom_id.id,
                    'name': line.product_id.name,
                    'quantity_done': line.qty,
                    'location_id': location_id.id,
                    'location_dest_id': location_dest.id,
                }))

            vals = {
                'product_id': line.product_id.id,
                'qty': line.qty,
            }
            product_line = self.env['product.line.list'].create(vals)
            product_line.write({
                'date': self.entry_date,
                'partner_id': employee.user_partner_id.id,
                'user_id': self.user_id.id,
                'employee_id': employee.id,
                'type': self.type,
                'cost': line.cost,
                'subtotal': line.subtotal,
                'state': 'done'
            })

        if moves:
            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'internal'),
                 ('default_location_src_id', '=', location_id.id)], limit=1)

            if not picking_type:
                raise UserError(
                    _('No internal type operation has been established for the location')%location_id.name)

            values = {
                'picking_type_id': picking_type.id,
                'origin': self.name,
                'move_ids': moves,
                'location_id': location_id.id or picking_type.location_id.id,
                'location_dest_id': location_dest.id or picking_type.location_dest_id.id,
                'partner_id': employee.user_partner_id.id,
                'company_id': self.company_id.id,
                'scheduled_date': self.entry_date.strftime('%Y-%m-%d')
            }
            picking = self.env['stock.picking'].create(values)
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()
            picking_ids.append(picking.id)

        return picking_ids

    def exe_cancel(self):
        """."""
        self.state = 'cancel'

    def exe_solicitado(self):
        """."""
        if not self.product_ids:
            raise UserError(_("You must add products."))
        if not self.employee_ids:
            raise UserError(_("You must add employees."))
        self.state = 'requested'

    def exe_aprobar(self):
        """."""
        if not self.product_ids:
            raise UserError(_("You must add products."))
        if not self.employee_ids:
            raise UserError(_("You must add employees."))
        self.state = 'approved'

    def exe_deliver(self):
        """."""
        picking_ids = []
        if not self.product_ids:
            raise UserError(_("You must add products."))
        if not self.employee_ids:
            raise UserError(_("You must add employees."))

        for employee in self.employee_ids:
            partner_id = employee.user_partner_id
            if not partner_id:
                # Create partner
                partner_id = self.env['res.partner'].create({
                        'name': employee.name,
                                                              })
                employee.user_partner_id = partner_id.id
                if not partner_id:
                    partner_id = self.env['res.partner'].create({
                        'name': employee.name,
                    })
                    employee.user_partner_id = partner_id.id
                    if not partner_id:
                        partner_id = self.env['res.partner'].create({
                            'name': employee.name,
                        })
                        employee.user_partner_id = partner_id.id
                        if not partner_id:
                            raise UserError(_("Employee %s has not home address defined") % employee.display_name)

            if self.type == 'delivery':
                ubication_deliver_dest_id = employee.epi_location_id
                ubication_deliver_id = self.company_id.ubication_deliver_id
                if not ubication_deliver_id:
                    ubication_deliver_dest_id = self.company_id.ubication_deliver_dest_id
                if not ubication_deliver_id or not ubication_deliver_dest_id:
                    raise UserError(_("You must configure the delivery location and the destination location"))

                if not ubication_deliver_id or not ubication_deliver_dest_id:
                    raise UserError(_("You must configure the delivery location and the destination location"))

                tmp = self.action_create_picking(ubication_deliver_id, ubication_deliver_dest_id, employee)
                picking_ids = picking_ids + tmp



        self.picking_ids = picking_ids
        self.state = 'done'

    def exe_return_draft(self):
        """."""
        self.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('massive.deliver.products') or 'New'
        return super().create(vals_list)

#
class ProductLineList(models.Model):
    """Product list"""

    _name = 'massive.product.line.list'
    _description = "Product list"
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='Product', domain="[('tool_ok', '=', True)]")
    qty = fields.Float('Quantity', default=1)
    cost = fields.Float('Cost')
    subtotal = fields.Float('Subtotal')
    product_deliver_id = fields.Many2one(
        'massive.deliver.products', string="Delivery",
        ondelete='cascade')
    checked = fields.Boolean('Select')
    retry = fields.Boolean('Withdrawn/Transferred')

    expiration_date = fields.Date('Due date', compute='_compute_giveme_expired')

    expiration_days = fields.Integer('Maturity Days', related='product_id.expiration_days')

    expired = fields.Boolean('Expired', compute='_compute_giveme_expired')

    note = fields.Char('Notes')
    company_id = fields.Many2one('res.company',related='product_deliver_id.company_id')

    @api.onchange('product_id')
    def _compute_giveme_expired(self):
        for record in self:
            if record.expiration_days != 0:
                if record.type == 'withdrawal':
                    record.expired = False
                else:
                    record.expiration_date = fields.Date.from_string(record.date) + timedelta(days=record.expiration_days)
                    today = date.today()
                    if today > record.expiration_date:
                        record.expired = True
                    else:
                        record.expired = False
            else:
                record.expired = True
                record.expiration_date = fields.Date.from_string(record.date) + timedelta(days=record.expiration_days)

    date = fields.Date(related='product_deliver_id.entry_date', store=True, readonly=True)

    type = fields.Selection(
        related='product_deliver_id.type',
        store=True, readonly=True)

    user_id = fields.Many2one('res.users', related='product_deliver_id.user_id', store=True, readonly=True)

    stock_product = fields.Float(related='product_id.qty_available', readonly=True)

    categ_id = fields.Many2one('product.category', related='product_id.product_tmpl_id.categ_id', store=True, readonly=True)
    state = fields.Selection(related='product_deliver_id.state')

    @api.onchange('product_id')
    def onchange_product_id(self):
        """."""
        self.cost = self.product_id.standard_price

    @api.onchange('qty', 'cost')
    def onchange_product_cost_id(self):
        """."""
        self.subtotal = self.qty * self.cost