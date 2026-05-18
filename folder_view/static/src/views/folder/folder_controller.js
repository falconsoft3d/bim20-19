/** @odoo-module */
import { ListController } from '@web/views/list/list_controller';

export class FolderController extends ListController {
    setup() {
        super.setup();
        this.onOpenFormView = this.openFormView.bind(this);
    }

    async openFormView(record) {
        await record.save();
        const activeIds = this.model.root.records.map((datapoint) => datapoint.resId);
        this.props.selectRecord(record.resId, { activeIds });
    }

    async openRecord(record) {
        await record.save();
        const parentField = this.props.archInfo.parentField;
        const views = this.env.config.views.sort((i, j) => i[1] === 'folder' ? -1 : 0)
        const context = { ...record.context };
        context[`default_${parentField}`] = record.resId;
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: record.data.name,
            res_model: record.resModel,
            domain: [[parentField, '=', record.resId]],
            views,
            context,
        }, {
            onClose: async () => {
                await record.model.root.load();
            },
        });
    }
};
