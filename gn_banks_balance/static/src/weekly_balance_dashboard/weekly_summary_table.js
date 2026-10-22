/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { BankDetailExpandable } from "./bank_detail_expandable";

export class WeeklySummaryTable extends Component {
    static template = "gn_banks_balance.WeeklySummaryTable";
    static components = { BankDetailExpandable };
    static props = {
        weeks: Array,
        currencyId: Number,
        onDrilldown: Function,
        weekSync: { type: Object, optional: true },
        highlightedWeekKey: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ expanded: {}, highlightKey: null });
        this._unsub = null;
        onMounted(() => {
            if (this.props.weekSync) {
                this._unsub = this.props.weekSync.subscribe((key) => {
                    this.state.highlightKey = key;
                });
            }
        });
        onWillUnmount(() => {
            if (this._unsub) {
                this._unsub();
            }
        });
    }

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.props.currencyId });
    }

    toggleExpand(weekKey) {
        this.state.expanded[weekKey] = !this.state.expanded[weekKey];
    }

    isExpanded(weekKey) {
        return Boolean(this.state.expanded[weekKey]);
    }

    isHighlighted(week) {
        const key = this.state.highlightKey || this.props.highlightedWeekKey;
        return key && week.key === key;
    }

    onRowEnter(week) {
        this.props.weekSync?.setHighlightedWeek(week.key);
    }

    onRowLeave() {
        this.props.weekSync?.clear();
    }

    deltaClass(value) {
        if (value > 0) {
            return "gn-wb-delta--up";
        }
        if (value < 0) {
            return "gn-wb-delta--down";
        }
        return "gn-wb-delta--flat";
    }

    deltaIcon(value) {
        if (value > 0) {
            return "fa-arrow-up";
        }
        if (value < 0) {
            return "fa-arrow-down";
        }
        return "fa-minus";
    }

    onCellClick(week, metric, journalId) {
        this.props.onDrilldown({
            week_no: week.week_no,
            journal_id: journalId || false,
            metric,
        });
    }
}
