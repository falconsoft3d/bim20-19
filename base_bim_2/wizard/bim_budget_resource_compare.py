# coding: utf-8
import base64
import logging
import xlwt
import calendar
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from io import BytesIO
from datetime import datetime, date, timedelta
_logger = logging.getLogger(__name__)
from dateutil import rrule

RESOURCE_TYPE = {
    'M': 'Material',
    'H': 'Labor',
    'Q': 'Equipment',
    'A': 'Administrative',
}


class BimBudgetResourceCompareWizard(models.TransientModel):
    _name = 'bim.budget.resource.compare.wizard'
    _description = 'Budget Resource Compare'

    @api.model
    def _default_budget_ids(self):
        ids = self.env.context.get('active_ids', [])
        budgets = self.env['bim.budget'].browse(ids)
        budgets_to_compare = budgets.filtered_domain([('resource_template_id','!=',False)])
        budget_ids = []
        if budgets_to_compare:
            budget_ids = budgets_to_compare.ids
        return budget_ids

    budget_ids = fields.Many2many('bim.budget', default=_default_budget_ids)

    def _default_date_from(self):
        budget_ids = self._default_budget_ids()
        budgets = self.env['bim.budget'].browse(budget_ids)
        today = fields.Date.today()
        date_from = min([d for d in budgets.concept_ids.child_ids.mapped('acs_date_start') if d], default=today)
        return date_from

    def _default_date_to(self):
        budget_ids = self._default_budget_ids()
        budgets = self.env['bim.budget'].browse(budget_ids)
        today = fields.Date.today()
        date_to = max([d for d in budgets.concept_ids.child_ids.mapped('acs_date_end') if d], default=today)
        return date_to

    date_from = fields.Date(required=True, default=_default_date_from)
    date_to = fields.Date(required=True, default=_default_date_to)

    def iterate_months(self):
        start_date = datetime(self.date_from.year, self.date_from.month, self.date_from.day)
        end_date = datetime(self.date_to.year, self.date_to.month, self.date_to.day)
        date_pares = []
        last_dt = False
        for dt in rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date):
            date_pares.append(datetime(dt.year, dt.month, dt.day,12,00,00))
            # dateMonthEnd = datetime(dt.year, dt.month, calendar.monthrange(dt.year, dt.month)[1], 23, 59, 59)
            # # dateMonthEnd = datetime.strptime(dateMonthEnd,'%Y-%m-%d')
            # # dateMonthEnd = datetime.strftime(dateMonthEnd,'%Y-%m-%d')
            # date_pares.append(dateMonthEnd)
            last_dt = dt
        if (last_dt and last_dt.month != self.date_to.month) or not last_dt:
            date_pares.append(datetime(self.date_to.year, self.date_to.month, self.date_to.day, 12, 00, 00))
            # date_pares.append(self.date_to)
        return date_pares

    def include_in_summary(self, summary, par, product, quantity,template_qty):
        found = False
        for resource in summary['resources']:
            if resource['product'] == product:
                for period in resource['periods']:
                    if period['period'] == par:
                        period['quantity'] += quantity
                        found = True
                        break
                if not found:
                    resource['periods'].append(
                        {'period': par, 'quantity': quantity}
                    )
                    found= True
                    break
        if not found:
            summary['resources'].append({
                'product': product,
                'quantity': quantity,
                'template_qty': template_qty,
                'periods': [{'period': par, 'quantity': quantity}],
            })
        return summary

    def get_max_resource_qty(self, filtered_resources):
        start = min([d for d in filtered_resources.mapped('acs_date_start') if d or d.parent_id.acs_date_start])
        date_to = max([d for d in filtered_resources.mapped('acs_date_end') if d or d.parent_id.acs_date_end])
        max_qty = 0
        fist_day = start
        while fist_day <= date_to:
            total_available = sum(filtered_resources.filtered(lambda r: r.acs_date_start <= fist_day and r.acs_date_end >= fist_day).mapped('available'))
            if total_available > max_qty:
                max_qty = total_available
            fist_day = fist_day + timedelta(days=1)
        return max_qty



    def print_compare(self):
        date_pares = self.iterate_months()
        if not self.budget_ids:
            raise ValidationError(_('You should assign Resource Templates to Budgets before printing balance'))
        templates = self.budget_ids.mapped('resource_template_id')
        if len(templates) > 1:
            raise ValidationError(_('Only Budgets with the same Resource Template can be compare'))
        elif len(templates) == 0:
            raise ValidationError(_("Budgets without template can not be included in balance"))
        workbook = xlwt.Workbook(encoding="utf-8")
        worksheet = workbook.add_sheet(_('Resources Balance'))
        file_name = _('Resources_Balance')
        style_title = xlwt.easyxf('font: name Times New Roman 180, color-index black, bold on; align: wrap yes, horiz center')
        style_border_table_top = xlwt.easyxf('borders: left thin, right thin, top thin, bottom thin; font: bold on;')
        style_bold = xlwt.easyxf('font: bold on;')
        style_border_table_details = xlwt.easyxf('borders: bottom thin;')
        worksheet.write_merge(0, 0, 0, 11, _("RESOURCE BALANCE"), style_title)
        worksheet.write_merge(1,1,0,3, _("Printing Date"),style_bold)
        row = 2
        row +=2
        worksheet.write_merge(2,2,0,3, datetime.now().strftime('%d-%m-%Y'))
        worksheet.write_merge(row,row,0,3, _("Budget"), style_border_table_top)
        worksheet.write_merge(row,row,4,4, _("Code"), style_border_table_top)
        worksheet.write_merge(row,row,5,8, _("Resource"), style_border_table_top)
        worksheet.write_merge(row,row,9,9, _("Type"), style_border_table_top)
        worksheet.write_merge(row,row,10,10, _("Template"), style_border_table_top)
        col = 11
        periods = []
        for par in date_pares:
            period = " %s-%s"%(par.month,par.year)
            periods.append({'period': period})
            worksheet.write_merge(row,row,col,col, _("Quant") + period , style_border_table_top)
            col += 1
        row += 1
        summary = {'resources': []}
        for budget in self.budget_ids:
            resources = budget.concept_ids.filtered_domain([('type', 'in', ('labor', 'equip'))])
            products = resources.mapped('product_id')
            for product in products:
                template_qty = templates.line_ids.filtered_domain([('product_id','=',product.id)]).quantity or 0
                worksheet.write_merge(row, row, 0, 3, budget.display_name, style_border_table_details)
                worksheet.write_merge(row, row, 4, 4, product.default_code, style_border_table_details)
                worksheet.write_merge(row, row, 5, 8, product.name, style_border_table_details)
                worksheet.write_merge(row, row, 9, 9, _(RESOURCE_TYPE[product.resource_type]) , style_border_table_details)
                worksheet.write_merge(row, row, 10, 10, template_qty, style_border_table_details)
                col = 11
                filtered_resources = resources.filtered_domain([('product_id','=',product.id)])
                date_from = datetime(self.date_from.year, self.date_from.month, self.date_from.day, 12, 00, 00)
                date_to = datetime(self.date_to.year, self.date_to.month, self.date_to.day, 12, 00, 00)
                date_from = datetime.strftime(date_from, '%Y-%m-%d')
                date_to = datetime.strftime(date_to, '%Y-%m-%d')
                for par in date_pares:
                    resource_ids = []
                    for res in filtered_resources:
                        acs_date_start = res.acs_date_start if res.acs_date_start else res.parent_id.acs_date_start
                        acs_date_end = res.acs_date_end if res.acs_date_end else res.parent_id.acs_date_end
                        if acs_date_start and acs_date_end and \
                            (((acs_date_start.year == par.year and acs_date_start.month == par.month) or
                                                                 ((acs_date_end.year == par.year and acs_date_end.month == par.month)))
                        or (acs_date_start <= par and acs_date_end >= par)):
                            exe_dates = res.resource_execution_dates()
                            if (date_from in exe_dates) or (date_to in exe_dates):
                                resource_ids.append(res.id)
                    search_in_resources = filtered_resources.filtered_domain([('id','in',resource_ids)])
                    if search_in_resources:
                        quantity = self.get_max_resource_qty(search_in_resources)
                    else:
                        quantity = 0
                    worksheet.write_merge(row,row,col,col, quantity, style_border_table_details)
                    col += 1
                    par_info = " %s-%s"%(par.month,par.year)
                    summary = self.include_in_summary(summary, par_info, product, quantity,template_qty)
                row += 1
            row += 1
        if len(summary['resources']) > 0:
            worksheet.write_merge(row, row, 0, 3, _("TOTALS"), style_border_table_top)
            worksheet.write_merge(row, row, 4, 4, _("Code"), style_border_table_top)
            worksheet.write_merge(row, row, 5, 8, _("Resource"), style_border_table_top)
            worksheet.write_merge(row, row, 9, 9, _("Type"), style_border_table_top)
            worksheet.write_merge(row, row, 10, 10, _("Template"), style_border_table_top)
            col = 11
            for par in date_pares:
                period = " %s-%s" % (par.month, par.year)
                worksheet.write_merge(row, row, col, col, _("Total ") + period, style_border_table_top)
                col += 1
            row += 1
            for element in summary['resources']:
                worksheet.write_merge(row, row, 0, 3, "", style_border_table_details)
                worksheet.write_merge(row, row, 4, 4, element['product'].default_code, style_border_table_details)
                worksheet.write_merge(row, row, 5, 8, element['product'].name, style_border_table_details)
                worksheet.write_merge(row, row, 9, 9, _(RESOURCE_TYPE[element['product'].resource_type]),
                                      style_border_table_details)
                worksheet.write_merge(row, row, 10, 10, element['template_qty'], style_border_table_details)
                col = 11
                for period in element['periods']:
                    worksheet.write_merge(row, row, col, col, period['quantity'], style_border_table_details)
                    col += 1

                row +=1


        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        data_b64 = base64.encodebytes(data)
        doc = self.env['ir.attachment'].create({
            'name': '%s.xls' % (file_name),
            'datas': data_b64,
        })

        return {
            'type': "ir.actions.act_url",
            'url': "web/content/?model=ir.attachment&id=" + str(
                doc.id) + "&filename_field=name&field=datas&download=true&filename=" + str(doc.name),
            'target': "self",
            'no_destroy': False,
        }
