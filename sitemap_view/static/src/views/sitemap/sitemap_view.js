/** @odoo-module */

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { SitemapArchParser } from './sitemap_arch_parser';
import { SitemapController } from './sitemap_controller';
import { SitemapRenderer } from './sitemap_renderer';

export const SitemapView = {
    ...listView,
    type: 'sitemap',
    display_name: 'Sitemap',
    icon: 'fa fa-sitemap',
    ArchParser: SitemapArchParser,
    Controller: SitemapController,
    Renderer: SitemapRenderer,
};

registry.category('views').add('sitemap', SitemapView);
