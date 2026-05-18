import base64
import io

import xlwt
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BimBudgetHistoryCompare(models.TransientModel):
    _name = 'bim.budget.history.compare.wizard'
    _description = 'Budgets History comparator'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ids = self.env.context.get('active_ids', [])
        budgets = self.env['bim.budget.history'].browse(ids)
        if len(budgets) != 2:
            raise ValidationError(_('You must choose only 2 Budgets to be able to compare.'))
        res.update({
            'origin_budget_id': budgets[0].id,
            'compare_budget_id': budgets[1].id,
        })
        return res

    origin_budget_id = fields.Many2one('bim.budget.history', string='Origin Budget History', readonly=True)
    compare_budget_id = fields.Many2one('bim.budget.history', string='Budget History to Compare', readonly=True)
    compare = fields.Selection([('chapter', 'Chapters'),
                                ('departure', 'Budget Items'),
                                ('both', 'All')], 'Compare', default='both', required=True)
    price = fields.Boolean('Price', default=True)
    quantity = fields.Boolean('Quantity', default=True)

    def switch_budgets(self):
        """ Cambia entre los presupuestos a comparar """
        self.origin_budget_id, self.compare_budget_id = self.compare_budget_id, self.origin_budget_id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Compare Budget History"),
            'res_model': 'bim.budget.history.compare.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }

    def print_excel(self):
        if not self.price and not self.text and not self.quantity:
            raise ValidationError(_('You must choose at least one option to compare out of price, text or quantity.'))

        # Estilos a usar
        normal_right = xlwt.easyxf('align: wrap yes, horiz right;')
        bold_left = xlwt.easyxf('align: wrap yes, horiz left; font: bold on;')
        red_right = xlwt.easyxf('align: wrap yes, horiz right; font: colour red;')
        separator = xlwt.easyxf('pattern: pattern solid, fore_colour periwinkle;')

        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet(_('Comparison'))

        # Anchos
        sheet.col(0).width = 256 * 20
        sheet.col(1).width = 256 * 30
        sheet.col(2).width = 256 * 10
        sheet.col(3).width = 256 * 10
        sheet.col(4).width = sheet.col(5).width = sheet.col(6).width = sheet.col(7).width = sheet.col(8).width = sheet.col(9).width = 1
        sheet.col(10).width = 256
        sheet.col(11).width = 256 * 30
        sheet.col(12).width = 256 * 10
        sheet.col(13).width = 256 * 10
        sheet.col(14).width = sheet.col(15).width = sheet.col(16).width = sheet.col(17).width = sheet.col(18).width = sheet.col(19).width = 1
        sheet.col(20).width = 256
        sheet.col(21).width = 256 * 30
        sheet.col(22).width = 256 * 10
        sheet.col(23).width = 256 * 10

        sheet.write_merge(1, 1, 0, 20,
                          "Presupuesto: %s" % (self.origin_budget_id.budget_id.display_name),
                          bold_left)
        # Cabecera
        sheet.write(3, 2, _('Quant'), bold_left)
        sheet.write(3, 3, _('Price'), bold_left)
        sheet.write(3, 10, '', separator)
        sheet.write(3, 12, _('Quant'), bold_left)
        sheet.write(3, 13, _('Price'), bold_left)
        sheet.write(3, 20, '', separator)
        sheet.write(3, 22, _('Quant'), bold_left)
        sheet.write(3, 23, _('Price'), bold_left)
        sheet.write_merge(4,4, 0,9, "%s - %s"%(self.origin_budget_id.display_name,self.origin_budget_id.description), bold_left)
        sheet.write(4, 10, '', separator)
        sheet.write_merge(4,4, 11,19, "%s - %s"%(self.compare_budget_id.display_name,self.compare_budget_id.description), bold_left)
        sheet.write(4, 20, '', separator)
        sheet.write(4, 21, _('Difference'), bold_left)

        row = 5
        # Buscamos códigos de conceptos en común (los repetidos dañan todo)
        if self.compare == 'both':
            types = ['departure','chapter']
        else:
            types = [self.compare]
        for origin_concept in self.origin_budget_id.history_line_ids.filtered_domain([('concept_id','!=',False)]):
            if origin_concept.concept_id.type not in types:
                continue
            diferences1 = []
            diferences2 = []
            origin_quantity = origin_concept.quantity
            origin_price = origin_concept.price
            sheet.write(row, 0, origin_concept.concept_id.code, bold_left)
            sheet.write(row, 1, origin_concept.concept_id.name, bold_left)
            sheet.write(row, 2, origin_quantity, normal_right)
            sheet.write(row, 3, origin_price, normal_right)
            # No olvidemos los separadores
            sheet.write(row, 10, '', separator)
            sheet.write(row, 20, '', separator)
            # Líneas de medición

            for compare_concept in self.compare_budget_id.history_line_ids.filtered_domain([('concept_id','!=',False)]):
                if compare_concept.concept_id.type not in types:
                    continue
                if origin_concept.concept_id.id == compare_concept.concept_id.id:
                    # Hora de buscar diferencias

                    diferences1.append((compare_concept.concept_id.name, bold_left))
                    diferences2.append((compare_concept.concept_id.name, bold_left))

                    compare_quantity = compare_concept.quantity
                    compare_price = compare_concept.price

                    if self.quantity and origin_quantity != compare_quantity:
                        diferences1.append((compare_quantity, red_right))
                        diferences2.append((compare_quantity - origin_quantity, red_right))
                    else:
                        diferences1.append((compare_quantity, normal_right))
                        diferences2.append((compare_quantity - origin_quantity, normal_right))

                    if self.price and origin_price != compare_price:
                        diferences1.append((compare_price, red_right))
                        diferences2.append((compare_price - origin_price, red_right))
                    else:
                        diferences1.append((compare_price, normal_right))
                        diferences2.append((compare_price - origin_price, normal_right))

                    # Líneas de medición
                    break  # Encontré el que coincide en código, no buscaré mas...

            if diferences1:
                for i, (value, style) in enumerate(diferences1, 11):
                    sheet.write(row, i, value, style)
                for i, (value, style) in enumerate(diferences2, 21):
                    sheet.write(row, i, value, style)

            # pasamos a la siguiente fila
            row += 1

        if row == 2:
            raise ValidationError(_('There are no common concepts to compare.'))

        # Unos cuantos separadores mas, hasta hacer al menos 50
        for i in range(row, 53):
            sheet.write(i, 10, '', separator)
            sheet.write(i, 20, '', separator)

        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)

        filename = '_%s_%s.xls' % (self.origin_budget_id.display_name, self.compare_budget_id.display_name)
        filename = _("Comparison") + filename
        attach_vals = {
            'name': filename,
            'datas': base64.b64encode(stream.getvalue()),
            'store_fname': filename,
        }
        doc_id = self.env['ir.attachment'].create(attach_vals)
        return {
            'name': filename,
            'type': 'ir.actions.act_url',
            'url': 'web/content/%d?download=true' % doc_id.id,
            'close_on_report_download': True,
            'target': 'self',
        }
