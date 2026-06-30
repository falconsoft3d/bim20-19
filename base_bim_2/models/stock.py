# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from datetime import datetime
import logging
from odoo.exceptions import ValidationError, UserError
_logger = logging.getLogger(__name__)


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _create_returns(self):
        res = super()._create_returns()
        picking = self.env['stock.picking'].browse(res[0])
        if picking:
            picking.returned = True
        return res


class StockLocation(models.Model):
    _inherit = 'stock.location'
    bim_main_location = fields.Boolean(string="Main Location", default=lambda r: r.env.company.bim_main_location)




class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'
    code = fields.Char('Short Name', required=True, help="Short name used to identify your warehouse")


class StockMove(models.Model):
    _inherit = 'stock.move'
    supplier_id = fields.Many2one('res.partner')
    concept_phase_id = fields.Many2one('concept.phase', 'Phase')
    name_picking = fields.Char('Picking Name', related='picking_id.name')
    scheduled_date = fields.Datetime('Scheduled Date', related='picking_id.scheduled_date')
    state_picking = fields.Selection(related='picking_id.state', string='Estado')
    picking_type_code = fields.Selection(related='picking_id.picking_type_id.code', string='Tipo')

    bim_project_id = fields.Many2one('bim.project', 'BIM Project', domain="[('company_id','=',company_id)]")
    bim_budget_id = fields.Many2one('bim.budget', 'Budget', domain="[('project_id','=',bim_project_id)]")

    concept_id = fields.Many2one(
        'bim.concepts',
        string='Partida',
        domain="[('budget_id','=',bim_budget_id),('type','=','departure')]"
    )

    @api.onchange('bim_project_id')
    def _onchange_bim_project_id(self):
        for record in self:
            # asigno por defecto el primer presupuesto del proyecto
            bim_project_id  = self.env['bim.project'].browse(record.bim_project_id.id)
            if bim_project_id and bim_project_id.budget_ids:
                record.bim_budget_id = bim_project_id.budget_ids[0].id
            record.concept_id = False



class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    supplier_id = fields.Many2one('res.partner', related="move_id.supplier_id")



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    bim_requisition_id = fields.Many2one('bim.purchase.requisition','Requisition')
    bim_project_id = fields.Many2one('bim.project','Bim Project', domain="[('company_id','=',company_id)]")
    bim_budget_id = fields.Many2one('bim.budget', 'Budget', domain="[('project_id','=',bim_project_id)]")
    bim_concept_id = fields.Many2one('bim.concepts', 'Concept', domain="[('budget_id','=',bim_budget_id),('type','=','departure')]")
    bim_space_id = fields.Many2one('bim.budget.space','Space', domain="[('budget_id','=',bim_budget_id)]")
    bim_object_id = fields.Many2one('bim.object','BIM Object', domain="[('project_id','=',bim_project_id)]")
    bim_worder_id = fields.Many2one('bim.work.order', 'Work Order')
    check_to_rewrite = fields.Boolean('Overwrite destination')
    invoice_guide_number = fields.Char('Invoice Guide No.')
    include_for_bim = fields.Boolean('Include for BIM', default=False)
    returned = fields.Boolean(default=False)
    motive_id = fields.Many2one(
        'deliver.products.motive', string='Motivo', readonly=True)

    place_of_delivery_id = fields.Many2one('res.partner', 'Place of Delivery')
    external_reference = fields.Char('External Reference')

    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice',
        required=False)


    bim_purchase_id = fields.Many2one('purchase.order', 'Purchase Order')

    def action_include_bim(self):
        for picking in self:
            if not picking.include_for_bim:
                picking.include_for_bim = True
            else:
                picking.include_for_bim = False

    def bim_create_invoice(self):
        invoice_obj = self.env['account.move']

        if self.account_move_id:
            if self.account_move_id.state == 'draft':
                self.account_move_id.unlink()

        if not self.move_ids:
            raise UserError(_('No lines to invoice'))

        if not self.bim_project_id:
            raise UserError(_('No project selected'))

        if not self.bim_purchase_id:
            raise UserError(_('No purchase order selected'))

        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.purchase_id.partner_id.id,
            'purchase_id': self.bim_purchase_id.id,
            'currency_id': self.bim_purchase_id.currency_id.id,
            'company_id': self.bim_purchase_id.company_id.id,
            'include_for_bim': True,
            'project_id': self.bim_project_id.id,
            'date': self.scheduled_date,
            }

        invoice_line_ids = []

        for line in self.move_ids:
            if line.purchase_line_id:
                purchase_line_id = line.purchase_line_id
            else:
                purchase_line_ids = self.bim_purchase_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id)
                purchase_line_id = purchase_line_ids and purchase_line_ids[0] or False
            vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'product_uom_id': purchase_line_id.product_uom.id,
                    'price_unit': purchase_line_id.price_unit,
                    'tax_ids': purchase_line_id.taxes_id.ids,
                    'discount': purchase_line_id.discount,
                    'concept_phase_id': purchase_line_id.concept_phase_id.id,
                    'project_id': self.bim_project_id.id,
                    'budget_id': self.bim_budget_id.id,
                    'concept_id': self.bim_purchase_id.concept_id.id,
                    'purchase_line_id': purchase_line_id.id,
                }

            analytic_id = self.bim_project_id.analytic_id.id and self.bim_project_id.analytic_id.id or False
            if analytic_id:
                    vals.update({
                        'analytic_distribution': {'%s' % (analytic_id): 100}
                    })
            invoice_line_ids.append((0, 0, vals))

        invoice_vals.update({'invoice_line_ids': invoice_line_ids})
        invoice = invoice_obj.create(invoice_vals)


        if invoice:
            self.account_move_id = invoice.id


        # mostrar la factura
        return {
            'name': _('Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }



    def button_validate(self):
        res = super().button_validate()
        if self.bim_project_id:
            self.bim_project_id.update_project_cost()

        for picking in self:
            if picking.bim_project_id:
                closing_expenses_id = self.env['closing.expenses'].search([
                    ('project_ids', 'in', self.bim_project_id.id),
                    ('state', '=', 'closed'),
                    ('date_closing', '>=', self.scheduled_date.date())
                ], limit=1)

                if closing_expenses_id:
                    raise ValidationError(
                        _('There is a closed closing expenses for this project after the done date of this document Please review.'))

        return res

    @api.constrains('picking_type_id')
    def _check_picking_type_bim(self):
        for picking in self:
            if picking.picking_type_id.code == 'incoming':
                include_for_bim_in = self.env['ir.config_parameter'].sudo().get_param('stock.picking.in')

                if include_for_bim_in == 'True':
                    picking.include_for_bim = True
                else:
                    picking.include_for_bim = False

            if picking.picking_type_id.code == 'outgoing':
                include_for_bim_out = self.env['ir.config_parameter'].sudo().get_param('stock.picking.out')

                if include_for_bim_out == 'True':
                    picking.include_for_bim = True
                else:
                    picking.include_for_bim = False



    @api.onchange('bim_requisition_id')
    def bim_req_change(self):
        new_lines = self.env['stock.move']
        self.move_ids = False
        req = self.bim_requisition_id
        for line in req.product_ids:
            if not line.done :
                new_line = new_lines.new({
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'product_uom_qty': line.despachado if not line.company_id.picking_move_all else line.quant,
                    'quantity_done': 0 if not line.company_id.picking_move_all else line.quant,
                    'date': req.date_begin,
                    'forecast_expected_date': req.date_prevista and req.date_prevista or datetime.today(),
                    'state': 'draft',
                    'price_unit': line.product_id.standard_price,
                    'picking_type_id': self.picking_type_id.id,
                    'origin': req.name,
                    'location_id': self.picking_type_id.default_location_src_id and self.picking_type_id.default_location_src_id.id or False,
                    'location_dest_id': req.project_id.stock_location_id and req.project_id.stock_location_id.id or False,
                    'warehouse_id': self.picking_type_id and self.picking_type_id.warehouse_id.id or False,
                })
                new_lines += new_line
        self.move_ids += new_lines
        return {}

    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type(self):
        if self.bim_requisition_id:
            self.location_dest_id = self.bim_requisition_id.project_id.stock_location_id \
                and self.bim_requisition_id.project_id.stock_location_id.id or False

    def action_force_assign(self):
        for picking in self:
            for move in picking.move_ids:
                if move.product_uom_qty != move.product_uom_qty:
                    move.product_uom_qty = move.product_uom_qty
        return True

    @api.onchange('bim_project_id')
    def _onchange_bim_project_id(self):
        for record in self:
            record.bim_budget_id = False
            record.bim_concept_id = False

    @api.onchange('bim_budget_id')
    def _onchange_bim_budget_id_id(self):
        for record in self:
            record.bim_concept_id = False

    @api.constrains('include_for_bim')
    def _check_include_for_bim(self):
        for picking in self:
            if picking.include_for_bim and picking.bim_budget_id and not picking.bim_budget_id.state_id.material_request:
                raise UserError(
                    _("It is not possible to include this Transfer in BIM if it's Budget State doesn't allow Material Request"))


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    resource_type = fields.Selection(related='product_tmpl_id.resource_type', string="Resource Type", store=True)



