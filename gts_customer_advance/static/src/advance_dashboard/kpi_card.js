/** @odoo-module **/

import { Component } from "@odoo/owl";

export class KpiCard extends Component {
    static template = "gts_customer_advance.KpiCard";
    static props = {
        label: String,
        value: String,
        icon: { type: String, optional: true },
        color: { type: String, optional: true },
    };

    get colorClass() {
        const c = this.props.color;
        if (c === "green") return "gts-advance-kpi--success";
        if (c === "yellow") return "gts-advance-kpi--warning";
        if (c === "red") return "gts-advance-kpi--danger";
        return "";
    }
}
