/** @odoo-module */

import { Component, useState, onMounted } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';

/**
 * Componente <li> con cada item
 */
export class SitemapSidebarItem extends Component {
    setup() {
        this.state = useState({
            children: [],
            selected: false,
            child_selected: false,
        });
        this.orm = useService('orm');
        this.getChildren();
        onMounted(() => {
            if (this.props.parentsSelected?.indexOf(this.item.id) >= 0) {
                this.toggleSelect();
            }
        });
    }

    async getChildren() {
        const childrenRecords = await this.orm.searchRead(this.props.resModel, [['parent_id', '=', this.props.item.id]], ['display_name']);
        this.state.children = childrenRecords.map(rec => { return { name: rec.display_name, id: rec.id } });
    }

    get item() {
        return this.props.item;
    }

    get children() {
        return this.state.children && this.state.children.length > 0 ? this.state.children : false;
    }

    get sibblingIds() {
        return this.props.container.items.map(item => item.id);
    }

    get padding() {
        return this.props.padding;
    }

    async toggleSelect() {
        this.state.selected = !this.state.selected;
        if (!this.state.selected) {
            this.state.child_selected = false;
        } else {
            await this.getChildren();
        }
        this.env.sitemapBus.trigger('select-item', this.state.selected ? this : this.props.parent);
    }

    isMyParent(parent) {
        if (!this.props.parent) {
            return false;
        }
        if (this.props.parent.item.id === parent.item.id) {
            return true;
        }
        return this.props.parent.isMyParent(parent);
    }
};
SitemapSidebarItem.template = 'sitemap_view.Sidebar.Item';
SitemapSidebarItem.props = {
    item: { type: Object, optional: false },
    resModel: { type: String, optional: false },
    container: { type: Object, optional: false },
    padding: { type: Number, optional: true },
    parent: { type: Object, optional: true },
    parentsSelected: { type: Array, optional: true },
};
SitemapSidebarItem.defaultProps = {
    padding: 0,
};

/**
 * Componente <ul> que engloba cada item
 */
export class SitemapSidebar extends Component {

    get items() {
        return this.props.items;
    }

    get padding() {
        return this.props.padding;
    }
};
SitemapSidebar.template = 'sitemap_view.Sidebar';
SitemapSidebar.components = {
    SitemapSidebarItem,
};
SitemapSidebar.props = {
    items: { type: Array, optional: false },
    resModel: { type: String, optional: false },
    padding: { type: Number, optional: true },
    parent: { type: Object, optional: true },
    parentsSelected: { type: Array, optional: true },
};
SitemapSidebar.defaultProps = {
    padding: 0,
};

SitemapSidebarItem.components = { SitemapSidebar };
