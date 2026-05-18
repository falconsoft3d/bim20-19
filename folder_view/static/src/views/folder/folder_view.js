/** @odoo-module */
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { FolderArchParser } from './folder_arch_parser';
import { FolderController } from './folder_controller';
import { FolderRenderer } from './folder_renderer';

export const folderView = {
    ...listView,
    type: 'folder',
    display_name: 'Folder',
    icon: 'fa fa-folder-open',
    ArchParser: FolderArchParser,
    Controller: FolderController,
    Renderer: FolderRenderer,
};

registry.category('views').add('folder', folderView);
