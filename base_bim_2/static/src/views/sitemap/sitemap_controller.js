/** @odoo-module */

import { SitemapController } from '@sitemap_view/views/sitemap/sitemap_controller';
import { useService } from '@web/core/utils/hooks';

export class BimSitemapController extends SitemapController {

    setup() {
        super.setup();
        this.orm = useService('orm');
    }

    get budgetId() {
        return this.props.context.default_budget_id;
    }

    get budgetType() {
        return this.props.context.budget_type;
    }

    backHome() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Presupuesto',
            res_model: 'bim.budget',
            res_id: this.budgetId,
            views: [[false, 'form']],
        }, {
            additional_context: {
                default_budget_id: this.budgetId,
            },
            clearBreadcrumbs: true,
        });
    }

    async changeBudgetType(type) {
        await this.orm.write('bim.budget', [this.budgetId], { type });
        const context = {
            budget_type: type,
            default_budget_id: this.budgetId,
        }
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Concepto',
            res_model: 'bim.concepts',
            views: [[false, 'sitemap'], [false, 'folder'], [false, 'list'], [false, 'form']],
            domain: this.props.domain,
            context,
        }, {
            additional_context: context,
            clearBreadcrumbs: true,
        });
    }
};
