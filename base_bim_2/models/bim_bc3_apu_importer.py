# coding: utf-8
import base64
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BimBc3ApuImporter(models.Model):
    _name = 'bim.bc3.apu.importer'
    _description = 'BC3 APU Importer'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                        default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('parsed', 'Parsed'),
        ('processing', 'Processing'),
        ('done', 'Done'),
    ], string='State', default='draft', readonly=True)
    bc3_file = fields.Binary(string='BC3 File')
    filename = fields.Char(string='File Name')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.user.company_id)
    code_filter = fields.Char(
        string='Code Filter',
        help='Only import chapters/APUs whose code starts with this prefix '
             '(case-insensitive). Resources are always imported. Leave empty to import all.')
    action_type = fields.Selection([
        ('add_update', 'Create and update resources'),
        ('import_resource', 'Import resources'),
    ], string='Action Type', default='import_resource', required=True)
    product_id = fields.Many2one(
        'product.product', string='Default Product',
        default=lambda self: self.env.ref('base_bim_2.default_product', raise_if_not_found=False))
    batch_size = fields.Integer(string='Batch Size', default=50, required=True)
    line_ids = fields.One2many('bim.bc3.apu.importer.line', 'importer_id', string='Lines')
    total_lines = fields.Integer(string='Total APUs', compute='_compute_progress', store=True)
    processed_lines = fields.Integer(string='Processed', compute='_compute_progress', store=True)
    pending_lines = fields.Integer(string='Pending', compute='_compute_progress', store=True)
    progress = fields.Float(string='Progress %', compute='_compute_progress', store=True, digits=(5, 2))
    template_count = fields.Integer(string='APU Templates', compute='_compute_template_count')
    product_count = fields.Integer(string='Products', compute='_compute_product_count')
    log = fields.Text(string='Log', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bim.bc3.apu.importer') or _('New')
        return super().create(vals_list)

    def _compute_template_count(self):
        template_obj = self.env['bim.concept.template']
        for rec in self:
            rec.template_count = template_obj.search_count(
                [('bc3_importer_id', '=', rec.id)])

    def _compute_product_count(self):
        product_tmpl_obj = self.env['product.template']
        for rec in self:
            rec.product_count = product_tmpl_obj.search_count(
                [('bc3_importer_id', '=', rec.id)])

    def action_view_templates(self):
        self.ensure_one()
        action = self.env.ref('base_bim_2.action_bim_concept_template').sudo().read()[0]
        action['domain'] = [('bc3_importer_id', '=', self.id)]
        action['context'] = {'default_bc3_importer_id': self.id}
        return action

    def action_view_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Products'),
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('bc3_importer_id', '=', self.id)],
            'context': {'default_bc3_importer_id': self.id},
        }

    @api.depends('line_ids', 'line_ids.state', 'line_ids.ctype', 'line_ids.code')
    def _compute_progress(self):
        for rec in self:
            apu_lines = rec.line_ids.filtered(
                lambda l: l.ctype == 0 and '#' not in (l.code or ''))
            total = len(apu_lines)
            done = len(apu_lines.filtered(lambda l: l.state in ('done', 'skip', 'error')))
            rec.total_lines = total
            rec.processed_lines = done
            rec.pending_lines = total - done
            rec.progress = (done / total * 100.0) if total else 0.0

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_parse(self):
        """Parse BC3 file and create staging lines."""
        self.ensure_one()
        if not self.bc3_file:
            raise UserError(_("Please upload a BC3 file first."))

        self.line_ids.unlink()

        data = base64.b64decode(self.bc3_file).decode('latin-1')

        concepts = {}       # code -> {name, uom, price, ctype}
        decompositions = {}  # parent_code (clean) -> [(child_code, qty), ...]
        descriptions = {}   # code (clean) -> text

        pending = ''
        rows = data.split('\n')
        for idx, row in enumerate(rows):
            row = row.strip()
            if row and pending:
                row = pending + row
                pending = ''

            next_row = rows[idx + 1].strip() if idx + 1 < len(rows) else ''
            if row and next_row and next_row and next_row[0] != '~':
                pending = row
                continue
            pending = ''

            if not row or row[0] != '~' or len(row) < 2:
                continue

            rec_type = row[1]

            if rec_type == 'C':
                datas = row[3:].split('|')
                if len(datas) < 6:
                    continue
                code = datas[0]
                uom = datas[1]
                name = datas[2]
                price_str = datas[3]
                ctype_str = datas[5]
                try:
                    ctype = int(ctype_str)
                except (ValueError, TypeError):
                    ctype = 0
                try:
                    price = float(price_str.replace(',', '.')) if price_str.strip() else 0.0
                except (ValueError, AttributeError):
                    price = 0.0
                concepts[code] = {
                    'name': name, 'uom': uom, 'price': price, 'ctype': ctype}

            elif rec_type == 'D':
                try:
                    content = row[3:-1] if row.endswith('|') else row[3:]
                    datas = content.split('|')
                    parent_code = datas[0].replace('#', '')
                    if len(datas) < 2 or not datas[1]:
                        continue
                    parts = datas[1].split('\\')
                    while parts and not parts[-1].strip():
                        parts.pop()
                    children = []
                    for i in range(0, len(parts) - 2, 3):
                        child_code = parts[i].strip()
                        qty_str = parts[i + 2].strip().replace(',', '.')
                        try:
                            qty = float(qty_str) if qty_str else 0.0
                        except ValueError:
                            qty = 0.0
                        if child_code:
                            children.append([child_code, qty])
                    if children:
                        decompositions[parent_code] = children
                except Exception:
                    pass

            elif rec_type == 'T':
                datas = row[3:].split('|', 1)
                code = datas[0].replace('#', '').strip()
                text = datas[1].strip() if len(datas) > 1 else ''
                if code and text:
                    descriptions[code] = text

        # Classify codes
        chapter_clean = set()
        for code, cdata in concepts.items():
            if cdata['ctype'] == 0 and '#' in code and '##' not in code:
                chapter_clean.add(code.replace('#', ''))

        # Build APU -> chapter mapping
        apu_to_chapter = {}
        for parent_code, children in decompositions.items():
            if parent_code in chapter_clean:
                for child_code, _qty in children:
                    child_data = concepts.get(child_code)
                    if child_data and child_data['ctype'] == 0 and '#' not in child_code:
                        apu_to_chapter[child_code] = parent_code

        # Build staging lines
        vals_list = []
        seq = 10
        code_prefix = (self.code_filter or '').strip().upper()

        for code, cdata in concepts.items():
            if '##' in code:
                continue  # root record, skip
            # Apply code filter: only for chapters/APUs (ctype=0); resources always pass
            if code_prefix and cdata['ctype'] == 0:
                clean = code.replace('#', '').upper()
                if not clean.startswith(code_prefix):
                    continue
            children = decompositions.get(code.replace('#', ''))
            # Percentage concepts (%CI, %GG…) are resources, not APU templates;
            # mark as 'skip' so they are never queued as APUs but remain
            # available in all_lines_by_code for child-line lookups.
            line_state = 'skip' if code.startswith('%') else 'pending'
            vals_list.append({
                'importer_id': self.id,
                'sequence': seq,
                'code': code,
                'name': cdata['name'],
                'uom': cdata['uom'],
                'price': cdata['price'],
                'ctype': cdata['ctype'],
                'parent_code': apu_to_chapter.get(code, ''),
                'notes': descriptions.get(code.replace('#', ''), ''),
                'decomp_json': json.dumps(children) if children else '[]',
                'state': line_state,
            })
            seq += 10

        self.env['bim.bc3.apu.importer.line'].create(vals_list)

        self.write({
            'state': 'parsed',
            'log': _("File parsed: %d concept records loaded.") % len(vals_list),
        })
        return True

    def action_process_batch(self):
        """Process the next batch_size APU lines."""
        self.ensure_one()

        uom_obj = self.env['uom.uom']
        product_obj = self.env['product.product']
        template_obj = self.env['bim.concept.template']
        group_obj = self.env['bim.concept.template.group']
        line_model = self.env['bim.concept.template.line']

        bc3_to_line_type = {1: 'H', 2: 'Q', 3: 'M'}

        # Cache all staging lines by code for resource lookups
        all_lines_by_code = {l.code: l for l in self.line_ids}

        # Step 1: process pending chapters (groups) - always all at once
        chapter_pending = self.line_ids.filtered(
            lambda l: l.state == 'pending' and l.ctype == 0
            and '#' in (l.code or '') and '##' not in (l.code or ''))
        for cl in chapter_pending:
            clean_code = cl.code.replace('#', '')
            group = group_obj.search([('code', '=', clean_code)], limit=1)
            if not group:
                group_obj.create({'code': clean_code, 'name': cl.name})
            cl.state = 'done'

        # Step 2: process pending APU lines in batch
        apu_pending = self.line_ids.filtered(
            lambda l: l.state == 'pending' and l.ctype == 0
            and '#' not in (l.code or '')
        ).sorted('sequence')[:self.batch_size]

        if not apu_pending:
            remaining = self.line_ids.filtered(
                lambda l: l.state == 'pending' and l.ctype == 0
                and '#' not in (l.code or ''))
            if not remaining:
                self.state = 'done'
                self.log = (self.log or '') + '\n' + _(
                    "Processing complete. %d APUs processed.") % self.processed_lines
            return True

        log_lines = []
        for apu_line in apu_pending:
            try:
                uom_id = False
                if apu_line.uom:
                    uom_rec = uom_obj.search(
                        ['|', ('name', 'ilike', apu_line.uom),
                         ('alt_names', 'ilike', apu_line.uom)], limit=1)
                    uom_id = uom_rec.id if uom_rec else False

                group_id = False
                if apu_line.parent_code:
                    grp = group_obj.search([('code', '=', apu_line.parent_code)], limit=1)
                    group_id = grp.id if grp else False

                tpl_vals = {
                    'code': apu_line.code,
                    'name': apu_line.name,
                    'uom_id': uom_id,
                    'company_id': self.company_id.id,
                    'bc3_importer_id': self.id,
                }
                if group_id:
                    tpl_vals['group_id'] = group_id
                if apu_line.notes:
                    tpl_vals['notes'] = apu_line.notes

                template = template_obj.search(
                    [('code', '=', apu_line.code),
                     ('company_id', '=', self.company_id.id)], limit=1)
                if not template:
                    template = template_obj.create(tpl_vals)
                else:
                    tpl_vals['bc3_importer_id'] = self.id
                    template.write(tpl_vals)

                # Create template lines from decomposition
                try:
                    children = json.loads(apu_line.decomp_json or '[]')
                except Exception:
                    children = []

                if children:
                    template.template_line_ids.unlink()
                    tpl_seq = 10
                    for child_code, qty in children:
                        try:
                            child_staging = all_lines_by_code.get(child_code)
                            if not child_staging:
                                continue
                            ctype = child_staging.ctype
                            line_type = bc3_to_line_type.get(ctype)
                            if not line_type:
                                # Porcentajes BC3: %CI, %GG, etc. → tipo A
                                if child_code.startswith('%'):
                                    line_type = 'A'
                                else:
                                    continue  # sub-APU u otro; saltar

                            # ----- Percentage concepts: no product needed -----
                            if line_type == 'A' and child_code.startswith('%'):
                                pct_name = child_staging.name or ''
                                # Fallback if name is empty or is just the unit symbol
                                if not pct_name or pct_name.strip() == '%':
                                    pct_name = child_code
                                line_model.create({
                                    'template_id': template.id,
                                    'type': 'A',
                                    'code': child_code,
                                    'name': pct_name,
                                    'price': child_staging.price,
                                    'quantity': qty,
                                    'sequence': tpl_seq,
                                })
                                tpl_seq += 10
                                continue

                            # Search by internal reference (default_code)
                            product = product_obj.search(
                                [('default_code', '=', child_code)], limit=1)

                            # Use exact match (=ilike) to avoid % acting as SQL wildcard
                            child_uom = child_staging.uom or ''
                            uom_rec = uom_obj.search(
                                ['|', ('name', '=ilike', child_uom),
                                 ('alt_names', '=ilike', child_uom)],
                                limit=1) if child_uom else uom_obj.browse()

                            if not product:
                                # Always 'service' — same as BC3 budget wizard;
                                # resource_type carries the BIM category (H/Q/M/A)
                                resource_type = line_type if line_type != 'A' else 'A'
                                create_vals = {
                                    'default_code': child_code,
                                    'name': child_staging.name,
                                    'resource_type': resource_type,
                                    'type': 'service',
                                    'bc3_importer_id': self.id,
                                }
                                if uom_rec:
                                    create_vals['uom_id'] = uom_rec.id
                                product = product_obj.create(create_vals)
                                self._write_product_price(child_staging.price, product)
                            else:
                                # Associate existing; update only if requested
                                if self.action_type == 'add_update':
                                    write_vals = {
                                        'name': child_staging.name,
                                        'resource_type': line_type,
                                    }
                                    if uom_rec:
                                        write_vals['uom_id'] = uom_rec.id
                                    product.write(write_vals)
                                    self._write_product_price(child_staging.price, product)

                            line_model.create({
                                'template_id': template.id,
                                'type': line_type,
                                'product_id': product.id,
                                'code': child_code,
                                'name': child_staging.name,
                                'uom_id': uom_rec.id if uom_rec
                                else (product.uom_id.id if product else False),
                                'price': child_staging.price,
                                'quantity': qty,
                                'sequence': tpl_seq,
                            })
                            tpl_seq += 10

                        except Exception as child_err:
                            _logger.warning(
                                "BC3 APU importer: skipping resource %s for APU %s: %s",
                                child_code, apu_line.code, child_err)

                apu_line.state = 'done'
                log_lines.append("✓ [%s] %s" % (apu_line.code, (apu_line.name or '')[:60]))

            except Exception as e:
                apu_line.state = 'error'
                apu_line.error_msg = str(e)
                log_lines.append("✗ [%s]: %s" % (apu_line.code, str(e)[:120]))
                _logger.exception("Error processing BC3 APU line %s", apu_line.code)

        if self.state == 'parsed':
            self.state = 'processing'

        self.log = (self.log or '') + '\n' + '\n'.join(log_lines)

        # Check completion
        remaining = self.line_ids.filtered(
            lambda l: l.state == 'pending' and l.ctype == 0
            and '#' not in (l.code or ''))
        if not remaining:
            self.state = 'done'
            self.log += '\n' + _("All APUs processed. Total: %d.") % self.total_lines

        return True

    def _write_product_price(self, price, product):
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0
        if self.company_id.type_work in ('costlist', 'cost'):
            product.with_company(self.company_id).standard_price = price
        else:
            product.list_price = price

    def action_reset(self):
        """Reset import to draft."""
        self.ensure_one()
        self.line_ids.unlink()
        self.write({'state': 'draft', 'log': False})

    def action_retry_errors(self):
        """Reset error lines to pending so they can be re-processed."""
        self.ensure_one()
        error_lines = self.line_ids.filtered(lambda l: l.state == 'error')
        error_lines.write({'state': 'pending', 'error_msg': False})
        if self.state == 'done':
            self.state = 'processing'

    @api.model
    def cron_process_batch(self):
        """Scheduled action: process one batch for every active importer."""
        importers = self.search([('state', 'in', ('parsed', 'processing'))])
        for importer in importers:
            try:
                importer.action_process_batch()
                self.env.cr.commit()  # commit each importer independently
            except Exception as e:
                _logger.exception(
                    "BC3 APU cron: error processing importer %s: %s",
                    importer.name, e)
                self.env.cr.rollback()


class BimBc3ApuImporterLine(models.Model):
    _name = 'bim.bc3.apu.importer.line'
    _description = 'BC3 APU Importer Line'
    _order = 'sequence, id'

    importer_id = fields.Many2one(
        'bim.bc3.apu.importer', ondelete='cascade', required=True, index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(string='Code', required=True)
    name = fields.Text(string='Name')
    uom = fields.Char(string='UoM')
    price = fields.Float(string='Price', digits='BIM price')
    ctype = fields.Integer(string='BC3 Type')
    parent_code = fields.Char(string='Chapter Code')
    notes = fields.Text(string='Notes')
    decomp_json = fields.Text(string='Children (JSON)')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
        ('skip', 'Skip'),
    ], string='State', default='pending')
    error_msg = fields.Text(string='Error Message')
    type_label = fields.Char(string='Kind', compute='_compute_type_label', store=True)

    @api.depends('ctype', 'code')
    def _compute_type_label(self):
        labels = {1: 'Labor', 2: 'Equipment', 3: 'Material'}
        for line in self:
            if line.ctype == 0:
                line.type_label = 'Chapter' if '#' in (line.code or '') else 'APU'
            else:
                line.type_label = labels.get(line.ctype, str(line.ctype))
