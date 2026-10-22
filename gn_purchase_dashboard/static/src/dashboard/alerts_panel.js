/** @odoo-module **/

import { Component } from "@odoo/owl";
import { PurchaseEmptyState } from "./empty_state";

const SEVERITY_ORDER = { critical: 0, high: 1, warning: 2, medium: 3, info: 4 };

export class PurchaseAlertsPanel extends Component {
    static template = "gn_purchase_dashboard.PurchaseAlertsPanel";
    static components = { PurchaseEmptyState };
    static props = {
        alerts: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        lastUpdate: { type: String, optional: true },
        onAlertClick: { type: Function, optional: true },
    };

    get sortedAlerts() {
        const items = [...(this.props.alerts?.items || [])];
        return items.sort((a, b) => {
            const sa = SEVERITY_ORDER[a.severity] ?? 5;
            const sb = SEVERITY_ORDER[b.severity] ?? 5;
            return sa - sb;
        });
    }

    severityIcon(sev) {
        return {
            critical: "fa-exclamation-circle",
            high: "fa-exclamation-triangle",
            warning: "fa-warning",
            medium: "fa-info-circle",
            info: "fa-info-circle",
        }[sev] || "fa-circle";
    }

    severityLabel(sev) {
        return {
            critical: "Crítica",
            high: "Alta",
            warning: "Alta",
            medium: "Media",
            info: "Baja",
        }[sev] || "Info";
    }

    onClick(alert, ev) {
        ev.stopPropagation();
        if (this.props.onAlertClick) this.props.onAlertClick(alert);
    }

    onActionClick(alert, ev) {
        ev.stopPropagation();
        if (this.props.onAlertClick) this.props.onAlertClick(alert);
    }
}
