#-*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError

TYPE = [
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer')]


class WizardDeliverProducts(models.TransientModel):
    """Wizard deliver products."""

    _name = 'wizard.deliver.products'
    _description = "Wizard deliver products"

    def _get_default_ids(self):
        """."""
        employee_id = self._context.get('active_id', False)
        delivereds = self.env['product.line.list'].search(
            [('employee_id', '=', employee_id), ('type', '!=', 'retiro')])
        list_ids = [deliver.id for deliver in delivereds if not deliver.retry]
        return [(6, 0, list_ids)]

    lines_ids = fields.Many2many(
        'product.line.list', 'many_location_rel',
        'many_id', 'product_line_id', 'Lines', default=_get_default_ids)
    employee_id = fields.Many2one('hr.employee', 'Employee')
    motive_id = fields.Many2one(
        'deliver.products.motive', 'Motive')
    obs_text = fields.Text('Observations')
    type = fields.Selection(TYPE, string='Type', default='withdrawal')

    def _get_default_to_show_ids(self):
        """."""
        list_ids = []
        employee_id = self._context.get('active_id', False)
        delivereds = self.env['product.line.list'].search(
            [('employee_id', '=', employee_id), ('type', '!=', 'withdrawal')])
        for line in delivereds:
            tmp = self.env['product.line.list.wizard'].create(
                {
                  'product_line_id': line.ids[0],
                  'product_id': line.product_id.name,
                  'qty': line.qty,
                  'cost': line.cost,
                  'subtotal': line.subtotal
                 })
            list_ids.append(tmp.id)
        return [(6, 0, list_ids)]

    lines_ids_to_show = fields.Many2many('product.line.list.wizard', default=_get_default_to_show_ids)

    @api.onchange('type')
    def _onchange_type(self):
        """."""
        self.employee_id = False
        if self.type == 'withdrawal':
            self.employee_id = self._context.get('active_id', False)

    @api.onchange('motive_id')
    def _onchange_motive_id(self):
        """."""
        if self.motive_id:
            self.obs_text = self.motive_id.obs

    def action_create_picking(self, location_id, location_dest):
        """."""
        moves = []
        for line in self.lines_ids_to_show:
            if not line.product_line_id.product_id.is_activo and line.product_line_id.product_id.type in ['consu', 'product']:
                if line.qty > line.product_line_id.qty:
                    raise UserError(_("Quantity to withdraw must be less than or equal to the quantity of products delivered to the employee."))
                else:
                    moves.append((0, 0, {
                        'product_id': line.product_line_id.product_id.id,
                        'product_uom_qty': line.qty,
                        'product_uom': line.product_line_id.product_id.uom_id.id,
                        'name': line.product_line_id.product_id.name,
                        'quantity_done': line.qty,
                        'location_id': location_id.id,
                       'location_dest_id': location_dest.id,
                    }))
        if moves:

            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'outgoing'),
                 ('default_location_src_id', '=', location_id.id)])

            if not picking_type:
                raise UserError(_("No internal operation type defined for location %s" % location_id.name))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'origin': self.employee_id.name,
                'move_ids': moves,
                'location_id': location_id.id,
                'location_dest_id': location_dest.id,
                'partner_id': self.employee_id.user_partner_id.id,
                'company_id': self.env.user.company_id.id,
                'scheduled_date': fields.Date.today().strftime('%Y-%m-%d'),
                'note': self.obs_text
            })

            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

    def create_deliver_product(self, retry):
        """."""
        entire_deliveries = []
        for line in self.lines_ids_to_show:
            if line.qty > line.product_line_id.qty:
                raise UserError(_("Quantity to withdraw must be less than or equal to the quantity of products delivered to the employee."))
            elif line.qty == line.product_line_id.qty:
                entire_deliveries.append(line.product_line_id.id)
                line.product_line_id.retry = retry
            else:
                vals={
                    'product_id': line.product_line_id.product_id.id,
                    'qty': line.qty,
                    'cost': line.cost,
                }
                tmp = self.env['product.line.list'].create(vals)
                entire_deliveries.append(tmp.id)
                line.product_line_id.qty = line.product_line_id.qty - line.qty
        self.env['deliver.products'].create({
            'employee_id': self.employee_id.id,
            'type': self.type,
            'product_ids': entire_deliveries,
            'obs': self.obs_text,
            'state': 'done'
        })

    def retry_product(self):
        """."""
        if not self.lines_ids_to_show:
            raise UserError(_("No products to retry."))

        if self.type != 'withdrawal':
            if self.employee_id.id == self._context.get('active_id', False):
                raise UserError(_("You can not transfer EPIs to same employee."))

            self.create_deliver_product(False)

        else:
            if not self.employee_id.user_partner_id:
                raise UserError(_("Employee must have a home address."))

            location_retry_id = self.env.user.company_id.ubication_retry_id
            if not location_retry_id:
                raise UserError(_("Withdrawal location not defined."))

            location_deliver_id = self.env.user.company_id.ubication_deliver_dest_id
            if not location_deliver_id:
                raise UserError(_("Delivery location not defined."))

            self.action_create_picking(
                location_deliver_id,
                location_retry_id)

            self.create_deliver_product(True)


class ProductLineListWizard(models.TransientModel):
    """Product list."""

    _name = 'product.line.list.wizard'
    _description = "Product list"
    _rec_name = 'product_id'

    product_line_id = fields.Many2one('product.line.list')
    product_id = fields.Char(string='Product')
    qty = fields.Float(string='Quantity')
    cost = fields.Float(string='Cost')
    subtotal = fields.Float(string='Subtotal', compute='onchange_product_cost_id')

    @api.onchange('qty', 'cost')
    def onchange_product_cost_id(self):
        """."""
        for record in self:
            record.subtotal = record.qty * record.cost