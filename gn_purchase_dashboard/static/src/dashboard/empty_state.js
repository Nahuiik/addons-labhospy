/** @odoo-module **/

import { Component } from "@odoo/owl";

export class PurchaseEmptyState extends Component {
    static template = "gn_purchase_dashboard.PurchaseEmptyState";
    static props = {
        icon: { type: String, optional: true },
        title: { type: String, optional: true },
        description: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        compact: { type: Boolean, optional: true },
        onAction: { type: Function, optional: true },
    };

    onActionClick(ev) {
        ev.stopPropagation();
        if (this.props.onAction) {
            this.props.onAction();
        }
    }
}
