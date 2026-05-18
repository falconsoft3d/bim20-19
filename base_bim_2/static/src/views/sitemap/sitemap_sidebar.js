/** @odoo-module */

import { SitemapSidebarItem, SitemapSidebar } from '@sitemap_view/views/sitemap/sitemap_sidebar';


export class BimSitemapSidebarItem extends SitemapSidebarItem {

    /** @override Metemos los campos que nos falten, como el tipo */
    async getChildren() {
        const childrenRecords = await this.orm.searchRead(this.props.resModel, [['parent_id', '=', this.props.item.id]], ['display_name', 'type', 'measuring_ids']);
        this.state.children = childrenRecords.map(rec => { return { ...rec, name: rec.display_name } });
    }

    /**
     * Pintamos acá el icono que queremos mostrar, según el tipo de concepto.
     */
    get icon() {
        let icon;
        switch (this.item.type) {
            case 'chapter':
                icon = 'fa-th-large text-success'; break;
            case 'departure':
                icon = 'fa-th-list text-warning'; break;
            case 'labor':
                icon = 'fa-male text-success'; break;
            case 'equip':
                icon = 'fa-gears text-danger'; break;
            case 'material':
                icon = 'fa-maxcdn text-warning'; break;
            case 'subcontract':
                icon = 'fa-group text-warning'; break;
            case 'aux':
                icon = 'fa-percent text-o'; break;
            default:
                icon = ''; break;
        }
        return `fa fa-fw me-1 ${icon}`;
    }

    openContextmenu(ev) {
        if (!this.state.selected) {
            this.toggleSelect();
        }
        this.env.sitemapBus.trigger('open-contextmenu', { ev, item: this });
    }
};
BimSitemapSidebarItem.template = 'base_bim_2.Sidebar.Item';


export class BimSitemapSidebar extends SitemapSidebar { };
BimSitemapSidebar.components = {
    SitemapSidebarItem: BimSitemapSidebarItem,
};

BimSitemapSidebarItem.components = {
    SitemapSidebar: BimSitemapSidebar,
};