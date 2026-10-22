/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { downloadCsv, downloadBase64File } from "./export_utils";
import { formatDashboardDateTime } from "./date_utils";

const MODEL = "inventory.dashboard.service";

/**
 * Tabla avanzada reutilizable con paginación servidor, filtros por columna,
 * ordenamiento, columnas configurables y selección múltiple.
 */
export class AdvancedDataTable extends Component {
    static template = "dev_advance_inventory_dashboard.AdvancedDataTable";
    static props = {
        tableKey: String,
        filters: Object,
        pageSize: { type: Number, optional: true },
        onRowClick: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: null,
            rows: [],
            columns: [],
            visibleColumnKeys: [],
            columnFilters: {},
            sortField: "",
            sortDir: "asc",
            search: "",
            page: 1,
            pages: 1,
            total: 0,
            selectedIds: [],
            showColumnPicker: false,
        });
        this._debouncedLoad = debounce(() => this.loadPage(), 400);
        onWillStart(() => this.loadPage());
        onWillUpdateProps((nextProps) => {
            if (nextProps.tableKey !== this.props.tableKey
                || JSON.stringify(nextProps.filters) !== JSON.stringify(this.props.filters)) {
                this.state.page = 1;
                this.loadPage();
            }
        });
    }

    get visibleColumns() {
        const keys = this.state.visibleColumnKeys.length
            ? this.state.visibleColumnKeys
            : this.state.columns.map((c) => c.key);
        return this.state.columns.filter((c) => keys.includes(c.key));
    }

    get allSelected() {
        return this.state.rows.length > 0
            && this.state.selectedIds.length === this.state.rows.length;
    }

    async loadPage() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const order = this.state.sortField
                ? `${this.state.sortField} ${this.state.sortDir}`
                : "";
            const data = await this.orm.call(MODEL, "get_table_page_advanced", [
                this.props.filters,
                this.props.tableKey,
                this.state.page,
                this.props.pageSize || 25,
                this.state.search,
                order,
                this.state.columnFilters,
                this.state.visibleColumnKeys.length ? this.state.visibleColumnKeys : null,
            ]);
            this.state.rows = data.rows || [];
            this.state.columns = data.columns || [];
            if (!this.state.visibleColumnKeys.length && this.state.columns.length) {
                this.state.visibleColumnKeys = this.state.columns.map((c) => c.key);
            }
            this.state.pages = data.pages || 1;
            this.state.total = data.total || 0;
            this.state.selectedIds = [];
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.page = 1;
        this._debouncedLoad();
    }

    onColumnFilter(col, ev) {
        this.state.columnFilters = {
            ...this.state.columnFilters,
            [col.key]: ev.target.value,
        };
        this.state.page = 1;
        this._debouncedLoad();
    }

    toggleSort(col) {
        if (!col.sortable) return;
        if (this.state.sortField === col.key) {
            this.state.sortDir = this.state.sortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = col.key;
            this.state.sortDir = "asc";
        }
        this.loadPage();
    }

    toggleColumn(key) {
        const keys = new Set(this.state.visibleColumnKeys);
        if (keys.has(key)) keys.delete(key);
        else keys.add(key);
        this.state.visibleColumnKeys = [...keys];
    }

    toggleSelectAll(ev) {
        if (ev.target.checked) {
            this.state.selectedIds = this.state.rows.map((r) => r.id);
        } else {
            this.state.selectedIds = [];
        }
    }

    toggleSelectRow(rowId) {
        const set = new Set(this.state.selectedIds);
        if (set.has(rowId)) set.delete(rowId);
        else set.add(rowId);
        this.state.selectedIds = [...set];
    }

    isSelected(rowId) {
        return this.state.selectedIds.includes(rowId);
    }

    changePage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.state.pages) return;
        this.state.page = next;
        this.loadPage();
    }

    exportCsv() {
        const cols = this.visibleColumns;
        const headers = cols.map((c) => c.label);
        const rows = this.state.rows.map((r) => cols.map((c) => r[c.key] ?? ""));
        downloadCsv(`${this.props.tableKey}.csv`, rows, headers);
    }

    async exportExcel() {
        const result = await this.orm.call(MODEL, "export_table_data", [
            this.props.filters,
            this.props.tableKey,
            "csv",
            this.state.search,
        ]);
        downloadBase64File(result.filename, result.data, result.mimetype);
    }

    onRowClick(row) {
        if (this.props.onRowClick) {
            this.props.onRowClick(row);
        }
    }

    cellValue(row, col) {
        const v = row[col.key];
        if (col.key === "state") {
            return v;
        }
        if (col.key === "date") {
            return formatDashboardDateTime(v);
        }
        return v ?? "";
    }
}
