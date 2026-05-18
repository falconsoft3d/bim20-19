# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)
from  datetime import date


class ApuProductTemplate(models.Model):
    _inherit = 'product.template'

    resource_type = fields.Selection(
        [
          ('M', 'Material'),
          ('H', 'Labor'),
          ('Q', 'Equipment'),
          ('A', 'Administrative'),
          ('S', 'Subcontract'),
          ('P', 'Virtual Template')
         ],
        'Resourse Type', default='M')
    social_law = fields.Boolean('Social Law')
    last_sec = fields.Integer("Last sec reg")
    document_ids = fields.One2many('product.document.line', 'product_id', string='Line Documents')
    change_ids = fields.One2many('product.change.line', 'product_id', string='Changes')
    id_bim = fields.Char("BIM ID")
    bim_purchase_ids = fields.One2many('bim.product.purchase', 'template_id')
    ite_id = fields.Many2one('bim.ite', string="ITE")
    sub_contract = fields.Boolean(string='Subcontract')
    bim_group_id = fields.Many2one('bim.product.group', ondelete='restrict')
    cost_usd = fields.Float('Cost USD ($)', digits="BIM price")
    last_currency_update = fields.Date()
    tool_ok = fields.Boolean(default=False, string='Is Tool')
    tool_cost = fields.Float('Tool Cost')
    deprecation_days = fields.Integer()
    bim_check_uom = fields.Boolean(default=True, string='Check UOM')
    is_activo = fields.Boolean('Is asset')
    expiration_days = fields.Integer('Maturity Days')
    depreciation = fields.Float(default=1.0, digits=(10, 6))
    bonus = fields.Float(default=1.0)
    virtual_product_id = fields.Many2one('virtual.product', string='Virtual Product')
    rubro_id = fields.Many2one('bim.rubro', string='Rubro')
    srubro_id = fields.Many2one('bim.rubro', string='Subrubro', domain="[('parent_id','=',rubro_id)]")



    def action_update_cost_usd(self,templates=False):
        if not templates:
            products_usd_prices = self.search([('cost_usd','!=',0)])
        else:
            products_usd_prices = templates
        exchange_rate = self.env['res.currency.rate'].search(
            ['|', ('currency_id.name', '=', 'USD'), ('currency_id.symbol', '=', '$'),('rate', '!=', 0)], order='name desc', limit=1)
        if products_usd_prices and exchange_rate:
            for product in products_usd_prices:
                formula = '%s %s %s' % (str(product.cost_usd), exchange_rate.exchange_operator, str(exchange_rate.rate))
                product.with_company(self.env.company).standard_price = eval(formula)

    def cron_update_product_currency(self,limit=1000):
        _logger.info(':::STARTING PRODUCT USD CURRENCY UPDATE')
        templates = self.search([('last_currency_update','!=',date.today()),('cost_usd','!=',0)],limit=limit)
        if templates:
            _logger.info(':::UPDATING %s PRODUCTS'%str(len(templates)))
            templates.action_update_cost_usd()
            templates.write({'last_currency_update': date.today()})
        _logger.info(':::FINISHING PRODUCT USD CURRENCY UPDATE')

    @api.onchange('cost_usd')
    def onchange_cost_usd(self):
        if self.cost_usd:
            exchange_rate = self.env['res.currency.rate'].search(['|',('currency_id.name','=','USD'),('currency_id.symbol','=','$'),
                                                                  ('rate', '!=', 0)], order='name desc',limit=1)
            if exchange_rate:
                formula = '%s %s %s'%(str(self.cost_usd),exchange_rate.exchange_operator,str(exchange_rate.rate))
                self.with_company(self.env.company).standard_price = eval(formula)

    @api.onchange('ite_id')
    def onchange_ite_id(self):
        self.list_price = self.ite_id.amount

    @api.constrains('bim_group_id','default_code')
    def on_save_group_check_reference(self):
        if self.bim_group_id and (self.product_variant_ids and not self.product_variant_ids[0].default_code or not self.default_code):
            group_code = str(self.bim_group_id.code)+'%'
            self.env.cr.execute(
                "SELECT MAX(default_code) as default_code FROM product_template WHERE bim_group_id = %s AND default_code ILIKE '%s' AND id <> %s"%(self.bim_group_id.id,group_code,self.id))
            res = self.env.cr.dictfetchall()
            if res[0]['default_code']:
                default_code = int(res[0]['default_code'])
                default_code +=1
            else:
                code = self.bim_group_id.code
                default_code = "%s%s"%(code,''.zfill(7-len(str(code))))
            if self.product_variant_ids:
                self.product_variant_ids[0].default_code = default_code
            self.default_code = default_code


class BimProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_product_bim_cost_list(self, partner_id=False, state_id=False):
        cost_line_ids = self.env['bim.cost.list.line'].search([('product_id','=',self.id)])
        product_cost = False
        if partner_id:
            for line in cost_line_ids.filtered_domain([('cost_id.partner_id','=',partner_id.id)]):
                product_cost = line.price
                break
        if state_id and not product_cost:
            for line in cost_line_ids.filtered_domain([('cost_id.state_id','=',state_id.id)]):
                product_cost = line.price
                break
        return product_cost


    maintenance_asset_ids = fields.One2many('maintenance.asset', 'product_id', 'Asset')
    count_maintenance_assets = fields.Integer('Quantity Assets', compute="_compute_count_assets")

    def _compute_count_assets(self):
        for rec in self:
            rec.count_maintenance_assets = len(rec.maintenance_asset_ids)


    def action_view_maintenance_assets(self):
        action = self.env.ref('base_bim_2.action_maintenance_asset').sudo().read()[0]
        action['domain'] = [('product_id', '=', self.id)]
        action['context'] = {
            'default_product_id': self.id,
            'default_name': self.name,
            'default_code': self.default_code,
        }
        return action


class ProductDocumentBim(models.Model):
    _name = 'product.document.line'
    _description = "Product Document Line"

    name = fields.Char('Name')
    comprobante_01_name = fields.Char("Attachment Name")
    comprobante_01 = fields.Binary(
        string=('Attachment'),
        copy=False,
        attachment=True,
        help='Voucher 01')
    entry_date = fields.Datetime('Entry Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Responsable',default=lambda self: self.env.user)
    product_id = fields.Many2one('product.template', string="Product", ondelete='cascade')


class ProductChangeBim(models.Model):
    _name = 'product.change.line'
    _description = "Product Change Line"

    product_id = fields.Many2one('product.product', string='Products')
    qty = fields.Float("Quantity", digits="BIM qty")
    code_id = fields.Many2one('product.product', string='Code')
    position = fields.Integer("Position")
    product_id = fields.Many2one('product.template', string="Product", ondelete='cascade')


class BimProductPurchase(models.Model):
    _name = 'bim.product.purchase'
    _description = "Bim Product Purchase"

    purchase_id = fields.Many2one('purchase.order', required=True, ondelete='cascade')
    template_id = fields.Many2one('product.template', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')
    project_id = fields.Many2one('bim.project', required=True, ondelete='cascade')
    supplier_id = fields.Many2one('res.partner', required=True)
    purchase_price = fields.Float(required=True, digits="BIM price")
    date = fields.Date()
    quantity = fields.Float(required=True, digits="BIM qty")


