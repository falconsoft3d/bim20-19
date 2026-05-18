# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    invoicefrompicking_id = fields.Many2one('invoice.from.picking.mass', 'Facturado desde', copy=False)
    picking_id = fields.Many2one('stock.picking', 'Albarán', copy=False)
    picking_origin = fields.Char('Picking Origin', compute='_giveme_origin', store=False, copy=False)

    # Si elimino la factura paso sus albaranes a to_invoice
    def unlink(self):
        for record in self:
            if record.invoicefrompicking_id:
                record.invoicefrompicking_id.state = 'deleted'
                for line in record.invoicefrompicking_id.invoicefrompicking_line_ids:
                    line.picking_id.state_invoice = 'to_invoice'
        return super().unlink()


    # action_post
    def action_post(self):
        _logger.info("invoice_from_picking_mass / action_post")
        res = super().action_post()
        for rec in self:
            if rec.invoice_line_ids:
                for line in rec.invoice_line_ids:

                    if line.picking_id:
                        _logger.info("picking_id: %s", line.picking_id.name)
                        _logger.info("line_picking_id: %s", line.line_picking_id)

                        line.line_picking_id.product_cost = line.price_unit
                        line.line_picking_id.compute_subtotal()
        return res


    @api.depends('invoicefrompicking_id', 'invoicefrompicking_id.invoicefrompicking_line_ids')
    def _giveme_origin(self):
        for record in self:
            picking_origin = ""
            if record.invoicefrompicking_id:
                for line in record.invoicefrompicking_id.invoicefrompicking_line_ids:
                    picking_origin += line.picking_id.name + ", "
            else:
                picking_origin = '-'

            record.picking_origin = picking_origin[:-2]



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    picking_id = fields.Many2one('stock.picking', 'Albarán')
    line_picking_id = fields.Many2one('stock.move', 'Linea Albarán')