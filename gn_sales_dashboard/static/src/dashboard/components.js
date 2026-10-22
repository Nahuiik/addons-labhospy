/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { debounce } from "@web/core/utils/timing";

const SECONDARY_FILTER_FIELDS = [
    "compare_mode", "date_from", "date_to", "journal_id",
    "warehouse_id", "category_id", "channel_id", "order_state",
];

export class SalesFilterBar extends Component {
    static template = "gn_sales_dashboard.SalesFilterBar";
    static props = {
        filterOptions: Object,
        draftFilters: Object,
        labels: Object,
        applying: { type: Boolean, optional: true },
        onSelect: Function,
        onApply: Function,
        onReset: Function,
    };

    setup() {
        this.state = useState({ showMore: false });
        this._debouncedApply = debounce(() => this.props.onApply(), 450);
    }

    toggleMore() {
        this.state.showMore = !this.state.showMore;
    }

    get secondaryActiveCount() {
        const f = this.props.draftFilters;
        let n = 0;
        for (const field of SECONDARY_FILTER_FIELDS) {
            const val = f[field];
            if (!val) continue;
            if (field === "compare_mode" && val === "previous") continue;
            n += 1;
        }
        return n;
    }

    get moreFiltersLabel() {
        const n = this.secondaryActiveCount;
        return n ? _t("Más filtros · %s", n) : _t("Más filtros");
    }

    _intVal(ev) {
        return ev.target.value ? parseInt(ev.target.value, 10) : false;
    }

    _select(field, value, autoApply = false) {
        this.props.onSelect(field, value);
        if (autoApply) {
            this._debouncedApply();
        }
    }

    onPeriodChange(ev) { this._select("period", ev.target.value, true); }
    onCompareChange(ev) { this._select("compare_mode", ev.target.value); }
    onCompanyChange(ev) { this._select("company_id", this._intVal(ev), true); }
    onDateFromChange(ev) {
        this.props.onSelect("date_from", ev.target.value || false);
        this.props.onSelect("period", "custom");
    }
    onDateToChange(ev) {
        this.props.onSelect("date_to", ev.target.value || false);
        this.props.onSelect("period", "custom");
    }
    onBranchChange(ev) { this._select("branch_id", this._intVal(ev)); }
    onTeamChange(ev) { this._select("team_id", this._intVal(ev)); }
    onUserChange(ev) { this._select("user_id", this._intVal(ev)); }
    onJournalChange(ev) { this._select("journal_id", this._intVal(ev)); }
    onWarehouseChange(ev) { this._select("warehouse_id", this._intVal(ev)); }
    onCategoryChange(ev) { this._select("category_id", this._intVal(ev)); }
    onChannelChange(ev) { this._select("channel_id", this._intVal(ev)); }
    onOrderStateChange(ev) { this._select("order_state", ev.target.value || false); }

    onApplyClick() {
        this.props.onApply();
    }

    onResetClick() {
        this.props.onReset();
    }
}
