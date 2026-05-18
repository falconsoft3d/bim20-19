# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
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


class DeliverProductsMotive(models.Model):
    """Deliver Products Motive."""

    _name = 'deliver.products.motive'
    _description = 'Deliver Products Motive'

    name = fields.Char('Motive', copy=False)
    obs = fields.Text('Description')


class DeliverProducts(models.Model):
    """Deliver Products."""

    _name = 'deliver.products'
    _description = 'Deliver Products'
    _inherit = "mail.thread"
    _order = 'id desc'

    name = fields.Char(
        'Deliver Products',
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))

    entry_date = fields.Date('Date', default=fields.Date.today)

    user_id = fields.Many2one(
        'res.users', string='User', tracking=True,
        default=lambda self: self.env.user)

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', tracking=True)

    from_employee_id = fields.Many2one(
        'hr.employee', string='From employee', tracking=True)

    picking_id = fields.Many2one(
        'stock.picking', string='Picking')

    obs = fields.Text('Observations')

    state = fields.Selection(
        STATE, string='Status', index=True, readonly=True,
        tracking=True, default='draft', copy=False)

    product_ids = fields.One2many(
        'product.line.list', 'product_deliver_id', string='Products')
    company_id = fields.Many2one(comodel_name="res.company", string='Company', default=lambda self: self.env.company,
                                 required=True)

    type = fields.Selection(
        TYPE, string='Tipo', index=True, default='delivery', copy=False)

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

    def action_create_picking(self,location_id, location_dest):
        """."""
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

        if moves:

            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'internal'),
                 ('default_location_src_id', '=', location_id.id)], limit=1)

            if not picking_type:
                raise UserError(
                    _('No internal type operation has been established for the location %s') % location_id.name)

            values = {
                'picking_type_id': picking_type.id,
                'origin': self.name,
                'move_ids': moves,
                'location_id': location_id.id,
                'location_dest_id': location_dest.id,
                'partner_id': self.employee_id.user_partner_id.id,
                'company_id': self.company_id.id,
                'scheduled_date': self.entry_date.strftime('%Y-%m-%d')
            }
            picking = self.env['stock.picking'].create(values)
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()
            self.picking_id = picking.id

    def exe_cancel(self):
        """."""
        self.state = 'cancel'

    def exe_solicitado(self):
        """."""
        self.state = 'requested'

    def exe_aprobar(self):
        """."""
        if not self.product_ids:
            raise UserError(_('You must add products.'))
        self.state = 'approved'

    def exe_deliver(self):
        """."""
        if not self.product_ids:
            raise UserError(_('You must add products.'))

        partner_id = self.employee_id.user_partner_id
        if not partner_id:
            partner_id = self.env['res.partner'].create({
                'name': self.employee_id.name,
            })
            self.employee_id.user_partner_id = partner_id.id
            if not partner_id:
                raise UserError(_("Employee %s has not home address defined") % self.employee_id.display_name)
        ubication_deliver_dest_id = self.employee_id.epi_location_id
        ubication_deliver_id = self.company_id.ubication_deliver_id
        if not ubication_deliver_id:
            ubication_deliver_dest_id = self.company_id.ubication_deliver_dest_id
        if not ubication_deliver_id or not ubication_deliver_dest_id:
            raise UserError(_("You must configure the delivery location and the destination location"))

        if self.type == 'delivery':
            self.action_create_picking(ubication_deliver_id, ubication_deliver_dest_id)
        if self.type == 'withdrawal':
            self.action_create_picking( ubication_deliver_dest_id,ubication_deliver_id)
        if self.type == 'transfer':
            ubication_deliver_id = self.from_employee_id.epi_location_id
            ubication_deliver_dest_id = self.employee_id.epi_location_id
            if ubication_deliver_id and ubication_deliver_dest_id and ubication_deliver_id != ubication_deliver_dest_id:
                self.action_create_picking(ubication_deliver_id, ubication_deliver_dest_id)
        self.state = 'done'

    def exe_return_draft(self):
        """."""
        self.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('deliver.products') or 'New'
        return super().create(vals_list)


class ProductLineList(models.Model):
    """Product List."""

    _name = 'product.line.list'
    _description = "Product Line List"
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='Product', domain="[('tool_ok', '=', True)]")
    qty = fields.Float('Quantity', default=1)
    cost = fields.Float('Cost')
    subtotal = fields.Float('Subtotal', compute='onchange_product_cost_id')
    product_deliver_id = fields.Many2one(
        'deliver.products', string="Delivery",
        ondelete='cascade')
    checked = fields.Boolean('Select')
    retry = fields.Boolean('Withdrawn/Transferred')

    expiration_date = fields.Date('Due date', compute='_compute_giveme_expired')

    expiration_days = fields.Integer('Maturity Days', related='product_id.expiration_days')

    expired = fields.Boolean('Expired', compute='_compute_giveme_expired')

    note = fields.Char('Notes')
    state = fields.Selection(related='product_deliver_id.state', store=True,readonly=True, copy=False)
    company_id = fields.Many2one('res.company', related='product_deliver_id.company_id')

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

    employee_id = fields.Many2one(
        'hr.employee', related='product_deliver_id.employee_id', store=True, readonly=True)

    partner_id = fields.Many2one(
        'res.partner', related='product_deliver_id.employee_id.user_partner_id', store=True, readonly=True)

    date = fields.Date(related='product_deliver_id.entry_date', store=True, readonly=True)

    type = fields.Selection(
        related='product_deliver_id.type',
        store=True, readonly=True)

    user_id = fields.Many2one('res.users', related='product_deliver_id.user_id', store=True, readonly=True)

    stock_product = fields.Float(related='product_id.qty_available', readonly=True)

    categ_id = fields.Many2one('product.category', related='product_id.product_tmpl_id.categ_id', store=True, readonly=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        """."""
        self.cost = self.product_id.standard_price

    @api.onchange('qty', 'cost')
    def onchange_product_cost_id(self):
        """."""
        for record in self:
            record.subtotal = record.qty * record.cost

