# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import xlrd
import base64
import logging
_logger = logging.getLogger(__name__)


class ResultTable(models.Model):
    _description = "Result Table"
    _name = 'result.table'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')


    title = fields.Char('Title', default='Tabla de Resultados', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    from_date = fields.Date('From Date', default=fields.Date.context_today, required=True)
    to_date = fields.Date('To Date', default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)

    project_ids = fields.Many2many('bim.project', string='Projects', tracking=True)
    execution_manager_ids = fields.Many2many('res.users', string='Jefe de Obra', tracking=True, default=lambda self: self.env.user)


    bim_project_state_ids = fields.Many2many('bim.project.state', string='State', tracking=True)
    lines_ids = fields.One2many('result.table.line', 'result_table_id', string='Lines')
    line_count = fields.Integer('Lines Count', compute='_compute_line_count')

    @api.depends('lines_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.lines_ids)


    def action_view_lines(self):
        action = self.env.ref('base_bim_2.action_result_table_line').sudo().read()[0]
        action['domain'] = [('result_table_id', '=', self.id)]
        action['context'] = {
            'default_result_table_id': self.id,
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('result.table') or 'New'
        return super().create(vals_list)



    def give_amount_out_invoice(self, project_id, date_from, date_to):
        amount = 0
        # FACTURAS DE VENTA
        invoices = self.env['account.move'].search([
            ('project_id', '=', project_id.id),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice'])
        ])

        for invoice in invoices:
            amount += invoice.amount_untaxed

        # FACTURAS RECTIFICATIVAS VENTA
        r_invoices = self.env['account.move'].search([
            ('project_id', '=', project_id.id),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('move_type', '=', 'out_refund')
        ])

        for invoice in r_invoices:
            amount -= invoice.amount_untaxed

        return amount


    def calculate_rows(self):
        # Validamos que tenga el grupo de permisos group_bi_bim
        if not self.env.user.has_group('base_bim_2.group_bi_bim_admin'):
            # Validamos que el user_id in execution_manager_ids
            if self.env.user.id not in self.execution_manager_ids.ids:
                raise UserError(_("You don't have the necessary permissions to perform this action."))
            else:
                if len(self.execution_manager_ids.ids) > 1:
                    raise UserError(_("You can only select one Execution Manager."))


        # Eliminar líneas previas
        self.lines_ids.unlink()
        if self.project_ids.ids:
            project_ids = self.project_ids
        elif self.bim_project_state_ids.ids:
            if not self.execution_manager_ids.ids:
                project_ids = self.env['bim.project'].search([('state_id', 'in', self.bim_project_state_ids.ids)])
            else:
                project_ids = self.env['bim.project'].search([('execution_manager', 'in', self.execution_manager_ids.ids), ('state_id', 'in', self.bim_project_state_ids.ids)])
        elif self.execution_manager_ids.ids:
            project_ids = self.env['bim.project'].search([('execution_manager', 'in', self.execution_manager_ids.ids)])
        else:
            project_ids = self.env['bim.project'].search([])

        if project_ids:
            for project_id in project_ids:
                # Obtener fechas
                date_from = self.from_date
                date_to = self.to_date

                # Obtener el año de `date_from`
                year = date_from.year

                # Inicializar la fecha con el mes anterior
                fecha_actual = date_from
                fdo_orig = 0
                if project_id.state_id.id:
                    counter = 0
                    while fecha_actual <= date_to:
                        # fdo_orig
                        # initial_sale + Facturado origen mes anterior + Facturado mes actual



                        # fdo_mon
                        fdo_mon = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        fdo_mon = self.give_amount_out_invoice(project_id, this_mon_begin_day, this_mon_last_day)

                        counter += 1
                        # fdo_orig

                        _logger.info('counter: %s', counter)
                        _logger.info('fecha_actual: %s', fecha_actual)


                        if counter == 1:
                            last_day = fecha_actual.replace(day=1) + timedelta(days=-1)
                            date_2000 = fecha_actual.replace(day=1, year=2000)
                            fdo_orig = fdo_mon + self.give_amount_out_invoice(project_id, date_2000, last_day) + project_id.initial_sale
                        else:
                            fdo_orig += fdo_mon

                        # fdo_year
                        this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        fdo_year = self.give_amount_out_invoice(project_id, this_mon_begin_day, this_mon_last_day)
                        bim_general_config_id = self.env['bim.general.config'].search([
                                    ('key', '=', 'picking_analysis_day')], limit=1)

                        if bim_general_config_id:
                            picking_analysis_day = bim_general_config_id.value
                            if picking_analysis_day == 0:
                                picking_analysis_day = 10
                        else:
                            picking_analysis_day = 10

                        # mat
                        # los albaranes de compra de material
                        # menos los de albaranes de devolución
                        picking_obj = self.env['stock.picking']


                        # Sumamos  las entradas
                        mat = 0
                        _logger.info('picking_analysis_day: %s', picking_analysis_day)
                        this_mon_begin_day = fecha_actual.replace(day=int(picking_analysis_day))
                        next_month = this_mon_begin_day + relativedelta(months=1)
                        domain = [
                                    ('bim_project_id', '=', project_id.id),
                                    ('state', '=', 'done'),
                                    ('include_for_bim', '=', True),
                                    ('date_done', '>', this_mon_begin_day),
                                    ('date_done', '<=', next_month),
                                    ('picking_type_id.code', 'in', ['incoming'])
                                  ]

                        in_pickings = picking_obj.search(domain)

                        _logger.info('in_pickings: %s', in_pickings)

                        for p in in_pickings:
                            mat += p.total_cost

                        # Restamos las salidas
                        domain = [
                                    ('bim_project_id', '=', project_id.id),
                                    ('state', '=', 'done'),
                                    ('include_for_bim', '=', True),
                                    ('date_done', '>', this_mon_begin_day),
                                    ('date_done', '<=', next_month),
                                    ('picking_type_id.code', 'in', ['outgoing'])
                                  ]
                        out_pickings = picking_obj.search(domain)
                        _logger.info('out_pickings: %s', out_pickings)

                        for p in out_pickings:
                            mat -= p.total_cost


                        # o_mat
                        if counter == 1:
                            o_mat = 0
                            this_mon_begin_day = fecha_actual.replace(day=int(picking_analysis_day))
                            next_month = this_mon_begin_day + relativedelta(months=1)
                            domain = [
                                        ('bim_project_id', '=', project_id.id),
                                        ('state', '=', 'done'),
                                        ('include_for_bim', '=', True),
                                        ('date_done', '>', date_2000),
                                        ('date_done', '<=', next_month),
                                        ('picking_type_id.code', 'in', ['incoming'])
                                      ]

                            in_pickings = picking_obj.search(domain)

                            _logger.info('in_pickings: %s', in_pickings)

                            for p in in_pickings:
                                o_mat += p.total_cost

                            # Restamos las salidas
                            domain = [
                                        ('bim_project_id', '=', project_id.id),
                                        ('state', '=', 'done'),
                                        ('include_for_bim', '=', True),
                                        ('date_done', '>', date_2000),
                                        ('date_done', '<=', next_month),
                                        ('picking_type_id.code', 'in', ['outgoing'])
                                      ]
                            out_pickings = picking_obj.search(domain)
                            _logger.info('out_pickings: %s', out_pickings)

                            for p in out_pickings:
                                o_mat -= p.total_cost
                        else:
                            o_mat += mat



                        # Sumamos  las entradas
                        cte_year_mat = 0
                        this_mon_begin_day = fecha_actual.replace(day=int(picking_analysis_day))
                        this_mon_begin_day_year = fecha_actual.replace(day=int(picking_analysis_day), month=1)
                        next_month = this_mon_begin_day + relativedelta(months=1)
                        domain = [
                                    ('bim_project_id', '=', project_id.id),
                                    ('state', '=', 'done'),
                                    ('include_for_bim', '=', True),
                                    ('date_done', '>', this_mon_begin_day_year),
                                    ('date_done', '<=', next_month),
                                    ('picking_type_id.code', 'in', ['incoming'])
                                  ]

                        in_pickings = picking_obj.search(domain)

                        _logger.info('in_pickings: %s', in_pickings)

                        for p in in_pickings:
                            cte_year_mat += p.total_cost

                        # Restamos las salidas
                        domain = [
                                    ('bim_project_id', '=', project_id.id),
                                    ('state', '=', 'done'),
                                    ('include_for_bim', '=', True),
                                    ('date_done', '>', this_mon_begin_day_year),
                                    ('date_done', '<=', next_month),
                                    ('picking_type_id.code', 'in', ['outgoing'])
                                  ]
                        out_pickings = picking_obj.search(domain)
                        _logger.info('out_pickings: %s', out_pickings)

                        for p in out_pickings:
                            cte_year_mat -= p.total_cost


                        # asist
                        asist = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        hr_attendance_ids = self.env['hr.attendance'].search([
                            ('project_id', '=', project_id.id),
                            ('check_in', '>=', this_mon_begin_day),
                            ('check_in', '<=', this_mon_last_day)
                        ])
                        asist = sum(hr_attendance_ids.mapped('attendance_cost'))


                        # o_asist
                        if counter == 1:
                            o_asist = 0
                            this_mon_begin_day = fecha_actual.replace(day=1)
                            this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                            hr_attendance_ids = self.env['hr.attendance'].search([
                                ('project_id', '=', project_id.id),
                                ('check_in', '>=', date_2000),
                                ('check_in', '<=', this_mon_last_day)
                            ])
                            o_asist = sum(hr_attendance_ids.mapped('attendance_cost'))
                        else:
                            o_asist += asist


                        # cte_year_asist
                        cte_year_asist = 0
                        this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        hr_attendance_ids = self.env['hr.attendance'].search([
                            ('project_id', '=', project_id.id),
                            ('check_in', '>=', this_mon_begin_day),
                            ('check_in', '<=', his_mon_last_day)
                        ])
                        cte_year_asist = sum(hr_attendance_ids.mapped('attendance_cost'))




                        # partner
                        partner = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        hr_attendance_partner_ids = self.env['partner.attendance'].search([
                            ('project_id', '=', project_id.id),
                            ('check_in', '>=', this_mon_begin_day),
                            ('check_in', '<=', this_mon_last_day)
                        ])
                        partner = sum(hr_attendance_partner_ids.mapped('balance'))


                        # o_partner
                        if counter == 1:
                            o_partner = 0
                            this_mon_begin_day = fecha_actual.replace(day=1)
                            this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                            hr_attendance_partner_ids = self.env['partner.attendance'].search([
                                ('project_id', '=', project_id.id),
                                ('check_in', '>=', date_2000),
                                ('check_in', '<=', this_mon_last_day)
                            ])
                            o_partner = sum(hr_attendance_partner_ids.mapped('balance'))
                        else:
                            o_partner += partner


                        _logger.info('o_partner >>>> : %s', o_partner)


                        # cte_year_partner
                        cte_year_partner = 0
                        this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        hr_attendance_ids = self.env['partner.attendance'].search([
                            ('project_id', '=', project_id.id),
                            ('check_in', '>=', this_mon_begin_day),
                            ('check_in', '<=', his_mon_last_day)
                        ])
                        cte_year_partner = sum(hr_attendance_ids.mapped('balance'))


                        # viajes
                        viajes = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        tms_shipment_ids = self.env['tms.shipment'].search([
                            ('bim_project_destination_id', '=', project_id.id),
                            ('date', '>=', this_mon_begin_day),
                            ('date', '<=', this_mon_last_day),
                            ('state', '=', 'confirmed')
                        ])

                        for v in tms_shipment_ids:
                            if v.bim_project_destination_id == v.bim_project_origin_id:
                                viajes += v.total


                        tms_shipment_ids = self.env['tms.shipment'].search([
                            ('bim_project_origin_id', '=', project_id.id),
                            ('date', '>=', this_mon_begin_day),
                            ('date', '<=', this_mon_last_day),
                            ('state', '=', 'confirmed')
                        ])

                        for v in tms_shipment_ids:
                            if v.bim_project_destination_id != v.bim_project_origin_id:
                                viajes += v.total


                        # o_viajes
                        if counter == 1:
                            o_viajes = 0
                            tms_shipment_ids = self.env['tms.shipment'].search([
                                ('bim_project_destination_id', '=', project_id.id),
                                ('date', '>=', date_2000),
                                ('date', '<=', this_mon_last_day),
                                ('state', '=', 'confirmed')
                            ])

                            for v in tms_shipment_ids:
                                if v.bim_project_destination_id == v.bim_project_origin_id:
                                    o_viajes += v.total
                        else:
                            o_viajes += viajes


                        tms_shipment_ids = self.env['tms.shipment'].search([
                            ('bim_project_origin_id', '=', project_id.id),
                            ('date', '>=', date_2000),
                            ('date', '<=', this_mon_last_day),
                            ('state', '=', 'confirmed')
                        ])

                        for v in tms_shipment_ids:
                            if v.bim_project_destination_id != v.bim_project_origin_id:
                                o_viajes += v.total



                        # cte_year_viajes
                        cte_year_viajes = 0
                        this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)

                        tms_shipment_ids = self.env['tms.shipment'].search([
                            ('bim_project_destination_id', '=', project_id.id),
                            ('date', '>=', this_mon_begin_day),
                            ('date', '<=', his_mon_last_day),
                            ('state', '=', 'confirmed')
                        ])

                        for v in tms_shipment_ids:
                            if v.bim_project_destination_id == v.bim_project_origin_id:
                                cte_year_viajes += v.total


                        tms_shipment_ids = self.env['tms.shipment'].search([
                            ('bim_project_origin_id', '=', project_id.id),
                            ('date', '>=', this_mon_begin_day),
                            ('date', '<=', his_mon_last_day),
                            ('state', '=', 'confirmed')
                        ])

                        for v in tms_shipment_ids:
                            if v.bim_project_destination_id != v.bim_project_origin_id:
                                cte_year_viajes += v.total



                        # otros
                        otros = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        this_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        other_expense_line_ids = self.env['other.expense.line'].search([
                            ('project_id', '=', project_id.id),
                            ('other_expense_id.date', '>=', this_mon_begin_day),
                            ('other_expense_id.date', '<=', this_mon_last_day),
                            ('other_expense_id.state', '=', 'done')
                        ])

                        for o in other_expense_line_ids:
                            otros += o.total


                        # o_otros
                        if counter == 1:
                            o_otros = 0
                            other_expense_line_ids = self.env['other.expense.line'].search([
                                ('project_id', '=', project_id.id),
                                ('other_expense_id.date', '>=', date_2000),
                                ('other_expense_id.date', '<=', this_mon_last_day),
                                ('other_expense_id.state', '=', 'done')
                            ])

                            for o in other_expense_line_ids:
                                o_otros += o.total
                        else:
                            o_otros += otros


                        # cte_year_otros
                        this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        cte_year_otros = 0
                        other_expense_line_ids = self.env['other.expense.line'].search([
                            ('project_id', '=', project_id.id),
                            ('other_expense_id.date', '>=', this_mon_begin_day),
                            ('other_expense_id.date', '<=', his_mon_last_day),
                            ('other_expense_id.state', '=', 'done')
                        ])

                        for o in other_expense_line_ids:
                            cte_year_otros += o.total


                        # cte_mes
                        cte_mes = mat + asist + viajes + otros + partner

                         # cte_orig
                        if counter == 1:
                            cte_orig = o_mat + o_asist + o_viajes + o_otros + o_partner + project_id.initial_coste
                        else:
                            cte_orig += cte_mes


                        # cte_year
                        cte_year = cte_year_mat + cte_year_asist + cte_year_viajes + cte_year_otros + cte_year_partner

                        # ap_mon
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)

                        arr_search = [
                            ('project_id', '=', project_id.id),
                            ('end_date', '>=', this_mon_begin_day),
                            ('end_date', '<=', this_mon_last_day),
                            ('include_for_bim', '=', True)
                        ]

                        picking_analysis_ids = self.env['picking.analysis'].search(arr_search)


                        ap_mon = 0
                        for pi in picking_analysis_ids:
                            ap_mon += pi.subtotal

                        # ap_year
                        # ap_dic
                        # this_mon_begin_day = fecha_actual.replace(day=1, month=1)
                        his_mon_last_day = fecha_actual.replace(day=1, month=1) - timedelta(days=1)
                        this_mon_begin_day = his_mon_last_day - timedelta(days=30)
                        picking_analysis_ids = self.env['picking.analysis'].search([
                            ('project_id', '=', project_id.id),
                            ('end_date', '>=', this_mon_begin_day),
                            ('end_date', '<=', his_mon_last_day),
                            ('include_for_bim', '=', True)
                        ])

                        ap_year = 0
                        ap_dic = 0
                        for pi in picking_analysis_ids:
                            ap_dic += pi.subtotal

                        ap_year = ap_mon - ap_dic


                        # oenc_mon OENC = Obra ejecutada no certificada
                        oenc_mon = 0
                        this_mon_begin_day = fecha_actual.replace(day=1)
                        his_mon_last_day = (fecha_actual + relativedelta(months=1)).replace(day=1) + timedelta(days=-1)
                        picking_analysis_ids = self.env['picking.analysis.line'].search([
                            ('picking_analysis_id.project_id', '=', project_id.id),
                            ('picking_analysis_id.end_date', '>=', this_mon_begin_day),
                            ('picking_analysis_id.end_date', '<=', his_mon_last_day),
                            ('picking_analysis_id.include_for_bim', '=', True),
                            ('oenc', '=', True)
                        ])
                        for pi in picking_analysis_ids:
                            oenc_mon += pi.subtotal


                        # oenc_year
                        oenc_year = 0
                        oenc_year_dic = 0
                        his_mon_last_day = fecha_actual.replace(day=1, month=1) - timedelta(days=1)
                        this_mon_begin_day = his_mon_last_day - timedelta(days=30)
                        picking_analysis_ids = self.env['picking.analysis.line'].search([
                            ('picking_analysis_id.project_id', '=', project_id.id),
                            ('picking_analysis_id.end_date', '>=', this_mon_begin_day),
                            ('picking_analysis_id.end_date', '<=', his_mon_last_day),
                            ('picking_analysis_id.include_for_bim', '=', True),
                            ('oenc', '=', True)
                        ])
                        for pi in picking_analysis_ids:
                            oenc_year_dic += pi.subtotal
                        oenc_year = oenc_mon - oenc_year_dic

                        # result_orig
                        result_orig = fdo_orig - cte_orig + ap_mon

                        # result_year
                        result_year = fdo_year - cte_year + ap_year

                        # mbrut_orig
                        if ( fdo_orig + oenc_mon) != 0:
                            mbrut_orig = (1 - ( (cte_orig - ap_mon + oenc_mon) / ( fdo_orig + oenc_mon) ) ) * 100
                        else:
                            mbrut_orig = 0

                        # mbrut_year
                        if ( fdo_year + oenc_year) != 0:
                            mbrut_year = (1 - ( (cte_year - ap_year + oenc_year) / ( fdo_year + oenc_year) ) ) * 100
                        else:
                            mbrut_year = 0

                        # mnet_orig
                        if ( fdo_orig + oenc_mon) != 0:
                            mnet_orig = (1 - ( (cte_orig - ap_mon + oenc_mon +  (  (10/100) * (fdo_orig+oenc_mon) )    ) / ( fdo_orig + oenc_mon) ) ) * 100
                        else:
                            mnet_orig = 0

                        # mmnet_year
                        if ( fdo_year + oenc_year) != 0:
                            mmnet_year = (1 - ( (cte_year - ap_year + oenc_year +  (  (10/100) * (fdo_year+oenc_year) )    ) / ( fdo_year + oenc_year) ) ) * 100
                        else:
                            mmnet_year = 0





                        vals = {
                            'project_id': project_id.id,
                            'result_table_id': self.id,
                            'year': fecha_actual.year,
                            'month': str(fecha_actual.month).zfill(2),  # Asegura que el mes tenga dos dígitos (ej: 01, 02)
                            'fdo_orig': fdo_orig,
                            'fdo_mon': fdo_mon,
                            'fdo_year': fdo_year,
                            'mat': mat,
                            'asist': asist,
                            'viajes': viajes,
                            'otros': otros,
                            'cte_mes': cte_mes,
                            'cte_orig': cte_orig,
                            'o_mat': o_mat,
                            'o_asist': o_asist,
                            'o_viajes': o_viajes,
                            'o_otros': o_otros,
                            'o_partner': o_partner,
                            'partner': partner,
                            'cte_year_mat': cte_year_mat,
                            'cte_year_asist': cte_year_asist,
                            'cte_year_viajes': cte_year_viajes,
                            'cte_year_otros': cte_year_otros,
                            'cte_year_partner': cte_year_partner,
                            'cte_year' : cte_year,
                            'ap_mon': ap_mon,
                            'ap_year': ap_year,
                            'oenc_mon': oenc_mon,
                            'oenc_year': oenc_year,
                            'result_orig': result_orig,
                            'result_year': result_year,
                            'mbrut_orig' : mbrut_orig,
                            'mbrut_year' : mbrut_year,
                            'mnet_orig' : mnet_orig,
                            'mmnet_year' : mmnet_year,
                            'state_project': project_id.state_id.name,
                            'execution_manager': project_id.execution_manager.id
                        }
                        self.env['result.table.line'].create(vals)
                        fecha_actual += relativedelta(months=1)




class ResultTableLine(models.Model):
    _description = "Result Table Line"
    _name = 'result.table.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    state_project = fields.Char('Estado')
    execution_manager = fields.Many2one('res.users', string='Jefe de Obra', tracking=True)
    result_table_id = fields.Many2one('result.table', string='Result Table')
    project_id = fields.Many2one('bim.project', string='Project')
    customer_id = fields.Many2one('res.partner', string='Customer', related='project_id.customer_id', store=True)

    contracted_sale = fields.Monetary('Contracted Sales', help="Total amount of contracted sales", related='project_id.contracted_sale', store=True)
    expansion_contract = fields.Monetary('Expansion Contract', help="Total amount of expansion contract", related='project_id.expansion_contract', store=True)
    contracted_cost = fields.Monetary('Contracted Costs', help="Total amount of contracted costs", related='project_id.contracted_cost', store=True)
    contracted_coefficient = fields.Float('Contracted Coefficient', help="Contracted coefficient", related='project_id.contracted_coefficient', store=True, digits=(10, 2))
    pending_execution = fields.Monetary('Pendiente Ejecutar', help="Pendiente Ejecutar (Contratado - Coste)", related='project_id.pending_execution',
                         store=True)


    currency_id = fields.Many2one('res.currency', string='Currency', related='project_id.currency_id', store=True)

    year = fields.Char('A')
    month = fields.Char('M')

    fdo_orig = fields.Float('FdO orig')
    fdo_mon = fields.Float('FdO-M')
    fdo_year = fields.Float('FdO-A')

    cte_orig = fields.Float('Cte orig.')
    cte_mes = fields.Float('Cte-M')

    mat = fields.Float('Mat.')
    partner = fields.Float('Partner.')
    asist = fields.Float('Asist.')
    viajes = fields.Float('Viajes')
    otros = fields.Float('Otros')

    o_mat = fields.Float('O.Mat.')
    o_partner = fields.Float('O.Partner.')
    o_asist = fields.Float('O.Asist.')
    o_viajes = fields.Float('O.Viajes')
    o_otros = fields.Float('O.Otros')

    cte_year_mat = fields.Float('A.Mat.')
    cte_year_partner = fields.Float('A.Partner.')
    cte_year_asist = fields.Float('A.Asist.')
    cte_year_viajes = fields.Float('A.Viajes')
    cte_year_otros = fields.Float('A.Otros')

    cte_year = fields.Float('Cte-A')
    ap_mon = fields.Float('A/P-M')
    ap_year = fields.Float('A/P-A')
    oenc_mon = fields.Float('OENC-M')

    oenc_year = fields.Float('OENC-A')
    result_orig = fields.Float('R-Orig')
    result_year = fields.Float('R-A')

    mbrut_orig = fields.Float('%MBrut orig')
    mbrut_year = fields.Float('%MBrut-A')
    mnet_orig = fields.Float('%MNet orig')
    mmnet_year = fields.Float('%MNet-A')
