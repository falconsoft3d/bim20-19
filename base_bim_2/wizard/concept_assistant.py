# coding: utf-8
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConceptAssistant(models.TransientModel):
    _name = 'concept.assistant'
    _description = 'Concept Assistant'


    concept_id = fields.Many2one('bim.concepts', "Concept", required=True)
    line_ids = fields.One2many('concept.assistant.line', 'assistant_id', "Lines")

    @api.model
    def default_get(self, fields):
        res = super(ConceptAssistant, self).default_get(fields)
        res['concept_id'] = self._context.get('active_id', False)
        return res


    def do_execute(self):
        for line in self.line_ids:
            if line.type == 'M':
                resource_type = 'M'
                type = 'product'
                _c_type = 'material'
            elif line.type == 'H':
                resource_type = 'H'
                type = 'service'
                _c_type = 'labor'
            elif line.type == 'Q':
                resource_type = 'Q'
                type = 'equip'
                _c_type = 'labor'
            elif line.type == 'S':
                resource_type = 'S'
                type = 'service'
                _c_type = 'subcontract'

            if not line.product_id:
                product_id = self.env['product.product'].create({
                    'name': line.description,
                    'default_code': line.code,
                    'standard_price': line.cost,
                    'resource_type': resource_type,
                    'type': type,
                })

                line.product_id = product_id

            vals = {
                'parent_id': self.concept_id.id,
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'amount_fixed': line.cost,
                'code': line.code or line.product_id.default_code or line.product_id.id,
                'name': line.description,
                'type': _c_type,
                'budget_id': self.concept_id.budget_id.id,
                'uom_id': line.product_id.uom_id.id,
            }

            self.env['bim.concepts'].create(vals)


class ConceptAssistantLine(models.TransientModel):
    _name = 'concept.assistant.line'
    _description = 'Concept Assistant Line'

    assistant_id = fields.Many2one('concept.assistant', "Assistant")

    type = fields.Selection([
        ('H', 'Mano de Obra'),
        ('Q', 'Equipo'),
        ('M', 'Material'),
        ('S', 'Subcontrato'),
    ], string='Type', required=True, default='M')

    code = fields.Char("Code")
    description = fields.Char("Description")
    uom = fields.Char("UOM")
    quantity = fields.Float("Quantity")
    cost = fields.Float("Cost")
    product_id = fields.Many2one('product.product', "Product")
    total = fields.Float("Total", compute='_compute_total', store=True)

    @api.depends('quantity', 'cost')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.quantity * rec.cost

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.code = self.product_id.default_code
            self.description = self.product_id.name
            self.uom = self.product_id.uom_id.name
            self.cost = self.product_id.standard_price
        else:
            self.code = False
            self.description = False
            self.uom = False
            self.cost = 0.0


    @api.onchange('code')
    def _onchange_code(self):
        if self.code and not self.product_id:
            product_id = self.env['product.product'].search([('default_code', '=', self.code)], limit=1)
            if product_id:
                self.product_id = product_id
                self.description = product_id.name
                self.uom = product_id.uom_id.name
                self.cost = product_id.standard_price

                if product_id.resource_type == 'M':
                    self.type = 'M'
                elif product_id.resource_type == 'H':
                    self.type = 'H'
                elif product_id.resource_type == 'Q':
                    self.type = 'Q'
                elif product_id.resource_type == 'S':
                    self.type = 'S'

            else:
                self.product_id = False
                self.description = False
                self.uom = False
                self.cost = 0.0