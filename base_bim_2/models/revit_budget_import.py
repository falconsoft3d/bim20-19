# -*- coding: utf-8 -*-
# Part of Bim20. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
from io import StringIO
import logging
_logger = logging.getLogger(__name__)

class RevitBudgetImport(models.Model):
    _description = "Revit Budget Import"
    _name = 'revit.budget.import'
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']

    name = fields.Char('Code', default='New')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('revit.budget.import') or 'New'
        return super().create(vals_list)

    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, required=True)
    file = fields.Binary("File", required=True)
    file_name = fields.Char("File Name")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('imported', 'Imported'),
    ], string='Status', default='draft', tracking=True)

    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, tracking=True)
    budget_id = fields.Many2one('bim.budget', string='Budget', tracking=True)
    bim_massive_certification_by_line_id = fields.Many2one('bim.massive.certification.by.line', string='Certification', tracking=True)

    file_type = fields.Selection([
        ('revit-txt', 'Revit TXT'),
    ], string='Type', default='revit-txt', tracking=True)

    type_action = fields.Selection([
        ('create_new_budget', 'Create New Budget'),
        ('create_new_certification', 'Create New Certification'),
    ], string='Action Type', default='create_new_budget', tracking=True)

    line_ids = fields.One2many('revit.budget.import.line', 'revit_budget_import_id', string='Import Lines')


    def load_data(self):
        self.ensure_one()
        if self.file_type == 'revit-txt':
            return self._load_revit_txt()
        else:
            raise UserError(_("Unsupported file type."))

    def _clean_number(self, value):
        """Limpia valores como '4 m²', '0.53 m³', '1 m', '' """
        if not value or value.strip() == '':
            return 0.0

        # Quitar unidades y espacios
        cleaned = (
            value.replace("m²", "")
            .replace("m³", "")
            .replace("m", "")
            .replace(",", ".")
            .strip()
        )

        try:
            return float(cleaned)
        except:
            return 0.0


    def to_draft(self):
        self.state = 'draft'

    def _load_revit_txt(self):
        """Carga archivo TXT/CSV exportado desde Revit"""
        self.ensure_one()

        if not self.file:
            raise UserError(_("Debe adjuntar un archivo."))

        # Leer archivo desde el Binary
        content = base64.b64decode(self.file).decode("utf-8", errors="ignore")
        f = StringIO(content)
        reader = csv.reader(f)

        # Saltar las primeras líneas vacías o headers erróneos
        header = next(reader, [])

        """
        expected = ["Description", "Assembly Code", "Count", "Material: Area", "Material: Volume", "Length"]
        if len(header) < 6:
            raise UserError(_("El archivo no tiene el formato esperado."))
        """


        # limpiamos las lineas
        self.line_ids.unlink()

        # Procesar líneas
        for row in reader:
            if len(row) < 6:
                continue

            description = row[0].strip()
            code = row[1].strip()
            count = self._clean_number(row[2])
            area = self._clean_number(row[3])
            volume = self._clean_number(row[4])
            length = self._clean_number(row[5])
            advance = self._clean_number(row[6])

            _logger.info("Importing line: %s | %s | %s | %s | %s | %s | %s", description, code, count, area, volume, length, advance)

            if not code:
                # Saltar líneas vacías
                continue

            # reviso que no exista ya la línea con ese codigo en esta importación
            existing_line = self.env['revit.budget.import.line'].search([
                ('revit_budget_import_id', '=', self.id),
                ('code', '=', code),
            ], limit=1)
            if not existing_line:
                # Crear línea de importación

                bim_concept_template_id = self.env['bim.concept.template'].search([('bim_id', '=', code)], limit=1)
                line = self.env['revit.budget.import.line'].create({
                    'revit_budget_import_id': self.id,
                    'code': code,
                    'count': count,
                    'area': area,
                    'volume': volume,
                    'length': length,
                    'advance': advance,
                    'decription': description,
                    'bim_concept_template_id': bim_concept_template_id.id if bim_concept_template_id else False,
                    'bim_uom': bim_concept_template_id.bim_uom if bim_concept_template_id else 'Volume',
                })
            else:
                # Actualizar línea existente sumando los valores
                existing_line.count += count
                existing_line.area += area
                existing_line.volume += volume
                existing_line.length += length
                existing_line.advance += advance

        self.state = "loaded"
        return {
            "effect": {
                "fadeout": "slow",
                "message": _("Archivo Revit importado correctamente."),
                "type": "rainbow_man",
            }
        }

    def insert(self):
        if self.type_action == 'create_new_budget':
            if not self.budget_id:
                raise UserError(_("No se ha seleccionado un presupuesto para insertar las líneas."))

            for line in self.line_ids:
                if line.bim_concept_template_id:
                    if line.bim_concept_template_id.bim_uom == 'Count':
                        quantity = line.count
                    elif line.bim_concept_template_id.bim_uom == 'Area':
                        quantity = line.area
                    elif line.bim_concept_template_id.bim_uom == 'Volume':
                        quantity = line.volume
                    elif line.bim_concept_template_id.bim_uom == 'Length':
                        quantity = line.length
                    else:
                        quantity = 0.0
                    if self.type_action == 'create_new_budget':
                        if self.budget_id:
                            departure_id = line.bim_concept_template_id._create_departure_from_template(
                                self.budget_id,
                                quantity,
                            )

        if self.type_action == 'create_new_certification':
            _logger.info("Inserting lines into certification...")
            if not self.bim_massive_certification_by_line_id:
                raise UserError(_("No se ha seleccionado una certificación para insertar las líneas."))

            all_apus = self.line_ids.mapped('bim_concept_template_id').ids
            _logger.info("all_apus: %s", all_apus)



            bim_concepts_ids = self.env['bim.concepts'].search([
                ('concept_template_id', 'in', all_apus),
                ('budget_id', '=', self.bim_massive_certification_by_line_id.budget_id.id),
            ])

            _logger.info("bim_concepts_ids found: %s", bim_concepts_ids.ids)

            self.bim_massive_certification_by_line_id.only_concept_ids = bim_concepts_ids
            self.bim_massive_certification_by_line_id.action_load_lines()

            for concep in bim_concepts_ids:
                # buscamos la primera partida en la cerfiticación
                cert_line = self.bim_massive_certification_by_line_id.certification_stage_ids.filtered(lambda l: l.concept_id == concep)
                cert_line = cert_line and cert_line[0] or False
                if cert_line:
                    qty = 0
                    bim_concept_template_id = concep.concept_template_id
                    # buscamos la línea importada
                    import_line = self.line_ids.filtered(lambda l: l.bim_concept_template_id == bim_concept_template_id)
                    if import_line:
                        qty = import_line.advance
                    cert_line.quantity_to_cert = qty


        self.state = 'imported'




class RevitBudgetImportLine(models.Model):
    _description = "Revit Budget Import Line"
    _name = 'revit.budget.import.line'

    revit_budget_import_id = fields.Many2one('revit.budget.import', string='Revit Budget Import', required=True, ondelete='cascade')
    code = fields.Char('Code', required=True)
    decription = fields.Char('Description')
    count = fields.Float('Count', default=0.0)
    area = fields.Float('Area', default=0.0)
    volume = fields.Float('Volume', default=0.0)
    length = fields.Float('Length', default=0.0)
    advance = fields.Float('Avance (Cant)', default=0.0)
    bim_concept_template_id = fields.Many2one('bim.concept.template', string='APU')
    bim_uom = fields.Selection([
        ('Count', 'Count'),
        ('Area', 'Area'),
        ('Volume', 'Volume'),
        ('Length', 'Length'),
    ],
        string="BIM UOM", default='Volume')
