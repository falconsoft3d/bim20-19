import io
import json
import re

import xlwt

from odoo import http
from odoo.tools import html_escape


class MainController(http.Controller):

    _INT_RE = re.compile(r'^[-+]?\d+$')
    _NUM_RE = re.compile(r'^[-+]?\d[\d\s.,]*$')

    @http.route('/tree_excel_export/download', type='http', auth='user')
    def download(self, header, body, name, **kwargs):
        try:
            header = header.split('#;')
            body = [i.split('~;') for i in body.split('#;')]
            excel = self.generate_excel(header, body)
        except Exception as e:
            se = http.serialize_exception(e)
            error = {
                'code': 200,
                'message': "Odoo Server Error",
                'data': se
            }
            return http.request.make_response(html_escape(json.dumps(error)))
        httpheaders = [('Content-Type', 'application/xls'), ('Content-Length', len(excel)), ('Content-Disposition', f'attachment; filename="{name or "export"}.xls"'), ]
        return http.request.make_response(excel, headers=httpheaders)

    def generate_excel(self, header, body):
        workbook = xlwt.Workbook()
        header_style = xlwt.easyxf('font: bold true')
        int_style = xlwt.easyxf(num_format_str='#,##0')
        float_style = xlwt.easyxf(num_format_str='#,##0.00')
        sheet = workbook.add_sheet('hoja')
        header_tmp = []
        for element in header:
            if element not in header_tmp:
                header_tmp.append(element)
        header = header_tmp
        for i, th in enumerate(header):
            sheet.write(0, i, th, header_style)

        for i, tr in enumerate(body, 1):
            for j, td in enumerate(tr):
                number = self._parse_number(td)
                if number is None:
                    sheet.write(i, j, td)
                elif isinstance(number, int):
                    sheet.write(i, j, number, int_style)
                else:
                    sheet.write(i, j, number, float_style)

        with io.BytesIO() as stream:
            workbook.save(stream)
            stream.seek(0)
            excel = stream.getvalue()
        return excel

    def _parse_number(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value

        raw = str(value).strip().replace('\xa0', '').replace(' ', '')
        if not raw:
            return None
        if not self._NUM_RE.match(raw):
            return None
        if self._INT_RE.match(raw):
            try:
                return int(raw)
            except ValueError:
                return None

        if ',' in raw and '.' in raw:
            decimal_sep = ',' if raw.rfind(',') > raw.rfind('.') else '.'
            thousand_sep = '.' if decimal_sep == ',' else ','
            normalized = raw.replace(thousand_sep, '').replace(decimal_sep, '.')
        elif ',' in raw:
            if raw.count(',') > 1:
                normalized = raw.replace(',', '')
            else:
                normalized = raw.replace(',', '.')
        else:
            if raw.count('.') > 1:
                normalized = raw.replace('.', '')
            else:
                normalized = raw

        if normalized.count('.') > 1:
            return None

        try:
            return float(normalized)
        except ValueError:
            return None
