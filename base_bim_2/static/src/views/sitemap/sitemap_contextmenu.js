/** @odoo-module */

import { Component, useState } from '@odoo/owl';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';
import { useService } from '@web/core/utils/hooks';
import { session } from '@web/session';

export class BimSitemapContextmenu extends Component {
    setup() {
        const sessionUid = Array.isArray(session.user_id) ? session.user_id[0] : session.user_id;
        const fallbackUid = session.uid;
        const rawUid = sessionUid || fallbackUid;
        const parsedUid = Number.parseInt(rawUid, 10);
        this.uid = Number.isInteger(parsedUid) && parsedUid > 0 ? parsedUid : false;
        this.action = useService('action');
        this.orm = useService('orm');
        this.dialog = useService('dialog');
        this.state = useState({
            pastebin: false,
        });
        if (this.uid) {
            this.orm.read('res.users', [this.uid], ['copied_bim_concept_id', 'cut_bim_concept_id']).then(result => {
                const userData = result && result[0] ? result[0] : {};
                this.state.pastebin = userData.copied_bim_concept_id || userData.cut_bim_concept_id;
            });
        }
    }

    get item() {
        return this.props.item.item;
    }

    get parent() {
        return this.props.item.props.parent;
    }

    get position() {
        const top = this.props.position.pageY;
        const cmHeight = 326; /* Altura estimada del contextMenu */
        const wHeight = window.innerHeight
        const yaxis = cmHeight + top >= wHeight ? `bottom: ${wHeight - top}px` : `top: ${top}px`;
        return `${yaxis}; left: ${this.props.position.pageX}px`;
    }

    actionOpen() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: this.item.name,
            target: 'current',
            res_id: this.item.id,
            res_model: 'bim.concepts',
            views: [[false, 'form']],
            context: { default_parent_id: this.item.id },
        });
    }

    actionCreate() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Concept',
            target: 'current',
            res_model: 'bim.concepts',
            views: [[false, 'form']],
            context: { default_parent_id: this.item.id },
        });
    }

    actionCopy() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Concept',
            target: 'current',
            res_model: 'bim.concepts',
            views: [[false, 'form']],
            context: { ...this.env.model.root.evalContext, default_parent_id: this.parent?.item.id },
        });
    }

    async actionDeleteItem() {
        const continueUnlink = await new Promise(resolve => this.dialog.add(ConfirmationDialog, {
            body: _t('Are you sure you want to delete this record ?'),
            confirm: () => resolve(true),
            cancel: () => resolve(false),
        }));
        if (!continueUnlink) {
            return;
        }
        this.props.item.env.sitemapBus.trigger('unlink-item', { SidebarItem: this.props.item });
    }

    async actionCertMassive() {
        await this.orm.call('bim.concepts', 'cert_massive', [this.item.id]);
        await this.item.toggleSelect();
        await this.item.toggleSelect();
    }

    async actionDeepCopy() {
        if (!this.uid) {
            return;
        }
        await this.orm.write('res.users', [this.uid], { copied_bim_concept_id: this.item.id, cut_bim_concept_id: false });
    }

    async actionDeepCut() {
        if (!this.uid) {
            return;
        }
        await this.orm.write('res.users', [this.uid], { copied_bim_concept_id: false, cut_bim_concept_id: this.item.id });
    }

    async actionDeepPaste() {
        if (!this.uid) {
            return;
        }
        this.props.item.env.sitemapBus.trigger('paste-item', { SidebarItem: this.props.item, uid: this.uid });
    }

    actionMoveUp() {
        this.props.item.env.sitemapBus.trigger('move-item', { SidebarItem: this.props.item, action: 'up' });
    }
    actionMoveDown() {
        this.props.item.env.sitemapBus.trigger('move-item', { SidebarItem: this.props.item, action: 'down' });
    }
    async actionUpdateConcept() {
        await this.orm.call('bim.concepts', 'update_concept', [this.item.id]);
        await this.item.toggleSelect();
        await this.item.toggleSelect();
    }

};
BimSitemapContextmenu.template = 'base_bim_2.SitemapContextmenu';
BimSitemapContextmenu.props = {
    item: { type: Object },
    position: { type: Object },
};
