/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('bi_account_asset_tour', {
    url: "/web",
    steps: () => [
        {
            content: "Open Accounting App",
            trigger: '.o_app[data-menu-xmlid="account.menu_finance"]',
            run: 'click',
        },
        {
            content: "Open Configuration Menu",
            trigger: 'button[data-menu-xmlid="account.menu_finance_configuration"]',
            run: 'click',
        },
        {
            content: "Click Assets and Revenues",
            trigger: 'a[data-menu-xmlid="bi_account_asset.menu_finance_config_assets"]',
            run: 'click',
        },
        {
            content: "Create new Asset Category",
            trigger: '.o_list_button_add',
            run: 'click',
        },
        {
            content: "Fill Asset Type Name",
            trigger: 'div[name="name"] input',
            run: "edit Test Asset Category",
        },
        {
            content: "Select Journal",
            trigger: 'div[name="journal_id"] input',
            run: "click",
        },
        {
            content: "Select first journal",
            trigger: '.dropdown-menu li:first-child, .ui-menu-item:first-child', 
            run: 'click',
        },
        {
            content: "Set Number of Entries",
            trigger: 'div[name="method_number"] input',
            run: "edit 5",
        },
        {
            content: "Save Category",
            trigger: '.o_form_button_save',
            run: 'click',
        },
        // Create Asset
        {
            content: "Open Accounting Menu",
            trigger: 'button[data-menu-xmlid="account.menu_finance_entries"]',
            run: 'click',
        },
        {
            content: "Click Assets",
            trigger: 'a[data-menu-xmlid="bi_account_asset.menu_action_account_asset_asset_form"]',
            run: 'click',
        },
        {
            content: "Create new Asset",
            trigger: '.o_list_button_add',
            run: 'click',
        },
        {
            content: "Fill Asset Name",
            trigger: 'div[name="name"] input',
            run: "edit Test Asset",
        },
        {
            content: "Select Category",
            trigger: 'div[name="category_id"] input',
            run: "edit Test Asset Category",
        },
        {
             content: "Select category from dropdown",
             trigger: '.dropdown-menu li, .ui-menu-item',
             run: 'click',
        },
        {
            content: "Set Gross Value",
            trigger: 'div[name="value"] input',
            run: "edit 1000",
        },
        {
            content: "Save Asset",
            trigger: '.o_form_button_save',
            run: 'click',
        },
        {
            content: "Confirm Asset",
            trigger: 'button[name="validate"]',
            run: 'click',
        },
        {
            content: "Compute Depreciation",
            trigger: 'button[name="compute_depreciation_board"]',
            run: 'click',
        }
    ]
});
