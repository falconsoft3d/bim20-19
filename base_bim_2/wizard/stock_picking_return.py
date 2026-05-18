# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_round

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'


    def create_returns(self):
        res = super(ReturnPicking, self).create_returns()
        for wizard in self:
            new_picking_id = res.get('res_id')
            if 'project_id' in wizard.picking_id:
                new_picking = self.env['stock.picking'].browse(new_picking_id)
                new_picking.write(
                            {
                                'project_id': wizard.project_id.id,
                                'include_for_bim' : True if wizard.picking_id.include_for_bim else False,
                                'bim_space_id' : wizard.picking_id.bim_space_id.id,
                                'supplier_reference' : wizard.picking_id.supplier_reference,
                            }
                        )
        return res