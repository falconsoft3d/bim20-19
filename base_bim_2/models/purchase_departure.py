# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class PurchaseDeparture(models.Model):
    _description = "Purchase Departure"
    _name = 'purchase.departure'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Code', required=True,
    readonly=True, copy=False, index=True,
    default=lambda self: self.env['ir.sequence'].next_by_code('purchase.departure'))

    project_id = fields.Many2one('bim.project', 'Project', ondelete="cascade")
    budget_id = fields.Many2one('bim.budget', 'Budget', ondelete="cascade")

    user_id = fields.Many2one('res.users', string='Created', default=lambda self: self.env.user)
    create_date = fields.Datetime('Creation Date', default=fields.Datetime.now, readonly=True)

    purchase_departure_line_ids = fields.One2many('purchase.departure.line', 'departure_id', 'Departure Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel')],
        string='Status', index=True, readonly=True, default='draft', copy=False)


    type = fields.Selection([
        ('labor', 'Labor'),
        ('equip', 'Equipment'),
        ('material', 'Material'),
        ('ALL', 'All'),],
        string='Type', index=True, required=True, default='material', copy=False)


    def exe_done(self):
        self.purchase_departure_line_ids.filtered(lambda x: not x.purchase_id).unlink()
        for rec in self:

            concept_ids = self.env['bim.concepts'].search([
                ('budget_id', '=', rec.budget_id.id)], order='code desc')

            for concept in concept_ids:
                if concept.type == 'departure':
                    self.env['purchase.departure.line'].create({
                                        'concept_id': concept.id,
                                        'old_id' : concept.id,
                                        'departure_id': rec.id,
                                    })
            rec.state = 'done'


    def exe_draft(self):
        for rec in self:
            rec.state = 'draft'


class PurchaseDepartureLine(models.Model):
    _description = "Purchase Departure Line"
    _name = 'purchase.departure.line'
    _order = 'id desc'

    departure_id = fields.Many2one('purchase.departure', 'Departure', ondelete="cascade")
    concept_id = fields.Many2one('bim.concepts', 'Concept', ondelete="cascade")
    purchase_id = fields.Many2one('purchase.order', 'Purchase', ondelete="cascade")
    purchases_ids = fields.Many2many('purchase.order', string='Purchases')
    old_id = fields.Integer('Old ID')
    amount_total = fields.Float('Total')
    partner_id = fields.Many2one('res.partner', 'Supplier')
    purchase = fields.Boolean('For Purchase', default=False)


    def exe_purchase(self):
        for rec in self:
            # Si no tenemos el partner fijado
            if not rec.partner_id:
                rec.purchases_ids = False
                concept_ids = self.env['bim.concepts'].search([
                    ('parent_id', '=', rec.concept_id.id)], order='id desc')

                # Si facturamos por tipo.
                if rec.departure_id.type != 'ALL':
                    array_data = []
                    for concept in concept_ids:
                        if concept.type == rec.departure_id.type:

                            partner_id = self.env.user.company_id.partner_id




                            price = concept.amount_fixed
                            product_tmpl_id = concept.product_id.product_tmpl_id
                            product_supplierinfo_ids = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id.id)], limit=1)

                            if product_supplierinfo_ids:
                                price = product_supplierinfo_ids.price
                                partner_id = product_supplierinfo_ids.partner_id


                            # Agregamos el partner y el producto a la lista
                            # Si el partner y producto no existe en la lista
                            if not any(d['partner_id'] == partner_id.id and d['product_id'] == concept.product_id.id for d in array_data):
                                array_data.append({'partner_id': partner_id.id, 'product_id': concept.product_id.id, 'price_unit': price, 'product_qty': concept.quantity * concept.parent_id.quantity, 'product_uom': concept.uom_id.id})

                            # Si el partner y producto existe en la lista
                            else:
                                for data in array_data:
                                    if data['partner_id'] == partner_id.id and data['product_id'] == concept.product_id.id:
                                        data['product_qty'] += concept.quantity * concept.parent_id.quantity
                                        break

                    print("1---------------------------------")
                    print("array_data")
                    print(array_data)
                    print("2---------------------------------")

                    # Agrupamos por partner_id

                    provider_ids = []
                    for data in array_data:
                        if data['partner_id'] not in provider_ids:
                            provider_ids.append(data['partner_id'])

                    print("3---------------------------------")
                    print("provider_ids")
                    print(provider_ids)

                    for provider_id in provider_ids:
                        purchase_id = self.env['purchase.order'].create({
                            'partner_id': provider_id,
                            'project_id': rec.departure_id.project_id.id,
                            'budget_id': rec.departure_id.budget_id.id,
                            'date_order': fields.Datetime.now()})
                        rec.purchases_ids = [(4, purchase_id.id)]

                        # Recorremos la lista para insertar los productos
                        for data in array_data:
                            if data['partner_id'] == provider_id:
                                self.env['purchase.order.line'].create({
                                    'order_id': purchase_id.id,
                                    'product_id': data['product_id'],
                                    'name': concept.name,
                                    'product_qty': data['product_qty'],
                                    'price_unit': data['price_unit'],
                                    'product_uom': data['product_uom'],
                                })
                else:
                    for concept in concept_ids:
                        partner_id = self.env.user.company_id.partner_id
                        purchase_id = self.env['purchase.order'].create({
                            'partner_id': partner_id.id,
                            'project_id': rec.departure_id.project_id.id,
                            'budget_id': rec.departure_id.budget_id.id,
                            'date_order': fields.Datetime.now()})

                        rec.purchases_ids = [(4, purchase_id.id)]

                        price = concept.product_id.product_tmpl_id.standard_price
                        product_tmpl_id = concept.product_id.product_tmpl_id
                        product_supplierinfo_ids = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id.id)], limit=1)

                        if product_supplierinfo_ids:
                            price = product_supplierinfo_ids.price
                            partner_id = product_supplierinfo_ids.partner_id
                            purchase_id.partner_id = partner_id.id

                        self.env['purchase.order.line'].create({
                                    'order_id': purchase_id.id,
                                    'product_id': concept.product_id.id,
                                    'name': concept.name,
                                    'product_qty': concept.quantity * concept.parent_id.quantity,
                                    'price_unit': price,
                                    'product_uom': concept.uom_id.id,
                                })


                rec.amount_total = sum(rec.purchases_ids.mapped('amount_total'))
                rec.purchase = True
            else:
                partner_id = rec.partner_id
                purchase_id = self.env['purchase.order'].create({
                'partner_id': partner_id.id,
                'project_id': rec.departure_id.project_id.id,
                'budget_id': rec.departure_id.budget_id.id,
                'date_order': fields.Datetime.now()})

                concept_ids = self.env['bim.concepts'].search([
                    ('parent_id', '=', rec.concept_id.id)], order='id desc')

                if concept_ids:
                    for concept in concept_ids:
                        if rec.departure_id.type != 'ALL':
                            if concept.type == rec.departure_id.type:
                                price = concept.product_id.product_tmpl_id.standard_price
                                product_tmpl_id = concept.product_id.product_tmpl_id
                                product_supplierinfo_ids = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id.id),
                                    ('partner_id', '=', partner_id.id )], limit=1)

                                if product_supplierinfo_ids:
                                    price = product_supplierinfo_ids.price

                                self.env['purchase.order.line'].create({
                                        'order_id': purchase_id.id,
                                        'product_id': concept.product_id.id,
                                        'name': concept.name,
                                        'product_qty': concept.quantity * concept.parent_id.quantity,
                                        'price_unit': price,
                                        'product_uom': concept.uom_id.id,
                                    })
                        else:
                            if concept.type == departure_id.type:
                                price = concept.price
                                product_tmpl_id = concept.product_id.product_tmpl_id
                                product_supplierinfo_ids = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id.id),
                                    ('partner_id', '=', partner_id.id )], limit=1)
                                if product_supplierinfo_ids:
                                    price = product_supplierinfo_ids.price

                                self.env['purchase.order.line'].create({
                                    'order_id': rec.purchase_id.id,
                                    'product_id': concept.product_id.id,
                                    'name': concept.name,
                                    'product_qty': 1,
                                    'price_unit': price,
                                    'product_uom': concept.uom_id.id,
                                })
                rec.purchases_ids = [(4, purchase_id.id)]
                rec.amount_total = sum(rec.purchases_ids.mapped('amount_total'))
                rec.purchase = True