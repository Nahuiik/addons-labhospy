/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('inventory_dashboard_tour', {
    url: "/web",
    steps: () => [
        {
            content: "Open Inventory app",
            trigger: '.o_app[data-menu-xmlid="stock.menu_stock_root"]',
            run: 'click',
        },
        {
            content: "Click on Dashboard menu",
            trigger: 'a[data-menu-xmlid="dev_advance_inventory_dashboard.inventory_menu_open_Dashboard"]',
            run: 'click',
        },
        {
            content: "Check if Dashboard filters are visible",
            trigger: '.inv-dash__filters select',
        },
        {
            content: "Check if KPI cards are loaded",
            trigger: '.inv-kpi-grid .inv-kpi',
        },
    ],
});
