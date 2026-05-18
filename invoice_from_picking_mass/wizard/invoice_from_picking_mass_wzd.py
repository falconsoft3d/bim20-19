# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class InvoiceFromPickingMassWzd(models.TransientModel):
    _name = 'invoice.from.picking.mass.wzd'
    _description = 'Wizard Invoice From Picking'

    type = fields.Selection([
        ('purchase', 'Compra'),
        ('sale', 'Venta'),
    ], 'Tipo', default='purchase')

    @api.model
    def default_get(self, fields_list):
        res = super(InvoiceFromPickingMassWzd, self).default_get(fields_list)
        picking_obj = self.env['stock.picking']
        pickings = self._context.get('active_ids', [])
        results = []
        for id in pickings:
            picking = picking_obj.search([('id', '=', id)])
            results.append(id)
        res.update({
            'picking_ids': results
        })
        return res

    picking_ids = fields.Many2many('stock.picking', string='Pickings')

    def action_create_ifpm(self):
        _logger.info('Begin = action_create_ifpm')
        ifpm_obj = self.env['invoice.from.picking.mass']
        lines = []


        for picking in self.picking_ids:
            _logger.info('El picking es %s y su estado es %s' % (picking.name, picking.state))
            if picking.state != 'done':
                raise UserError(_('The Albaran %s no esta validado') % (picking.name))

        for picking in self.picking_ids:
            line = {
                'picking_id': picking.id,
                'partner_id': picking.partner_id.parent_id.id if picking.partner_id.parent_id else picking.partner_id.id,
                'date': picking.scheduled_date,
                'origin': picking.origin,
            }
            lines.append([0, 0, line])

        vals = {
            'type': self.type,
            'date_to_invoice': fields.Datetime.now(),
            'invoicefrompicking_line_ids': lines
        }


        purchase_ifpm = ifpm_obj.create(vals)
        lines = []


        """
        for picking in self.picking_ids:
            line = {
                'picking_id': picking.id,
                'partner_id': picking.partner_id.parent_id.id if picking.partner_id.parent_id else picking.partner_id.id,
                'date': picking.scheduled_date,
                'origin': picking.origin,
            }
            lines.append([0, 0, line])

        vals = {
            'type': self.type,
            'date_to_invoice': fields.datetime.today(),
            'invoicefrompicking_line_ids': lines
        }

        _logger.info(vals)

        sale_ifpm = ifpm_obj.create(vals)
        """


        action = {
            'name': _('%s' % purchase_ifpm.name),
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.from.picking.mass',
            'view_mode': 'form',
            'res_id': purchase_ifpm.id,
        }

        _logger.info('End = action_create_ifpm')
        return action