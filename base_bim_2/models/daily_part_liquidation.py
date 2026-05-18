# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class DailyPartLiquidation(models.Model):
    _description = "Daily Part Liquidation"
    _name = 'daily.part.liquidation'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Code', default="New", copy=False)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Create Date', readonly=True, index=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    project_id = fields.Many2one('bim.project', string='Project')
    budget_id = fields.Many2one('bim.budget', string='Budget')
    stage_id = fields.Many2one('bim.budget.stage', string='Stage')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('read', 'Read'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='State', readonly=True, copy=False, index=True, tracking=True, default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('daily.part.liquidation') or 'New'
        return super().create(vals_list)


    diary_part_ids = fields.Many2many('diary.part', string='Diary Part')
    line_ids = fields.One2many('daily.part.liquidation.line', 'daily_part_liquidation_id', string='Lines')


    def action_done(self):
        self.write({'state': 'done'})


    def action_draft(self):
        for diary_part in self.diary_part_ids:
            diary_part.daily_part_liquidation_id = False

        self.write({'state': 'draft'})


    def action_read(self):
        # Limpiamos las líneas
        self.line_ids.unlink()

        # validamos que tengas líneas de diario de parte
        if not self.diary_part_ids:
            raise ValidationError(_('You must select Diary Part'))

        # recorremos los partes insertando las lineas que no estan por el PCP y la cantidad
        for diary_part in self.diary_part_ids:
            for line in diary_part.lines_ids:
                if not line.bim_pcp_id:
                    raise ValidationError(_('You must select PCP in the Diary Part'))


                # revisamos que ya exista el pcp en una linea para no agregarlos sino sumar la qty
                exist = self.line_ids.filtered(lambda x: x.bim_pcp_id == line.bim_pcp_id)
                if exist:
                    exist.qty += line.qty
                    exist.qty_certif += line.qty_certif
                else:
                    self.line_ids = [(0, 0, {
                        'bim_pcp_id': line.bim_pcp_id.id,
                        'qty': line.qty,
                        'qty_certif': line.qty,
                        'daily_part_liquidation_id': self.id,
                        'concepts_id' : line.concepts_id.id,
                    })]

            diary_part.daily_part_liquidation_id = self.id


        self.write({'state': 'read'})

class DailyPartLiquidationLine(models.Model):
    _description = "Daily Part Liquidation Line"
    _name = 'daily.part.liquidation.line'

    daily_part_liquidation_id = fields.Many2one('daily.part.liquidation', string='Daily Part Liquidation')
    bim_pcp_id = fields.Many2one('bim.pcp', string='PCP')
    concepts_id = fields.Many2one('bim.concepts', string='Concepts')
    qty = fields.Float('Qty')
    qty_certif = fields.Float('Qty Certif')
    budget_id = fields.Many2one('bim.budget', string='Budget', related='daily_part_liquidation_id.budget_id', store=True)