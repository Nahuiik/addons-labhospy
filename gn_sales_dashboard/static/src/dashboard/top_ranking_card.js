/** @odoo-module **/

import { Component } from "@odoo/owl";
import { SalesEmptyState } from "./empty_state";

export class SalesTopRankingCard extends Component {
    static template = "gn_sales_dashboard.SalesTopRankingCard";
    static components = { SalesEmptyState };
    static props = {
        title: String,
        section: String,
        rows: { type: Array, optional: true },
        type: { type: String, optional: true }, // sellers | products | customers
        loading: { type: Boolean, optional: true },
        fmtMoney: Function,
        onViewAll: Function,
        onRowClick: { type: Function, optional: true },
    };

    onViewAllClick(ev) {
        ev.stopPropagation();
        if (this.props.onViewAll) {
            this.props.onViewAll(this.props.section);
        }
    }

    onRowClick(row, ev) {
        ev.stopPropagation();
        if (this.props.onRowClick) {
            this.props.onRowClick(this.props.section, row);
        }
    }
}
