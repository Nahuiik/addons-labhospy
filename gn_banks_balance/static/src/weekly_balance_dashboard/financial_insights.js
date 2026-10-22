/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";

const SEVERITY_ORDER = { danger: 0, warning: 1, success: 2, info: 3 };
const SEVERITY_LABELS = {
    danger: "Riesgo",
    warning: "Atención",
    success: "Positivo",
    info: "Info",
};

export class FinancialInsights extends Component {
    static template = "gn_banks_balance.FinancialInsights";
    static props = {
        insights: { type: Array, optional: true },
        currencyId: { type: Number, optional: true },
    };

    get sortedInsights() {
        const list = [...(this.props.insights || [])];
        return list.sort((a, b) => {
            const sa = SEVERITY_ORDER[a.severity || a.type] ?? 9;
            const sb = SEVERITY_ORDER[b.severity || b.type] ?? 9;
            return sa - sb;
        });
    }

    severityClass(severity) {
        return `gn-wb-insight-card--${severity || "info"}`;
    }

    severityLabel(severity) {
        return SEVERITY_LABELS[severity || "info"] || SEVERITY_LABELS.info;
    }

    fmtValue(value) {
        if (value === null || value === undefined) {
            return "";
        }
        if (this.props.currencyId) {
            return formatMonetary(value, { currencyId: this.props.currencyId });
        }
        return `${Number(value).toFixed(2)}%`;
    }
}
