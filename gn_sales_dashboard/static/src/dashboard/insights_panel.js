/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { SalesEmptyState } from "./empty_state";

export class SalesInsightsPanel extends Component {
    static template = "gn_sales_dashboard.SalesInsightsPanel";
    static components = { SalesEmptyState };
    static props = {
        insights: { type: Array, optional: true },
        loading: { type: Boolean, optional: true },
        onInsightClick: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ expanded: false });
    }

    get visibleInsights() {
        const items = this.props.insights || [];
        if (this.state.expanded) return items;
        return items.slice(0, 5);
    }

    severityIcon(sev) {
        return {
            critical: "fa-exclamation-circle",
            warning: "fa-warning",
            info: "fa-lightbulb-o",
        }[sev] || "fa-info-circle";
    }

    onClick(insight, ev) {
        ev.stopPropagation();
        if (this.props.onInsightClick) {
            this.props.onInsightClick(insight);
        }
    }
}
