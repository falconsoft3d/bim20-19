/** @odoo-module */

import { registry } from '@web/core/registry';
import { SitemapView } from '@sitemap_view/views/sitemap/sitemap_view';
import { BimSitemapController } from './sitemap_controller';
import { BimSitemapRenderer } from './sitemap_renderer';

export const BimSitemapView = {
    ...SitemapView,
    Renderer: BimSitemapRenderer,
    Controller: BimSitemapController,
    buttonTemplate: 'base_bim_2.SitemapView.Buttons',
};

registry.category('views').add('bim_sitemap', BimSitemapView);
