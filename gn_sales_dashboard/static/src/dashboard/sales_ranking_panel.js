/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";

export class SalesRankingPanel extends Component {
    static template = "gn_sales_dashboard.SalesRankingPanel";
    static props = {
        title: String,
        rows: { type: Array, optional: true },
        type: { type: String, optional: true }, // sellers | teams
        currencyId: { type: Number, optional: true },
        loading: { type: Boolean, optional: true },
        onRowClick: { type: Function, optional: true },
    };

    fmtMoney(v) {
        return formatMonetary(v || 0, { currencyId: this.props.currencyId });
    }

    fmtPct(v) {
        return `${Number(v || 0).toFixed(1)}%`;
    }

    medalIcon(rank) {
        if (rank === 1) return "🥇";
        if (rank === 2) return "🥈";
        if (rank === 3) return "🥉";
        return rank;
    }

    onClick(row) {
        if (this.props.onRowClick) {
            this.props.onRowClick(row);
        }
    }
}
