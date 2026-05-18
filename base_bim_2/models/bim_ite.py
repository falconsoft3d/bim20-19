# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimIte(models.Model):
    _description = "Bim ITE"
    _name = 'bim.ite'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code')
    desc = fields.Char('Description')
    obs = fields.Text('Notes', default="")
    val_n = fields.Float("N", digits="BIM qty")
    val_x = fields.Float("X", digits="BIM qty")
    val_y = fields.Float("Y", digits="BIM qty")
    val_z = fields.Float("Z", digits="BIM qty")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    amount = fields.Float('Total', compute='_compute_amount', digits='BIM price')
    image = fields.Image("Image ITE", max_width=1920, max_height=1920)
    line_ids = fields.One2many(comodel_name="bim.ite.line", inverse_name="ite_ide", string="Lines", copy=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.ite') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(x.amount for x in record.line_ids if (x.type=='product' and not x.parent_id) or x.type == 'concept')

    @api.onchange('line_ids')
    def onchange_set_lines(self):
        if self.line_ids:
            line_parent = False
            for line in self.line_ids:
                if line.type == 'concept':
                    line_parent = line.id
                else:
                    line.parent_id = line_parent

                if line.sequence == 0:
                    line.sequence = len(self.line_ids)

    def name_get(self):
        res = super(BimIte, self).name_get()
        result = []
        for element in res:
            project_id = element[0]
            cod = self.browse(project_id).name
            desc = self.browse(project_id).desc
            name = cod and '[%s] %s' % (cod, desc) or '%s' % desc
            result.append((project_id, name))
        return result


class BimIteLine(models.Model):
    _name = 'bim.ite.line'
    _description = 'ITE Lines'
    _order = 'sequence'

    code = fields.Char("Code")
    name = fields.Char("Descripction")
    #concept = fields.Char("Concept")
    sequence = fields.Integer(string='Sequence',required=True, default=0)
    formula = fields.Char("Formulas / Value")
    product_id = fields.Many2one(comodel_name="product.product", string="Product")
    price = fields.Float("Price", digits='BIM price')
    amount = fields.Float('Balance', help="Balance", compute='_compute_amount', digits='BIM price')
    qty_calc = fields.Float('Quantity', help="Quantity", compute='_compute_quantity', digits='BIM qty')
    ite_ide = fields.Many2one(comodel_name="bim.ite", string="Bim Ite")
    product_uom = fields.Many2one('uom.uom', string='UdM')
    parent_id = fields.Many2one('bim.ite.line', string='Parent', compute='_compute_parent')
    children_ids = fields.One2many(string="Child Lines", comodel_name='bim.ite.line', inverse_name='parent_id')
    type = fields.Selection([
        ('product','Product'),
        ('concept','Budget Item')],
        string='Type')

    @api.onchange('name')
    def _onchange_name(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id
            self.price = self.product_id.standard_price

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.name = self.product_id.name
        if self.product_id.default_code:
            self.code = self.product_id.default_code
        else:
            self.code = "00"

    @api.depends('type', 'ite_ide')
    def _compute_parent(self):
        for record in self:
            lines_parent = record.ite_ide.line_ids.filtered(lambda l: l.type == 'concept')
            if record.type == 'product':
                list_res = []
                for parent in lines_parent:
                    if parent.sequence < record.sequence:
                        tuple_vals = (parent.sequence, parent.id)
                        list_res.append(tuple_vals)
                if list_res:
                    list_res.sort(key=lambda tup: tup[0],reverse=True)
                    record.parent_id = list_res[0][1]
                else:
                    record.parent_id = False
            else:
                record.parent_id = False

    @api.depends('price', 'formula', 'ite_ide')
    def _compute_quantity(self):
        for record in self:
            if record.formula:
                try:
                    N = n = record.ite_ide.val_n
                    X = x = record.ite_ide.val_x
                    Y = y = record.ite_ide.val_y
                    Z = z = record.ite_ide.val_z
                    record.qty_calc = eval(str(record.formula).replace(',','.'))
                except:
                    raise UserError(_('Define a formula based on the ITE description. Division by zero is not allowed'))
            else:
                record.qty_calc = 1

    @api.depends('price', 'type', 'ite_ide','sequence','qty_calc')
    def _compute_amount(self):
        for record in self:
            if record.type == 'concept':
                price = sum(line.price*line.qty_calc for line in self.ite_ide.line_ids if record.sequence < line.sequence and line.parent_id.id == record.id)
                record.price = price
                record.amount = record.qty_calc * price
            else:
                record.amount = record.price * record.qty_calc


