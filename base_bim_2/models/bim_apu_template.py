# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimApuTemplate(models.Model):
    _description = "Bim Apu Template"
    _name = 'bim.apu.template'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code', default='New')
    desc = fields.Char('Description')
    obs = fields.Text('Notes', default="")
    val_n = fields.Float("N", digits="BIM qty")
    val_x = fields.Float("X", digits="BIM qty")
    val_y = fields.Float("Y", digits="BIM qty")
    val_z = fields.Float("Z", digits="BIM qty")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    image = fields.Image("Image Template", max_width=1920, max_height=1920)
    line_ids = fields.One2many(comodel_name="bim.apu.template.line", inverse_name="template_id", string="Lines", copy=True)
    variable_ids = fields.One2many(comodel_name="bim.apu.template.variable", inverse_name="template_id", string="Variables", copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bim.apu.template') or 'New'
        return super().create(vals_list)

    @api.onchange('line_ids')
    def onchange_set_lines(self):
        if self.line_ids:
            line_parent = False
            for line in self.line_ids:
                if line.type == 'concept':
                    line_parent = line.id
                else:
                    line.parent_id = line_parent

                if line.sequence == 0:
                    line.sequence = len(self.line_ids)

    def name_get(self):
        res = super(BimApuTemplate, self).name_get()
        result = []
        for element in res:
            project_id = element[0]
            cod = self.browse(project_id).name
            desc = self.browse(project_id).desc
            name = cod and '[%s] %s' % (cod, desc) or '%s' % desc
            result.append((project_id, name))
        return result

    def create_budget(self, project_id):
        if not project_id:
            raise UserError(_("You must select a project"))
        budget = self.env['bim.budget'].create({
            'name': self.desc,
            'note': self.obs,
            'project_id': project_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        })
        return budget

    def create_chapters(self, budget):
        if not budget:
            raise UserError(_("You must select a budget"))
        for line in self.line_ids.filtered_domain([('type', '=', 'chapter')]):
                budget.concept_ids.create({
                    'budget_id': budget.id,
                    'name': line.name,
                    'type': line.type,
                    'code': line.code,
                    'sequence': line.sequence,
                })
    def create_departures(self, budget):
        for line in self.line_ids.filtered_domain([('type', '=', 'apu')]):
            chapter = budget.concept_ids.filtered_domain([('code', '=', line.parent_id.code),('type','=','chapter')])
            if chapter:
                line.apu_id._helper_create_departure_from_template(budget, chapter, quantity=1)


class BimApuTemplateLine(models.Model):
    _name = 'bim.apu.template.line'
    _description = 'Apu Template Lines'
    _order = 'sequence'

    code = fields.Char("Code")
    name = fields.Char("Description")
    sequence = fields.Integer(string='Sequence',required=True, default=0)
    formula = fields.Char("Formulas / Value")
    apu_id = fields.Many2one(comodel_name="bim.concept.template", string="Apu")
    qty_calc = fields.Float('Quantity', help="Quantity", compute='_compute_quantity', digits='BIM qty')
    template_id = fields.Many2one(comodel_name="bim.apu.template", string="Template")
    product_uom = fields.Many2one('uom.uom', string='UdM')
    parent_id = fields.Many2one('bim.apu.template.line', string='Parent', compute='_compute_parent')
    parent_code = fields.Char('Parent Code')
    children_ids = fields.One2many(string="Child Lines", comodel_name='bim.apu.template.line', inverse_name='parent_id')
    type = fields.Selection([
        ('apu','Apu'),
        ('chapter','Chapter')], required=True, default='chapter')

    @api.onchange('type')
    def _onchange_type(self):
        if self.type != 'chapter':
            self.formula = False

    @api.onchange('name')
    def _onchange_name(self):
        if self.apu_id:
            self.product_uom = self.apu_id.uom_id.id

    @api.onchange('apu_id')
    def onchange_apu_id(self):
        self.name = self.apu_id.name
        if self.apu_id.code:
            self.code = self.apu_id.code
        else:
            self.code = "00"

    @api.depends('type', 'template_id', 'parent_code')
    def _compute_parent(self):
        for record in self:
            lines_parent = record.template_id.line_ids.filtered(lambda l: l.type == 'chapter')
            parent_id = False
            if record.type == 'apu':
                if record.parent_code:
                    parent_id = lines_parent.filtered(lambda l: l.code == record.parent_code).id
                else:
                    list_res = []
                    for parent in lines_parent:
                        if parent.sequence < record.sequence:
                            tuple_vals = (parent.sequence, parent.id)
                            list_res.append(tuple_vals)
                    if list_res:
                        list_res.sort(key=lambda tup: tup[0],reverse=True)
                        parent_id = list_res[0][1]
                    else:
                        parent_id = False
            record.parent_id = parent_id

    @api.depends('formula', 'template_id','template_id.variable_ids','template_id.variable_ids.value','template_id.variable_ids.variable'
                 )
    def _compute_quantity(self):
        for record in self:
            if record.formula:
                try:
                    N = n = record.template_id.val_n
                    X = x = record.template_id.val_x
                    Y = y = record.template_id.val_y
                    Z = z = record.template_id.val_z
                    formula = record.formula
                    for variable in record.template_id.variable_ids:
                        formula = formula.replace(variable.variable.upper(), str(variable.value))
                        formula = formula.replace(variable.variable.lower(), str(variable.value))
                    record.qty_calc = eval(str(formula).replace(',','.'))
                except Exception as e:
                    print(e)
                    raise UserError(_('Define a formula based on the Apu Template description. Division by zero is not allowed'))
            else:
                record.qty_calc = 1

class BimApuTemplateVariable(models.Model):
    _name = 'bim.apu.template.variable'
    _description = 'Apu Template Variable'
    _order = 'sequence'

    _sql_constraints = [
        ('unique_template_variable',
         'unique(variable,template_id)',
         'Variable must be unique per template!'),
    ]

    template_id = fields.Many2one(comodel_name="bim.apu.template", string="Template")
    sequence = fields.Integer(string='Sequence', default=10)
    variable = fields.Char("Variable", required=True, size=1)
    name = fields.Char("Description", required=True)
    value = fields.Float("Value")
    product_uom = fields.Many2one('uom.uom', string='UdM')

    @api.constrains('variable')
    def _check_variable(self):
        for variable in self:
            if variable.variable in ('N', 'n', 'X', 'x', 'Y', 'y', 'Z', 'z') or not variable.variable.isalpha():
                raise UserError(_('Variable not allowed. Available (A-z / a - z), without repeat'))
            if not variable.variable.isupper():
                variable.variable = variable.variable.upper()




