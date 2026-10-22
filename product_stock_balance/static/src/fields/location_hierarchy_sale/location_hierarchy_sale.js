/** @odoo-module */

import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class SaleLocationsLink extends Component {
    static template = "product_stock_balance.saleLineByLocations";
    /*
    * Overwrite to import services
    */
    setup() {
        this.actionService = useService("action");
    }
    /*
    * The method to load stocks by locations action
    */
    _onShowStocksByLocations(ev) {
        const productField = this.props.record.data.product_id;
        const currentProduct = productField && (productField.id || productField[0]);
        if (currentProduct) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                name: _t("Inventory levels"),
                res_model: "product.product",
                res_id: currentProduct,
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: { form_view_ref: "product_stock_balance.product_product_form_only_locations" },
            });
        };
    }
};

export const saleLocationsLink = { component: SaleLocationsLink };

registry.category("view_widgets").add("SaleLocationsLink", saleLocationsLink);
