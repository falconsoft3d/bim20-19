/** @odoo-module */
import { ListRenderer } from '@web/views/list/list_renderer';

export class FolderRenderer extends ListRenderer {};
FolderRenderer.recordRowTemplate = 'folder_view.ListRenderer.RecordRow';
