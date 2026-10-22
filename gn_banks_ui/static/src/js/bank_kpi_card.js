/** @odoo-module **/

import { Component } from "@odoo/owl";

export class BankKpiCard extends Component {
    static template = "gn_banks_ui.BankKpiCard";
    static props = {
        label: String,
        value: [String, Number],
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
    };

    get toneClass() {
        return `gn-bk-kpi gn-bk-kpi--${this.props.tone || "neutral"}`;
    }
}
