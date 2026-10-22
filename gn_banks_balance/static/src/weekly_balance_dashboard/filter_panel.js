/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { DateTimeInput } from "@web/core/datetime/datetime_input";

const { DateTime } = luxon;

export class BanksWeeklyBalanceFilterPanel extends Component {
    static template = "gn_banks_balance.BanksWeeklyBalanceFilterPanel";
    static components = { DateTimeInput };
    static props = {
        filters: Object,
        filterOptions: Object,
        dirty: Boolean,
        onDraftChanged: Function,
        onApply: Function,
        onClear: Function,
    };

    get months() {
        return this.props.filterOptions.months || [];
    }

    get journals() {
        return this.props.filterOptions.journals || [];
    }

    get companies() {
        return this.props.filterOptions.companies || [];
    }

    get groupByOptions() {
        return this.props.filterOptions.group_by_options || [];
    }

    get showCompany() {
        return this.props.filterOptions.multi_company;
    }

    get useCustomRange() {
        return Boolean(this.props.filters.use_custom_range);
    }

    get dateFromValue() {
        return this._parseDate(this.props.filters.date_from);
    }

    get dateToValue() {
        return this._parseDate(this.props.filters.date_to);
    }

    get selectedJournalCount() {
        return (this.props.filters.journal_ids || []).length;
    }

    get totalJournalCount() {
        return this.journals.length;
    }

    get bankSelectionLabel() {
        const selected = this.selectedJournalCount;
        const total = this.totalJournalCount;
        if (!total) {
            return _t("Sin bancos disponibles");
        }
        if (selected === 0) {
            return _t("Ningún banco seleccionado");
        }
        if (selected === total) {
            return _t("Todos los bancos (%s)", total);
        }
        return _t("%s de %s bancos", selected, total);
    }

    get hasNoBanksSelected() {
        return this.totalJournalCount > 0 && this.selectedJournalCount === 0;
    }

    _parseDate(val) {
        if (!val) {
            return DateTime.local().startOf("month");
        }
        if (typeof val === "string") {
            return DateTime.fromISO(val);
        }
        return val;
    }

    isJournalSelected(journalId) {
        return (this.props.filters.journal_ids || []).includes(journalId);
    }

    onCompanyChange(ev) {
        this.props.onDraftChanged({ company_id: parseInt(ev.target.value, 10) });
    }

    onYearChange(ev) {
        this.props.onDraftChanged({ year: parseInt(ev.target.value, 10) || "" });
    }

    onMonthChange(ev) {
        this.props.onDraftChanged({ month: ev.target.value, use_custom_range: false });
    }

    onGroupByChange(ev) {
        this.props.onDraftChanged({ group_by: ev.target.value });
    }

    onCompareToggle(ev) {
        this.props.onDraftChanged({ compare_previous: ev.target.checked });
    }

    onCustomRangeToggle(ev) {
        const useCustom = ev.target.checked;
        const patch = { use_custom_range: useCustom };
        if (useCustom && !this.props.filters.date_from) {
            const now = DateTime.local();
            patch.date_from = now.startOf("month").toISODate();
            patch.date_to = now.endOf("month").toISODate();
        }
        this.props.onDraftChanged(patch);
    }

    onDateFromChange(date) {
        this.props.onDraftChanged({
            date_from: date ? date.toISODate() : false,
            use_custom_range: true,
        });
    }

    onDateToChange(date) {
        this.props.onDraftChanged({
            date_to: date ? date.toISODate() : false,
            use_custom_range: true,
        });
    }

    onJournalToggle(journalId) {
        const current = [...(this.props.filters.journal_ids || [])];
        const idx = current.indexOf(journalId);
        if (idx >= 0) {
            current.splice(idx, 1);
        } else {
            current.push(journalId);
        }
        this.props.onDraftChanged({ journal_ids: current });
    }

    onSelectAllJournals() {
        this.props.onDraftChanged({
            journal_ids: this.journals.map((j) => j.id),
        });
    }

    onClearJournals() {
        this.props.onDraftChanged({ journal_ids: [] });
    }

    onQuickPeriod(period) {
        const now = DateTime.local();
        let from = now.startOf("month");
        let to = now.endOf("month");
        if (period === "last_month") {
            from = now.minus({ months: 1 }).startOf("month");
            to = now.minus({ months: 1 }).endOf("month");
        }
        this.props.onDraftChanged({
            use_custom_range: false,
            date_from: false,
            date_to: false,
            year: from.year,
            month: String(from.month),
        });
    }
}
