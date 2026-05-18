/** @odoo-module */
import { ListController } from '@web/views/list/list_controller';

export class SitemapController extends ListController {
    async onRecordSaved(record) {
        this.env.bus.trigger('reload-sidepanel');
    }

    get deleteConfirmationDialogProps() {
        const props = super.deleteConfirmationDialogProps;
        props.confirm = async () => {
            await this.model.root.deleteRecords();
            this.env.bus.trigger('reload-sidepanel');
        }
        return props;
    }
};
SitemapController.template = 'sitemap_view.SitemapView'
