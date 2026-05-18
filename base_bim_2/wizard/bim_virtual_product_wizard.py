# coding: utf-8
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BimVirtualProductWizard(models.TransientModel):
    _name = 'bim.virtual.product.wizard'
    _description = 'Bim Virtual Product Wizard'


    name = fields.Char()
    name2 = fields.Char()
    reference = fields.Char()
    lines_ids = fields.One2many('bim.virtual.product.wizard.line', 'bim_virtual_product_wizard_line_id', 'Lines')
    attribute_ids = fields.One2many('bim.virtual.product.wizard.attribute.line', 'bim_virtual_product_wizard_line_id', 'Attribute Ids')
    calc = fields.Boolean('Calc')


    @api.model
    def default_get(self, fields):
        res = super(BimVirtualProductWizard, self).default_get(fields)
        res['concept_id'] = self._context.get('active_id', False)
        return res

    concept_id = fields.Many2one('bim.concepts', "Concept", required=True)


    def do_action(self):
        concept_obj = self.env['bim.concepts']
        concept_parent = concept_obj.browse(self._context['active_id'])

        if not self.lines_ids:
            raise ValidationError(_('No lines found'))


        lines_qty = self.lines_ids.filtered(lambda l: l.qty > 0)
        if not lines_qty:
            raise ValidationError(_('No lines found with qty > 0'))

        for line in self.lines_ids:
            product_id = self.env['product.product'].search([('resource_type', '=', 'P')], limit=1)
            if not product_id:
                raise ValidationError(_('No product found with resource_type = P Virtual Product'))

            if line.qty > 0 and product_id:
                # MATERIAL
                _name = line.name.product_id.name if line.name.product_id else line.name.name
                _code = line.name.product_id.default_code if line.name.product_id else line.name.reference
                _product_id = line.name.product_id if line.name.product_id else product_id

                bim_concept_new_id = self.env['bim.concepts'].create({
                    'name': _name,
                    'code': _code,
                    'virtual_product_id': line.name.id if not line.name.product_id else False,
                    'parent_id': concept_parent.id,
                    'type': 'material',
                    'budget_id': concept_parent.budget_id.id,
                    'product_id': _product_id.id,
                    'quantity': line.qty,
                    'amount_fixed' : line.name.product_id.standard_price if line.name.product_id else 0,
                    'uom_id': line.name.product_id.uom_id.id if line.name.product_id else False
                })



    # onchange name
    @api.onchange('calc')
    def onchange_name(self):
        for record in self:
            if record.attribute_ids:
                record.lines_ids.unlink()
                product_ids_per_attribute = []

                for attribute in record.attribute_ids:
                    virtual_product_line_ids = self.env['virtual.product.line'].search([
                        ('name', '=', attribute.name.id),
                        ('value_id', '=', attribute.value_id.id),
                    ]).mapped('virtual_id.id')  # Asumiendo que existe un campo 'product_id' en 'virtual.product.line'

                    if virtual_product_line_ids:
                        product_ids_per_attribute.append(set(virtual_product_line_ids))

                # Calcula la intersección de los conjuntos de IDs de productos
                common_product_ids = set.intersection(*product_ids_per_attribute) if product_ids_per_attribute else set()

                for product_id in common_product_ids:
                    record.lines_ids = [(0, 0, {'name': product_id})]

            else:
                if record.name and not record.reference:
                    domain = [('name', 'ilike', record.name)]
                elif record.reference and not record.name:
                    domain = [('reference', 'ilike', record.reference)]
                elif record.name and record.name2:
                    domain = [('name', 'ilike', record.name), ('name', 'ilike', record.name2)]
                elif record.reference and record.name:
                    domain = [('reference', 'ilike', record.reference), ('name', 'ilike', record.name)]
                else:
                    domain = [('name', '=', False)]

                virtual_product_ids = self.env['virtual.product'].search(domain)
                if virtual_product_ids:
                    lines = []
                    record.lines_ids.unlink()
                    for virtual_product in virtual_product_ids:
                        lines.append((0, 0, {'name': virtual_product.id, 'insert': False}))
                    record.lines_ids = lines


class BimVirtualProductWizardLine(models.TransientModel):
    _description = "Bim Virtual Product Wizard Line"
    _name = 'bim.virtual.product.wizard.line'

    name = fields.Many2one('virtual.product')
    reference = fields.Char(related='name.reference')
    pp = fields.Boolean(compute='_compute_pp')
    qty = fields.Float(string='qty', default=0)
    bim_virtual_product_wizard_line_id = fields.Many2one('bim.virtual.product.wizard', ondelete='cascade')

    @api.depends('name')
    def _compute_pp(self):
        for record in self:
            if record.name.product_id:
                record.pp = True
            else:
                record.pp = False


class BimVirtualProductWizardAttributeLine(models.TransientModel):
    _description = "Bim Virtual Product Wizard Attribute Line"
    _name = 'bim.virtual.product.wizard.attribute.line'

    name = fields.Many2one('bim.attribute', string='Attribute')
    value_id = fields.Many2one('bim.attribute.value',
                                string='Value')
    bim_virtual_product_wizard_line_id = fields.Many2one('bim.virtual.product.wizard', ondelete='cascade')
