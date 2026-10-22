/** @odoo-module **/

import { Component } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { GnBanksJournalMultiSelector } from "./journal_multi_selector";
import { filterBarLabels } from "./dashboard_labels";

const { DateTime } = luxon;

export class GnBanksDashboardFilterBar extends Component {
    static template = "gn_banks_dashboard.GnBanksDashboardFilterBar";
    static components = { GnBanksJournalMultiSelector, DateTimeInput };
    static props = {
        draftFilters: Object,
        filterOptions: Object,
        loading: Boolean,
        onDraftChanged: Function,
        onApply: Function,
        onReset: Function,
    };

    get journals() {
        return this.props.filterOptions.journals || [];
    }

    get allJournalIds() {
        return this.journals.map((j) => j.id);
    }

    get journalMeta() {
        const meta = {};
        for (const j of this.journals) {
            meta[j.id] = { bank_name: j.bank_name || "" };
        }
        return meta;
    }

    get journalResIds() {
        return this.props.draftFilters.journal_ids || [];
    }

    get companyId() {
        return this.props.draftFilters.company_id;
    }

    get flowSource() {
        return this.props.draftFilters.flow_source || "treasury";
    }

    onFlowSourceChange(value) {
        if (value !== this.flowSource) {
            this.props.onDraftChanged({ flow_source: value });
        }
    }

    get showCompany() {
        return this.props.filterOptions.multi_company;
    }

    get labels() {
        return filterBarLabels();
    }

    get months() {
        const locale = luxon.Settings.defaultLocale || "es";
        return Array.from({ length: 12 }, (_, idx) => {
            const value = idx + 1;
            const raw = DateTime.local(2024, value, 1).setLocale(locale).toFormat("LLLL");
            return {
                value,
                label: raw.charAt(0).toUpperCase() + raw.slice(1),
            };
        });
    }

    get selectedMonth() {
        return this._periodAnchor().month;
    }

    get selectedYear() {
        return this._periodAnchor().year;
    }

    get dateFromValue() {
        return this._parseDate(this.props.draftFilters.date_from);
    }

    get dateToValue() {
        return this._parseDate(this.props.draftFilters.date_to);
    }

    _periodAnchor() {
        const from = this.props.draftFilters.date_from;
        if (from) {
            return DateTime.fromISO(from);
        }
        const to = this.props.draftFilters.date_to;
        if (to) {
            return DateTime.fromISO(to);
        }
        return DateTime.local();
    }

    _parseDate(val) {
        if (!val) {
            return DateTime.local().startOf("month");
        }
        return DateTime.fromISO(val);
    }

    _applyMonthYear(month, year) {
        const safeYear = year || DateTime.local().year;
        const safeMonth = Math.min(12, Math.max(1, month || 1));
        const start = DateTime.local(safeYear, safeMonth, 1).startOf("month");
        const end = start.endOf("month");
        this.props.onDraftChanged({
            date_from: start.toISODate(),
            date_to: end.toISODate(),
        });
    }

    onMonthChange(ev) {
        this._applyMonthYear(parseInt(ev.target.value, 10), this.selectedYear);
    }

    onYearChange(ev) {
        const year = parseInt(ev.target.value, 10);
        if (year >= 2000 && year <= 2100) {
            this._applyMonthYear(this.selectedMonth, year);
        }
    }

    onDateFromChange(date) {
        this.props.onDraftChanged({ date_from: date ? date.toISODate() : false });
    }

    onDateToChange(date) {
        this.props.onDraftChanged({ date_to: date ? date.toISODate() : false });
    }

    onCompanyChange(ev) {
        const companyId = parseInt(ev.target.value, 10);
        this.props.onDraftChanged({
            company_id: companyId,
            journal_ids: [],
        });
    }

    onJournalsUpdate(resIds) {
        this.props.onDraftChanged({ journal_ids: resIds });
    }
}
