/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class PurchaseDrilldownNavigator extends Component {
    static template = "gn_purchase_dashboard.DrilldownNavigator";
    static props = {
        breadcrumb: Array,
        rows: Array,
        level: String,
        loading: Boolean,
        fmtMoney: Function,
        onNavigate: Function,
        onRowClick: Function,
        onOpenPanel: { type: Function, optional: true },
    };

    onCrumbClick(item) {
        if (this.props.onNavigate) this.props.onNavigate(item.level, {});
    }

    onRowSelect(row) {
        if (this.props.onRowClick) this.props.onRowClick(this.props.level, row);
    }

    onPanelOpen(row, ev) {
        ev.stopPropagation();
        if (this.props.onOpenPanel) this.props.onOpenPanel(row);
    }
}
