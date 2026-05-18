# -*- coding: utf-8 -*-
import csv
import base64
import random
import string
from odoo import api, fields, models
from odoo.exceptions import UserError

BLACKLIST = ['insert', 'update', 'delete']


class BimSqlReport(models.Model):
    _name = 'bim.sql.report'
    _description = 'Reporte SQL'
    _inherit = ['mail.activity.mixin', 'mail.thread']

    name = fields.Char(
        'Number', required=True, default='Nuevo', readonly=True)
    description = fields.Char('Description', required=True)
    type = fields.Selection([
        ('sql', 'SQL'),
        ('apus', 'Apus'),
        ('project', 'Project'),
        ('budget', 'Budget'),
    ], string='Type', default='sql', required=True, tracking=True)

    select_sql = fields.Text('SQL statement', tracking=True)
    project_id = fields.Many2one(
        'bim.project', 'Project', tracking=True)
    budget_id = fields.Many2one(
        'bim.budget', 'Budget', tracking=True)


    # Generate token 10 characters aleatory
    token = fields.Char('Token')
    active_token = fields.Boolean('Active token', default=False)
    url = fields.Char('URL', compute='_compute_url', store=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env.company.id)



    @api.depends('token')
    def _compute_url(self):
        for record in self:
            if record.token:
                param_web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                record.url = param_web_base_url + '/bim_report_sql/{}'.format(record.token)
            else:
                record.url = ""

    def check_select_sql(self):
        """."""
        for s in self.select_sql.split(' '):
            if s.lower() in BLACKLIST:
                raise UserError(
                    'The {} parameter is not supported.'.format(s.upper()))

    def header_csv(self, dicc):
        """."""
        return [key for key in dicc]

    def get_json_report(self):
        """."""
        self.check_select_sql()
        try:
            self.env.cr.execute(self.select_sql)
        except Exception as e:
            raise UserError(str(e))

        if self.env.cr.rowcount:
            res = self.env.cr.dictfetchall()
            return res
        raise UserError('Not results')


    def generate_report(self):
        """."""
        self.check_select_sql()
        try:
            self.env.cr.execute(self.select_sql)
        except Exception as e:
            raise UserError(str(e))

        if self.env.cr.rowcount:
            res = self.env.cr.dictfetchall()
            header = sorted(self.header_csv(res[0]))

            path = '/tmp/bim_report_sql.csv'
            with open(path, mode='w',encoding='UTF-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=header)
                writer.writeheader()
                for data in res:
                    for key, val in data.items():
                        if isinstance(val, str):
                            data[key] = val.strip()
                    writer.writerow(data)

            csv_file.close()
            arch = open(path, 'r').read()
            data = base64.b64encode(bytes(arch, 'utf-8'))
            attach_vals = {
                'name': 'report-sql.csv',
                'datas': data,
                'type': 'binary',
            }
            doc_id = self.env['ir.attachment'].create(attach_vals)

            return {
                'type': "ir.actions.act_url",
                'url': "web/content/?model=ir.attachment&id={}&filename_field"
                "=datas_fname&field=datas&download=true&filename={}".format(
                    doc_id.id, doc_id.name),
                'target': '_blank',
            }
        raise UserError('Not results')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Secuencia
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.sql.report'
                ) or 'Nuevo'

            # Token aleatorio (10 caracteres)
            if not vals.get('token'):
                vals['token'] = ''.join(
                    random.choices(string.ascii_uppercase + string.digits, k=10)
                )

        records = super().create(vals_list)
        return records