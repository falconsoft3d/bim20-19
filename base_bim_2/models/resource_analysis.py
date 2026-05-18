# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import base64
import io

try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
except (ImportError, IOError):
    plt = False
    _logger.info('Missing external dependency matplotlib.')

class ResourceAnalysis(models.Model):
    _description = "Resource Analysis"
    _name = 'resource.analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Code', required=True, copy=False, readonly=True, index=True,default='New')
    title = fields.Char('Title', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    project_id = fields.Many2one('bim.project', string='Project', required=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', required=True)
    lines_ids = fields.One2many('resource.analysis.line', 'analysis_id', string='Lines')
    analysis_graph = fields.Binary(readonly=True)

    type = fields.Selection([
        ('mo_percent', 'Curva S MO en %'),
        ('mo_qty', 'Curva S MO en Cant'),
    ], string='Type', required=True, default='mo_percent', copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('resource.analysis') or 'New'
        return super().create(vals_list)


    def update_budget_graph(self):
        if not plt:
            raise UserError(_("Matplotlib is not installed. Please install it to generate graphs."))

        for record in self:
            if not record.lines_ids:
                raise UserError(_("No data available to generate the graph."))

            stages = []
            pln_vals = []
            exc_vals = []

            cert_count = exc_count = pln_count = 0
            for stage in record.lines_ids:
                stages.append(stage.bim_budget_stage_id.name.replace('Stage', 'Etapa'))

                pln_vals.append(stage.value + pln_count)
                exc_vals.append(stage.value_r + exc_count)


                exc_count += stage.value
                pln_count += stage.value_r

            fig = plt.figure(figsize=(15, 5))
            ax = fig.add_subplot(111)

            ax.plot(stages, pln_vals, color='blue', marker='.', label=_('Valor Plan'))
            ax.plot(stages, exc_vals, color='red', marker='.', label=_('Valor Real'))
            plt.title(_('Análisis'), fontsize=14)
            plt.legend(loc='lower center', ncol=len(stages), bbox_to_anchor=(0.5, -0.2))
            plt.grid(True)
            figfile = io.BytesIO()
            plt.savefig(figfile, format='png', bbox_inches='tight', pad_inches=0)
            plt.clf()
            plt.cla()
            plt.close()
            figfile.seek(0)
            record.analysis_graph = base64.b64encode(figfile.getvalue())




    def load_data(self):
        self.lines_ids.unlink()

        if self.type == 'mo_percent' or self.type == 'mo_qty':
            for stage in self.budget_id.stage_ids:
                # Calculamos el total de horas de mano de obra
                t_mo = 0
                departure_ids = self.env['bim.concepts'].search([
                                        ('budget_id', '=', self.budget_id.id),
                                    ])

                for dep in departure_ids:
                    for rec in dep:
                        if rec.type == 'labor':
                            t_mo += dep.quantity * rec.quantity


                # Calculamos el coste planificado
                value = 0
                departure_ids = self.env['bim.concepts'].search([
                                        ('budget_id', '=', self.budget_id.id),
                                        ('acs_date_end', '>=', stage.date_stop),
                                        ('acs_date_end', '<=', stage.date_stop),
                                    ])


                for dep in departure_ids:
                    for rec in dep:
                        if rec.type == 'labor':
                            value += dep.quantity * rec.quantity


                # Calculamos el coste real
                value_r = 0

                diary_part_ids = self.env['diary.part'].search([
                                        ('date', '>=', stage.date_start),
                                        ('date', '<=', stage.date_stop),
                                        ('state', 'in', ['done']),
                                    ])

                value_r = sum([x.amount_total for x in diary_part_ids])


                value_percent = value / t_mo * 100
                value_r_percent = value_r / t_mo * 100

                if self.type == 'mo_percent':
                    _logger.info('value_percent: %s', value_percent)
                    self.env['resource.analysis.line'].create({
                        'analysis_id': self.id,
                        'bim_budget_stage_id': stage.id,
                        'date' : stage.date_stop,
                        'value': value_percent,
                        'value_r': value_r_percent,
                    })
                else:
                    _logger.info('value: %s', value)
                    self.env['resource.analysis.line'].create({
                        'analysis_id': self.id,
                        'bim_budget_stage_id': stage.id,
                        'date' : stage.date_stop,
                        'value': value,
                        'value_r': value_r,
                    })

class ResourceAnalysisLine(models.Model):
    _description = "Resource Analysis Line"
    _name = 'resource.analysis.line'

    analysis_id = fields.Many2one('resource.analysis', string='Analysis', required=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today)
    bim_budget_stage_id = fields.Many2one('bim.budget.stage', string='Stage', required=True)
    value = fields.Float('Value Plan', required=True)
    value_r = fields.Float('Value Real', required=True)