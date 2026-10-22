/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { PurchaseEmptyState } from "./empty_state";

export class PurchaseInsightsPanel extends Component {
    static template = "gn_purchase_dashboard.PurchaseInsightsPanel";
    static components = { PurchaseEmptyState };
    static props = {
        insights: { type: Array, optional: true },
        loading: { type: Boolean, optional: true },
        onInsightClick: { type: Function, optional: true },
    };

    severityIcon(sev) {
        return { critical: "fa-exclamation-circle", warning: "fa-warning", info: "fa-lightbulb-o" }[sev] || "fa-info-circle";
    }

    impactLabel(sev) {
        return { critical: "Alto impacto", warning: "Impacto medio", info: "Informativo" }[sev] || "Informativo";
    }

    onClick(insight, ev) {
        ev.stopPropagation();
        if (this.props.onInsightClick) this.props.onInsightClick(insight);
    }
}
