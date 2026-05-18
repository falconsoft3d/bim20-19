# coding: utf-8
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BimApuWizard(models.TransientModel):
    _name = 'bim.apu.wizard'
    _description = 'Apu Wizard'

    template_id = fields.Many2one(comodel_name="bim.apu.template", string="Apu Template", required=True)
    project_id = fields.Many2one('bim.project', "Concept", required=True)
    obs = fields.Text('Notes', default="")
    val_n = fields.Float("N", digits="BIM qty")
    val_x = fields.Float("X", digits="BIM qty")
    val_y = fields.Float("Y", digits="BIM qty")
    val_z = fields.Float("Z", digits="BIM qty")
    variable_ids = fields.One2many('bim.apu.wizard.variable', 'wizard_id', string="Variables")
    sale_id = fields.Many2one('sale.order', "Sale Order")
    # def do_action(self):

    @api.onchange('template_id')
    def onchange_template_id(self):
        self.variable_ids = [(5, 0, 0)]
        variables = []
        if self.template_id:
            if not self.sale_id:
                self.val_n = self.template_id.val_n
            self.val_x = self.template_id.val_x
            self.val_y = self.template_id.val_y
            self.val_z = self.template_id.val_z
            self.obs = self.template_id.obs
            for variable in self.template_id.variable_ids:
                variables.append((0, 0, {'name': variable.name, 'value': variable.value, 'variable': variable.variable,'product_uom': variable.product_uom.id if variable.product_uom else False}))
        self.variable_ids = variables


    def do_action(self):
        budget_id = self.template_id.create_budget(self.project_id)
        self.template_id.create_chapters(budget_id)
        for line in self.template_id.line_ids.filtered_domain([('type', '=', 'apu')]):
            if not line.formula:
                quantity = line.qty_calc
            else:
                quantity = self._compute_formula(line.formula)
            chapters = budget_id.concept_ids.filtered_domain([('code', '=', line.parent_id.code),('type', '=', 'chapter')])
            if chapters and quantity > 0:
                # departure = line.apu_id._helper_create_departure_from_template(budget_id, chapters[0], quantity)
                line.apu_id._create_departure_with_parameters(chapters[0])
        if self.sale_id:
            self.sale_id._assign_assets_to_budget(budget_id)
        return budget_id.action_view_budget()

    def _compute_formula(self,formula):
        value = 0
        if formula:
            try:
                N = n = self.val_n
                X = x = self.val_x
                Y = y = self.val_y
                Z = z = self.val_z
                for variable in self.variable_ids:
                    formula = formula.replace(variable.variable.upper(), str(variable.value))
                    formula = formula.replace(variable.variable.lower(), str(variable.value))
                print(formula)
                value = eval(str(formula).replace(',', '.'))
            except Exception as e:
                print(e)
                raise UserError(
                    _('Define a formula based on the Apu Template description. Division by zero is not allowed'))
        return value

    def get_type(self,line):
        if line.type == 'concept':
            type = 'departure'
        else:
            if line.product_id.resource_type == 'M':
                type = 'material'
            elif line.product_id.resource_type == 'H':
                type = 'labor'
            elif line.product_id.resource_type == 'Q':
                type = 'equip'
            else:
                type = 'aux'
        return type

class BimApuWizardVariable(models.TransientModel):
    _name = 'bim.apu.wizard.variable'
    _description = 'Apu Wizard'

    wizard_id = fields.Many2one('bim.apu.wizard', string="Wizard")
    variable = fields.Char("Variable", required=True, readonly=True)
    name = fields.Char("Description", required=True, readonly=True)
    value = fields.Float("Value")
    product_uom = fields.Many2one('uom.uom', string='UdM', readonly=True)



