/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import {
    ALL_COLUMNS, COLUMN_TOOLTIPS, CENTER_COLUMNS, STICKY_COLUMNS,
    formatMoney as fmtMoney, isMoneyColumn, overdueClass, statusBadgeClass,
} from "./format_utils";

export class InvPayDataTable extends Component {
    static template = "gn_accounting_reports.InvPayDataTable";
    static props = {
        table: Object,
        columns: Array,
        density: { type: String, optional: true },
        currencyId: Number,
        loading: Boolean,
        onSort: Function,
        onPageChange: Function,
        onPageSizeChange: { type: Function, optional: true },
        onGoToPage: { type: Function, optional: true },
        onRowClick: Function,
        onSearch: Function,
        search: { type: String, optional: true },
        groupBy: { type: String, optional: true },
        onGroupBy: Function,
        onColumnsChange: Function,
        onDensityChange: Function,
        onResetToolbar: { type: Function, optional: true },
        onToggleGroup: { type: Function, optional: true },
        onExpandRow: { type: Function, optional: true },
        expandedRows: { type: Object, optional: true },
        expandedGroups: { type: Object, optional: true },
        title: { type: String, optional: true },
        showMeta: { type: Boolean, optional: true },
        mode: { type: String, optional: true },
    };

    setup() {
        this.allColumns = ALL_COLUMNS;
        this.state = useState({ showColumnPicker: false, goToPage: "" });
    }

    get columnDefs() {
        const ids = this.props.columns || [];
        return ALL_COLUMNS.filter((c) => ids.includes(c.id));
    }

    get densityClass() {
        const map = { comfortable: "", compact: "o_inv_pay_table--compact", dense: "o_inv_pay_table--dense" };
        return map[this.props.density || "comfortable"] || "";
    }

    get metaLabel() {
        const m = this.props.table?.meta;
        if (!m) return `${this.props.table?.total_rows || 0} registros`;
        return `${m.payment_count || 0} pagos · ${m.invoice_count || 0} facturas · ${m.client_count || 0} clientes`;
    }

    get displayGroups() {
        return this.props.table?.groups || null;
    }

    get flatRows() {
        if (this.displayGroups) return null;
        return this.props.table?.rows || [];
    }

    toggleColumnPicker() {
        this.state.showColumnPicker = !this.state.showColumnPicker;
    }

    isColumnVisible(colId) {
        return (this.props.columns || []).includes(colId);
    }

    isSticky(colId) {
        return STICKY_COLUMNS.has(colId);
    }

    colAlign(colId) {
        if (isMoneyColumn(colId)) return "text-end";
        if (CENTER_COLUMNS.has(colId)) return "text-center";
        return "";
    }

    colTooltip(colId) {
        return COLUMN_TOOLTIPS[colId] || "";
    }

    onToggleColumn(colId, ev) {
        const checked = ev.target.checked;
        let cols = [...(this.props.columns || [])];
        if (checked && !cols.includes(colId)) {
            cols.push(colId);
        } else if (!checked) {
            cols = cols.filter((c) => c !== colId);
            if (cols.length < 3) return;
        }
        this.props.onColumnsChange(cols);
    }

    onDensitySelect(ev) {
        this.props.onDensityChange(ev.target.value);
    }

    onPageSizeSelect(ev) {
        this.props.onPageSizeChange?.(parseInt(ev.target.value, 10));
    }

    submitGoToPage() {
        const p = parseInt(this.state.goToPage, 10);
        if (p > 0) this.props.onGoToPage?.(p);
    }

    cellValue(row, col) {
        const v = row[col];
        if (col === "payment_state" && !v) return row.invoice_status || "—";
        if (isMoneyColumn(col) && typeof v === "number") {
            return fmtMoney(v, this.props.currencyId);
        }
        return v ?? "—";
    }

    totalForColumn(colId) {
        const t = this.props.table?.totals || {};
        const map = {
            amount_total: t.amount_total,
            amount_applied: t.amount_applied,
            balance_pending: t.balance_pending,
            amount_untaxed: t.amount_untaxed,
            amount_tax: t.amount_tax,
            days_overdue: t.avg_days_overdue != null ? `${t.avg_days_overdue} prom.` : null,
            invoice_number: t.invoice_count != null ? String(t.invoice_count) : null,
            payment_receipt: t.payment_count != null ? String(t.payment_count) : null,
        };
        if (colId in map && map[colId] != null) {
            if (isMoneyColumn(colId)) return fmtMoney(map[colId], this.props.currencyId);
            return map[colId];
        }
        return null;
    }

    statusClass(row) {
        return statusBadgeClass(row.payment_state);
    }

    priorityClass(row) {
        const tone = row.collection_priority_tone || "info";
        return `o_inv_pay_priority--${tone}`;
    }

    overdueRowClass(row) {
        return overdueClass(row.days_overdue);
    }

    sortIcon(col) {
        if (this.props.table?.sort_by !== col) return "fa-sort text-muted";
        return this.props.table?.sort_dir === "asc" ? "fa-sort-asc" : "fa-sort-desc";
    }

    formatMoney(value) {
        return fmtMoney(value, this.props.currencyId);
    }

    isExpanded(row) {
        return this.props.expandedRows?.[row.invoice_id];
    }

    isGroupCollapsed(groupName) {
        return this.props.expandedGroups?.[groupName] === false;
    }
}
