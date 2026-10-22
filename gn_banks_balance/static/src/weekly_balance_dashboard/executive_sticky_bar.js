/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";

export class ExecutiveStickyBar extends Component {
    static template = "gn_banks_balance.ExecutiveStickyBar";
    static props = {
        visible: Boolean,
        metrics: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    fmt(amount) {
        if (amount === null || amount === undefined) {
            return "—";
        }
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }

    riskClass(level) {
        const map = { green: "success", yellow: "warning", red: "danger" };
        return map[level] || "secondary";
    }
}
