# coding: utf-8
from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    journal_id = fields.Many2one('account.journal', string='Journal')
    bim_hours = fields.Integer('Daily Work Hours', default=8)
    validate_stock = fields.Boolean('Validate Stock Movements', default=True)
    allow_to_buy_more_mat = fields.Boolean('More Materials',copy=False)
    allow_to_buy_more_serv = fields.Boolean('More Services',copy=False)
    working_hours = fields.Float('Bim Working Hours', help="Indicates the number of hours in a day or working day", default=8.0, digits="BIM qty")
    extra_hour_factor = fields.Float('Overtime Factor', digits=(12, 8), help="Indicates the factor for the calculation of overtime", default=0.0077777)
    hourly_cost = fields.Float('Hourly cost', digits=(10, 2),
                                     help="Default hourly cost", default=50)
    paidstate_product = fields.Many2one('product.product', 'Payment Status Product', help="Product that will be used to invoice the payment status of project. Leave prices at zero")
    retention_product = fields.Many2one('product.product', 'Retention Product', help="Product that will be used to bill the Retention in the payment status of Project.")

    stock_location_mobile = fields.Many2one('stock.location', 'Mobile Warehouse Location', help="Location that will be used by default for the entry of merchandise in the Mobile Warehouse")
    retention = fields.Float('Retention %', default=5, digits=(10, 2))
    sequence_by_year = fields.Boolean('Sequence by Year', default=False)
    type_work = fields.Selection([
        ('cost', 'Cost'),
        ('price', 'Price'),
        ('pricelist', 'Rate'),
        ('costlist', 'Cost List')],
        string="Price in Budget", default='cost')

    type_calc = fields.Selection([
        ('standard', 'Standard'),
        ('apu', 'Apu'),
        ('apu-hh', 'Apu HH'),
        ],
        string="type of calculation", default='standard')

    asset_template_id = fields.Many2one(
        'bim.assets.template',
        'Assets and Discounts Template',
        default=lambda self: self.env.ref('base_bim_2.bim_asset_template_base', raise_if_not_found=False),
        help='Assets and Discounts template to use when creating a budget')
    template_mant_id = fields.Many2one('mail.template', string='Mail Template')
    bim_product_category_id = fields.Many2one('product.category', required=True, default=lambda self: self.env.ref('product.product_category_all', raise_if_not_found=False))
    include_vat_in_indicators = fields.Boolean()
    hour_start_job = fields.Selection([('0','00'),('1','01'),('2','02'),('3','03'),('4','04'),('5','05'),('6','06'),('7','07'),('8','08'),('9','09'),('10','10'),('11','11'),('12','12'),
                                       ('13','13'),('14','14'),('15','15'),('16','16'),('17','17'),('18','18'),('19','19'),('20','20'),('21','21'),('22','22'),('23','23')], default='9')
    minute_start_job = fields.Selection([('0', '00'), ('05', '05'), ('10', '10'), ('15', '15'), ('20', '20'), ('25', '25'), ('30', '30'),
                                        ('35', '35'), ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')], default='0')
    department_required = fields.Boolean(default=True)
    use_project_warehouse = fields.Boolean(default=False)
    create_analytic_account = fields.Boolean(default=True)
    include_picking_cost = fields.Boolean(default=False)
    picking_move_all = fields.Boolean(default=False)
    warehouse_prefix = fields.Char(default='ALM ')
    invoice_debit_credit = fields.Boolean(default=True)
    bim_include_invoice_sale = fields.Boolean(default=True, string="Bim Include Sale Invoice")
    bim_include_invoice_purchase = fields.Boolean(default=True, string="Bim Include Purchase Invoice")
    bim_include_refund = fields.Boolean(default=True)
    bim_invoice_multiple_project = fields.Boolean(default=True)
    bim_certificate_chapters = fields.Boolean(default=True, string="Certificate Chapters")
    server_hour_difference = fields.Integer(default=0, string="Server Hour Difference")
    limit_certification_percent = fields.Integer(default=100, string="Limit Certification Percent")
    limit_certification = fields.Boolean(default=True, string="Limit Certification")
    performance_calculation = fields.Boolean(default=True, string="Performance Calculation")
    type_calc_cert = fields.Selection([('quantity', 'Quantity'),
                                       ('percent', 'Percent')],
                                        help="Allows you to configure whether the certification is calculated by quantity or percentage",
                                        string='Type Calc Certification',
                                        required=True,
                                        default='quantity')
    limit_purchase = fields.Boolean(default=False, string="Limit Purchase")
    project_product_limited = fields.Boolean(default=False, string="Project Product Limited")
    edit_code_space = fields.Boolean(default=False, string="Edit Code Space")

    edit_code_project = fields.Boolean(default=False, string="Edit Code Project")
    edit_code_budget = fields.Boolean(default=False, string="Edit Code Budget")
    calc_performance = fields.Boolean(default=False, string="Calc Performance")

    purchase_cost_zero = fields.Boolean(default=False, string="Cost Zero Purchase")
    bim_main_location = fields.Boolean(default=True, string="Main Location")
    company_resource_template_id = fields.Many2one('bim.resource.template')
    ubication_deliver_id = fields.Many2one('stock.location', "EPI deliver location", domain="[( 'usage', '=', 'internal' )]")
    ubication_deliver_dest_id = fields.Many2one('stock.location', "EPI destination location", domain="[( 'usage', '=', 'internal' )]")
    amount_type = fields.Selection([
        ('compute', 'Calculated'),
        ('fixed', 'Manual'),
        ('locked', 'Lock')], string="Price Type", default='compute')
