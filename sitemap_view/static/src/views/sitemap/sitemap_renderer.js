/** @odoo-module */
import { ListRenderer } from '@web/views/list/list_renderer';
import { SitemapSidebar } from './sitemap_sidebar';
import { EventBus, useState, useSubEnv, onMounted } from '@odoo/owl';
import { useBus, useService } from '@web/core/utils/hooks';


export class SitemapRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.itemState = useState({
            items: [],
        });

        useSubEnv({
            sitemapBus: new EventBus(),
        });
        useBus(this.env.sitemapBus, 'select-item', ev => this.selectItem(ev.detail));
        useBus(this.env.bus, 'reload-sidepanel', ev => this.reloadsidePanel());
        
        this.actionService = useService('action');
        onMounted(async () => {
            /**
             * Es necesaria esta migropausa, para que el action cargue correctamente y exista el currentController,
             * que sirve para que checkSelected verifique los elementos que estaban abiertos.
             */
            await new Promise(r => setTimeout(r, 1));
            await this.checkSelected();
            this.getItems();
        });
    }

    /**
     * Lo llamamos al inicio solo para traernos los elementos padres y popular nuestra lista.
     */
    async getItems() {
        const parentField = this.props.archInfo.parentField;
        const domain = !!this.env.model.root.domain.length ? ['&', ...this.env.model.root.domain, [parentField, '=', false]] : [[parentField, '=', false]];
        const parentRecords = await this.env.model.orm.searchRead(this.env.model.root.resModel, domain, ['display_name']);
        this.itemState.items = parentRecords.map(rec => { return { name: rec.display_name, id: rec.id }});
    }

    /**
     * Método que se encarga de actualizar el listado con los registros hijos del elemento seleccionado.
     * @param {SitemapSidebarItem} item Viene del sidebar, si viene vacío es porque lo deseleccionaron.
     */
    async selectItem(item) {
        if (item && this.selectedItem) {
            if (item.isMyParent(this.selectedItem)) {
                this.selectedItem.state.child_selected = true;
            } else {
                this.selectedItem.state.child_selected = false;
                let parent = this.selectedItem.props.parent;
                while (parent && !item.isMyParent(parent)) {
                    parent.state.child_selected = false;
                    parent = parent.props.parent;
                }
            }
            this.selectedItem.state.selected = false;
            item.state.selected = true;
        }
        const parentField = this.props.archInfo.parentField;
        this.selectedItem = item;
        const parentId = this.selectedItem ? this.selectedItem.item.id : false;

        /* Actualizamos el context para que por defecto los nuevos registros vengan con el padre que se ha seleccionado */
        /* Por si le dan al botón nuevo y va al form */
        this.actionService.currentController.action.context[`default_${parentField}`] = parentId;
        /* Por si están en una lista editable y agregan el registro ahí mismo */
        this.props.list.evalContext[`default_${parentField}`] = parentId;

        let domain = [];
        let parentFieldInDomain = false;
        for (let dom of this.env.searchModel.domain) {
            if (Array.isArray(dom) && dom[0] === parentField) {
                dom[2] = parentId;
                parentFieldInDomain = true;
            }
            domain.push(dom);
        }
        if (!parentFieldInDomain) {
            domain = [[parentField, '=', parentId]];
        }
        await this.env.model.root.load({ domain });
    }

    /**
     * Pensado para ejecutarse solamente al inicio, y verificar si hay elementos preseleccionados según el context.
     * Con esto logramos que se vuelva a abrir la vista tal como la dejamos.
     */
    async checkSelected() {
        const parentField = this.props.archInfo.parentField;
        const itemId = this.actionService.currentController.action.context[`default_${parentField}`];
        /* Vamos a buscar todos sus padres */
        let parentId = itemId;
        const parentIds = [];
        while (parentId) {
            parentIds.push(parentId);
            let itemData = await this.env.model.orm.read(this.actionService.currentController.props.resModel, [parentId], [parentField]);
            if (!itemData[0][parentField]) {
                parentId = false;
            } else {
                parentId = itemData[0][parentField][0];
            }
        }
        this.parentsSelected = parentIds;
    }

    /**
     * Recarga los elementos del sidePanel, cuando se haya creado,
     * editado o eliminado algún elemento.
     */
    reloadsidePanel() {
        if (this.selectedItem) {
            this.selectedItem.getChildren();
        } else {
            this.getItems();
        }
    }
};
SitemapRenderer.template = 'sitemap_view.SitemapRenderer';
SitemapRenderer.components = {
    ...ListRenderer.components,
    SitemapSidebar,
}
