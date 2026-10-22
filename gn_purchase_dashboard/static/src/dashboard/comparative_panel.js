/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { formatMonetary } from "@web/views/fields/formatters";

const MODEL = "purchase.dashboard.service";

export class PurchaseComparativePanel extends Component {
    static template = "gn_purchase_dashboard.ComparativePanel";
    static props = {
        open: Boolean,
        filters: Object,
        filterOptions: Object,
        currencyId: Number,
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            compareType: "vendor",
            entityA: false,
            entityB: false,
            result: null,
            loading: false,
        });
    }

    get entityOptions() {
        const map = {
            vendor: this.props.filterOptions.vendors || [],
            buyer: this.props.filterOptions.buyers || [],
            branch: this.props.filterOptions.branches || [],
            category: this.props.filterOptions.categories || [],
            company: this.props.filterOptions.companies || [],
        };
        return map[this.state.compareType] || [];
    }

    async runCompare() {
        if (!this.state.entityA || !this.state.entityB) return;
        this.state.loading = true;
        try {
            this.state.result = await this.orm.call(MODEL, "get_comparative_analysis", [
                this.props.filters,
                this.state.compareType,
                this.state.entityA,
                this.state.entityB,
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    fmt(row, side) {
        const v = side === "a" ? row.value_a : row.value_b;
        if (row.format === "currency") return formatMonetary(v, { currencyId: this.props.currencyId });
        if (row.format === "days") return `${Number(v).toFixed(1)} d`;
        return Number(v).toLocaleString();
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }
}
