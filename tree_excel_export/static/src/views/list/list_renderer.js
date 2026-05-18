/** @odoo-module */

import { patch } from '@web/core/utils/patch';
import { ListRenderer } from '@web/views/list/list_renderer';
import { download } from '@web/core/network/download';

patch(ListRenderer.prototype, {

    get displayOptionalFields() {
        return true;
    },

    _mfhGetFlatRecords(list) {
        if (!list) {
            return [];
        }
        if (!list.isGrouped) {
            return list.records || [];
        }
        return (list.groups || []).flatMap((group) => this._mfhGetFlatRecords(group.list));
    },

    _mfhToPlainText(value) {
        if (value === null || value === undefined) {
            return '';
        }
        return String(value)
            .replaceAll('~;', ' ')
            .replaceAll('#;', ' ')
            .replaceAll('\n', ' ')
            .trim();
    },

    _mfhGetRawValue(column, record) {
        const value = record?.data?.[column.name];
        if (value === null || value === undefined) {
            return '';
        }
        if (Array.isArray(value)) {
            return value.length > 1 ? value[1] : value[0] || '';
        }
        if (value && typeof value === 'object') {
            if ('display_name' in value && value.display_name) {
                return value.display_name;
            }
            return '';
        }
        if (typeof value === 'boolean') {
            return value ? '1' : '0';
        }
        return value;
    },

    _mfhGetCellValue(column, record) {
        try {
            if (column.widget || !this.canUseFormatter(column, record)) {
                return this._mfhGetRawValue(column, record);
            }
            return this.getFormattedValue(column, record);
        } catch {
            return this._mfhGetRawValue(column, record);
        }
    },

    async mfhExportExcel() {
        const columns = (this.columns || []).filter((column) => column.type === 'field' && column.name);
        const header = columns.map((column) => this._mfhToPlainText(column.label || column.name)).join('#;');
        const records = this._mfhGetFlatRecords(this.props.list);
        const body = records
            .map((record) =>
                columns
                    .map((column) => this._mfhToPlainText(this._mfhGetCellValue(column, record)))
                    .join('~;')
            )
            .join('#;');

        const actionName = this.env.services?.action?.currentController?.action?.display_name
            || this.env.services?.action?.currentController?.action?.name
            || this.props?.list?.resModel
            || '';

        await download({
            data: { header, body, name: actionName },
            url: '/tree_excel_export/download',
        });
    }
});
