/** @odoo-module **/

import { Component } from "@odoo/owl";

export class SalesTop5Panel extends Component {
    static template = "gn_sales_dashboard.SalesTop5Panel";
    static props = {
        top5: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        fmtMoney: Function,
        onViewAll: Function,
        onRowClick: { type: Function, optional: true },
    };

    onView(section) {
        if (this.props.onViewAll) {
            this.props.onViewAll(section);
        }
    }

    onClickRow(section, row) {
        if (this.props.onRowClick) {
            this.props.onRowClick(section, row);
        }
    }
}
