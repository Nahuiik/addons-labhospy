/** @odoo-module **/

import { Component } from "@odoo/owl";

export class DataTable extends Component {
    static template = "gts_customer_advance.DataTable";
    static props = {
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    fmt(v) {
        if (v === undefined || v === null) return "0.00";
        return Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    onRowClick(rowKey) {
        if (this.props.onDrilldown) {
            this.props.onDrilldown(rowKey);
        }
    }
}
