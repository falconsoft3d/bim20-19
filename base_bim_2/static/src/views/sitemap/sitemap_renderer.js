/** @odoo-module */

import { Component, useState, onWillStart } from '@odoo/owl';
import { useBus, useService } from '@web/core/utils/hooks';
import { Record } from "@web/model/record";
import { ListRenderer } from '@web/views/list/list_renderer';
import { SitemapRenderer } from '@sitemap_view/views/sitemap/sitemap_renderer';
import { BimSitemapSidebar } from './sitemap_sidebar';
import { BimSitemapContextmenu } from './sitemap_contextmenu';


export class BimSitemapMeasure extends Component {};


export class BimSitemapRenderer extends SitemapRenderer {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.contextmenuState = useState({
            item: false,
            position: false,
        });
        this.measureState = useState({
            open: false,
            record: false,
            context: false,
        });
        useBus(this.env.sitemapBus, 'open-contextmenu', this.openContextmenu);
        useBus(this.env.sitemapBus, 'unlink-item', this.unlinkItem);
        useBus(this.env.sitemapBus, 'paste-item', this.pasteItem);
        useBus(this.env.sitemapBus, 'move-item', this.moveItem);
        this.orm = useService('orm');

        onWillStart(async () => {
           const response = await this.orm.call('ir.config_parameter', 'get_param', ['bim.measures.always.open']);
           this.measureState.open = response === 'True';
        });
    }

    /**
     * @override
     * Sobreescribimos el método para que traiga lo que necesitemos del modelo bim.concepts
     */
    async getItems() {
        const parentField = this.props.archInfo.parentField;
        const domain = !!this.env.model.root.domain.length ? ['&', ...this.env.model.root.domain, [parentField, '=', false]] : [[parentField, '=', false]];
        const parentRecords = await this.env.model.orm.searchRead(this.env.model.root.resModel, domain, ['display_name', 'type', 'measuring_ids']);
        this.itemState.items = parentRecords.map(rec => { return { ...rec, name: rec.display_name } });
    }

    /**
     * @override
     * Sobreescribimos el método para que al seleccionar, guardemos antes los valores del record,
     * de modo que podamos obtener las mediciones y notas.
     */
    async selectItem(item) {
        const hasMeasures = item && item.item.measuring_ids.length ? true : false;
        const record = item ? this.env.model.root.records.find(rec => rec.resId === item.item.id) : false;
        await super.selectItem(item);
        this.measureState.record = hasMeasures ? record : false;
        this.measureState.context = hasMeasures ? this.env.model.root.context : false;
        this.measureState.fieldInfo = hasMeasures ? this.props.archInfo.fieldNodes.measuring_ids_0 : false;
        this.measureState.note = !!record?.data?.note ? record.data.note : false;
    }

    /**
     * Al activar la casillita de mediciones, guardamos el valor en los parámetros.
     */
    async setMeasureOpen() {
        await this.orm.call('ir.config_parameter', 'set_param_sudo', ['bim.measures.always.open', !this.measureState.open ? 'True' : 'False']);
        this.measureState.open = !this.measureState.open;
    }

    /**
     * En caso de existir mediciones, se mostrará la nota asociada al concepto.
     */
    get note() {
        return this.measureState.note;
    }

    openContextmenu({ detail: { item, ev: { pageX, pageY } } }) {
        this.contextmenuState.item = item;
        this.contextmenuState.position = { pageX, pageY };
    }

    /**
     * Este método lo llamamos desde el SitemapContextmenu, ya que si intentamos
     * hacer el unlink y borrado ahí, da error porque se borra a sí mismo en el
     * proceso, por eso lo controlamos desde acá.
     * @param {SitemapSidebarItem} SidebarItem 
     */
    async unlinkItem({ detail: { SidebarItem } }) {
        await this.orm.unlink(this.env.model.root.resModel, [SidebarItem.item.id]);
        if (SidebarItem.props.parent) {
            await SidebarItem.props.parent.toggleSelect();
        } else {
            await this.selectItem(false);
            await this.getItems();
        }
    }

    /**
     * Método llamado desde el SitemapContextmenu, para hacer el pegado, esto ya
     * que el context se destruye antes de que se termine de pegar todo y no da
     * tiempo para actualizar, mejor hacerlo acá mismo.
     * @param {SitemapSidebarItem} SidebarItem
     * @param {int} uid
     */
    async pasteItem({ detail: { SidebarItem, uid } }) {
        await this.orm.call('res.users', 'copy_bim_concept', [uid, SidebarItem.item.id, this.env.model.root.context.default_budget_id]);
        this.reloadsidePanel();
    }

    /**
     * Llamada desde el SitemapContextmenu, acá lo complicado de mover es que
     * refrescamos desde el padre, este cambia las posiciones de sus hijos sin
     * destruir los elementos, pero los nietos quedan en la misma posición.+
     * @param {SitemapSidebarItem} SidebarItem
     * @param {string} action
     * @returns 
     */
    async moveItem({ detail: { SidebarItem, action } }) {
        const position = SidebarItem.sibblingIds.indexOf(SidebarItem.item.id);
        if ((action === 'up' && position === 0) || action === 'down' && position === SidebarItem.sibblingIds.length - 1) {
            return;
        }
        const itemId = SidebarItem.item.id;
        await this.orm.call('bim.concepts', 'move_record', [itemId, `move_${action}`]);
        if (SidebarItem.props.parent) {
            await SidebarItem.toggleSelect();
            await SidebarItem.props.parent.getChildren();
        } else {
            await this.selectItem(false);
            await this.getItems();
        }
    }
};
BimSitemapRenderer.template = 'base_bim_2.SitemapRenderer';
BimSitemapRenderer.components = {
    ...ListRenderer.components,
    SitemapSidebar: BimSitemapSidebar,
    SitemapContextmenu: BimSitemapContextmenu,
    Record,
};