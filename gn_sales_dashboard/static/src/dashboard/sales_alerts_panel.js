/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { SalesEmptyState } from "./empty_state";

export class SalesAlertsPanel extends Component {
    static template = "gn_sales_dashboard.SalesAlertsPanel";
    static components = { SalesEmptyState };
    static props = {
        alerts: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        onAlertClick: { type: Function, optional: true },
        onViewAll: { type: Function, optional: true },
        compact: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({ expanded: false });
    }

    severityIcon(sev) {
        return {
            critical: "fa-exclamation-circle",
            warning: "fa-warning",
            info: "fa-info-circle",
        }[sev] || "fa-circle";
    }

    get sortedItems() {
        const items = [...(this.props.alerts?.items || [])];
        const order = { critical: 0, warning: 1, info: 2 };
        items.sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));
        return items;
    }

    get visibleItems() {
        const items = this.sortedItems;
        if (!this.props.compact || this.state.expanded) return items;
        return items.slice(0, 3);
    }

    toggleExpanded() {
        this.state.expanded = !this.state.expanded;
    }

    onClick(alert, ev) {
        ev.stopPropagation();
        if (this.props.onAlertClick) {
            this.props.onAlertClick(alert);
        }
    }

    onViewAllClick(ev) {
        ev.stopPropagation();
        if (this.props.onViewAll) {
            this.props.onViewAll();
        }
    }
}
