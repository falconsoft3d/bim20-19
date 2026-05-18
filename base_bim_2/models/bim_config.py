# coding: utf-8
from odoo import api, fields, models, _

class BimConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    journal_id = fields.Many2one('account.journal', string='Journal', related="company_id.journal_id", readonly=False)
    working_hours = fields.Float('Workday', related ="company_id.working_hours", readonly=False, digits="BIM qty")
    extra_hour_factor = fields.Float('Overtime Factor', related ="company_id.extra_hour_factor", readonly=False, digits=(10, 2))
    paidstate_product = fields.Many2one('product.product', string='Payment Status Product', related ="company_id.paidstate_product", readonly=False)

    hourly_cost = fields.Float('Default hourly cost', related="company_id.hourly_cost", readonly=False, digits=(10, 2))


    retention_product = fields.Many2one('product.product', string='Retention Product',
                                             related="company_id.retention_product", readonly=False)
    retention = fields.Float('Retention %', related="company_id.retention", readonly=False, digits=(10, 2))
    server_hour_difference = fields.Integer('Server Hour Difference', related="company_id.server_hour_difference", readonly=False, required=True)

    validate_stock = fields.Boolean(related="company_id.validate_stock")
    picking_move_all = fields.Boolean(related="company_id.picking_move_all", readonly=False)
    allow_to_buy_more_mat = fields.Boolean('More Materials', related="company_id.allow_to_buy_more_mat", readonly=False)
    allow_to_buy_more_serv = fields.Boolean('More Services', related="company_id.allow_to_buy_more_serv", readonly=False)
    include_vat_in_indicators = fields.Boolean(related="company_id.include_vat_in_indicators", string='Include VAT in Calculations', readonly=False)
    asset_template_id = fields.Many2one('bim.assets.template', related='company_id.asset_template_id', readonly=False)
    stock_location_mobile = fields.Many2one('stock.location', related='company_id.stock_location_mobile', readonly=False)
    type_work = fields.Selection(string="Price in Budget", required=True, related="company_id.type_work", readonly=False)
    type_calc = fields.Selection(string="Type of calculation", required=True, related="company_id.type_calc", readonly=False)

    template_mant_id = fields.Many2one('mail.template', related="company_id.template_mant_id", string='Mail Template', readonly=False)
    product_category_id = fields.Many2one('product.category', 'Product Category', related='company_id.bim_product_category_id', readonly=False, required=True)


    sequence_by_year = fields.Boolean(related='company_id.sequence_by_year', readonly=False)
    hour_start_job = fields.Selection(related='company_id.hour_start_job', readonly=False, required=True)
    minute_start_job = fields.Selection(related='company_id.minute_start_job', readonly=False, required=True)
    department_required = fields.Boolean(related='company_id.department_required', readonly=False)
    use_project_warehouse = fields.Boolean(related='company_id.use_project_warehouse', readonly=False)
    create_analytic_account = fields.Boolean(related='company_id.create_analytic_account', readonly=False)
    include_picking_cost = fields.Boolean(related='company_id.include_picking_cost', readonly=False)
    warehouse_prefix = fields.Char(related='company_id.warehouse_prefix', readonly=False, required=True)
    invoice_debit_credit = fields.Boolean(related='company_id.invoice_debit_credit', readonly=False, string="Invoice Debit Credit")
    limit_certification = fields.Boolean(related='company_id.limit_certification', readonly=False, string="Limit Certification")
    limit_certification_percent = fields.Integer(related='company_id.limit_certification_percent', readonly=False, string="Limit Certification Percent")
    bim_include_invoice_sale = fields.Boolean(related='company_id.bim_include_invoice_sale', readonly=False, string="Bim Include Sale Invoice")
    bim_include_invoice_purchase = fields.Boolean(related='company_id.bim_include_invoice_purchase', readonly=False, string="Bim Include Purchase Invoice")
    bim_include_refund = fields.Boolean(related='company_id.invoice_debit_credit', readonly=False, string="Bim Include Refund")
    bim_invoice_multiple_project = fields.Boolean(related='company_id.bim_invoice_multiple_project', readonly=False, string="Bim Invoice Multiple Projects")
    bim_certificate_chapters = fields.Boolean(related='company_id.bim_certificate_chapters', readonly=False, string="Certificate Chapters")
    performance_calculation = fields.Boolean(related='company_id.performance_calculation', readonly=False, string="Performance Calculation")
    limit_purchase = fields.Boolean(related='company_id.limit_purchase', readonly=False, string="Limit Purchase")

    type_calc_cert = fields.Selection(related='company_id.type_calc_cert', readonly=False, required=True)
    amount_type = fields.Selection(related='company_id.amount_type', readonly=False, required=True)

    project_product_limited = fields.Boolean(related='company_id.project_product_limited', readonly=False, string="Project Product Limited")
    edit_code_space = fields.Boolean(related='company_id.edit_code_space', readonly=False, string="Edit Code Space")
    edit_code_project = fields.Boolean(related='company_id.edit_code_project', readonly=False, string="Edit Code Project")
    edit_code_budget = fields.Boolean(related='company_id.edit_code_budget', readonly=False, string="Edit Code Budget")
    purchase_cost_zero = fields.Boolean(related='company_id.purchase_cost_zero', readonly=False, string="Cost Zero Purchase")
    calc_performance = fields.Boolean(default=False, string="Calc Performance")

    bim_main_location = fields.Boolean(related='company_id.bim_main_location', readonly=False, string="Main Location")
    company_resource_template_id = fields.Many2one('bim.resource.template', related='company_id.company_resource_template_id',
                                                   readonly=False, string="Resource Template")
    master_url = fields.Char()
    master_region = fields.Char()
    master_token = fields.Char()
    tools_inventory_movement = fields.Boolean()
    close_stage_with_certification = fields.Boolean()
    product_expense_invoice_id = fields.Many2one("product.product", string="Product expense invoice")

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        master_url = params.get_param('master_url')
        master_region = params.get_param('master_region')
        master_token = params.get_param('master_token')
        tools_inventory_movement = params.get_param('tools_inventory_movement')
        product_expense_invoice_id = params.get_param('product_expense_invoice_id')
        close_stage_with_certification = params.get_param('close_stage_with_certification')
        res.update(
            master_url=master_url,
            master_region=master_region,
            master_token=master_token,
            tools_inventory_movement=tools_inventory_movement,
            product_expense_invoice_id=product_expense_invoice_id,
            close_stage_with_certification=close_stage_with_certification,
        )
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param("master_url",
                                                         self.master_url)
        self.env['ir.config_parameter'].sudo().set_param("master_region",
                                                         self.master_region)
        self.env['ir.config_parameter'].sudo().set_param("master_token",
                                                         self.master_token)
        self.env['ir.config_parameter'].sudo().set_param("tools_inventory_movement",
                                                         self.tools_inventory_movement)
        self.env['ir.config_parameter'].sudo().set_param("product_expense_invoice_id",
                                                         self.product_expense_invoice_id)
        self.env['ir.config_parameter'].sudo().set_param("close_stage_with_certification",
                                                         self.close_stage_with_certification)
