from odoo import _, api, models


class BimConcepts(models.AbstractModel):
    _inherit = "base"

    @api.model
    def get_gantt_data(
            self, domain, groupby, read_specification, limit=None, offset=0,
    ):
        final_result = super(BimConcepts, self).get_gantt_data(
                domain, groupby, read_specification, limit=limit, offset=offset
            )
        if self._name == "bim.concepts":
            lazy = not limit and not offset and len(groupby) == 1
            default_parent_id = self.env.context.get('default_parent_id')
            parent_id = default_parent_id or final_result['records'][0]['id'] if final_result['records'] else False
            domain = [
                    ("parent_id", "=", parent_id),
                    ("type", "in", ['departure', 'chapter']),
                ]
            records = self.search_fetch(domain, read_specification.keys(), offset=offset, limit=limit, order='acs_date_start')
            # records = bim.concepts(11, 9, 8, 14, 10)
            all_records = self.with_context(active_test=False).search_fetch([('id', 'in', records.ids)],
                                                                            read_specification.keys())
            final_result['records'] = all_records.with_env(self.env).web_read(read_specification)
            for group in final_result['groups']:
                # Reorder __record_ids
                group['__record_ids'] = list(records.ids)

        return final_result