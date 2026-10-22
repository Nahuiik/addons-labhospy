/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { downloadBase64File } from "./export_utils";

const MODEL = "purchase.dashboard.service";

export class PurchaseDataTable extends Component {
    static template = "gn_purchase_dashboard.PurchaseDataTable";
    static props = {
        tableKey: String,
        title: { type: String, optional: true },
        filters: Object,
        currencyId: { type: Number, optional: true },
        pageSize: { type: Number, optional: true },
        onRowClick: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, error: null, rows: [], columns: [],
            search: "", sortField: "", sortDir: "desc",
            page: 1, pages: 1, total: 0, exporting: false,
        });
        this._debouncedLoad = debounce(() => this.loadPage(), 350);
        onWillStart(() => this.loadPage());
        onWillUpdateProps((next) => {
            if (next.tableKey !== this.props.tableKey
                || JSON.stringify(next.filters) !== JSON.stringify(this.props.filters)) {
                this.state.page = 1;
                this.loadPage();
            }
        });
    }

    get tableSubtitle() {
        return _t("%s registros · máx. 10 por página", this.state.total);
    }

    get pagerLabel() {
        return _t("Página %s de %s", this.state.page, this.state.pages);
    }

    async loadPage() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const order = this.state.sortField ? `${this.state.sortField} ${this.state.sortDir}` : "";
            const data = await this.orm.call(MODEL, "get_table_page", [
                this.props.filters, this.props.tableKey,
                this.state.page, this.props.pageSize || 10,
                this.state.search, order,
            ]);
            this.state.rows = data.rows || [];
            this.state.columns = data.columns || [];
            this.state.pages = data.pages || 1;
            this.state.total = data.total || 0;
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    formatCell(row, col) {
        const v = row[col.key];
        if (v === undefined || v === null || v === "") return "—";
        if (col.type === "currency") return formatMonetary(v, { currencyId: this.props.currencyId });
        if (col.type === "number") return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
        return v;
    }

    colClass(col) {
        let cls = col.sortable ? "gn-pd-table__sortable" : "";
        if (col.type === "currency" || col.type === "number") cls += " gn-pd-table__col--num";
        return cls;
    }

    cellClass(col) {
        if (col.type === "currency" || col.type === "number") return "gn-pd-table__cell--num";
        return "";
    }

    isBadgeColumn(key) {
        if (this.isProgressColumn(key)) return false;
        return ["rating", "price_var_pct", "variation_pct", "growth_pct"].includes(key);
    }

    isProgressColumn(key) {
        return ["share_pct", "compliance_pct"].includes(key);
    }

    badgeClass(row, key) {
        const v = row[key];
        if (key === "rating") {
            return `gn-pd-table__badge--${row.rating || "neutral"}`;
        }
        const n = Number(v) || 0;
        if (n > 10) return "gn-pd-table__badge--danger";
        if (n > 5) return "gn-pd-table__badge--warn";
        if (n < -5) return "gn-pd-table__badge--success";
        return "gn-pd-table__badge--neutral";
    }

    badgeLabel(row, key) {
        const v = row[key];
        if (key === "rating") {
            return { good: "A", warn: "B", bad: "C" }[row.rating] || "—";
        }
        const n = Number(v);
        if (Number.isNaN(n)) return v;
        return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
    }

    progressPct(row, key) {
        return Math.max(0, Math.min(100, Number(row[key]) || 0));
    }

    footerCell(col) {
        const rows = this.state.rows;
        if (!rows.length) return "";
        const sum = rows.reduce((acc, r) => acc + (Number(r[col.key]) || 0), 0);
        if (col.type === "currency") {
            return formatMonetary(sum, { currencyId: this.props.currencyId });
        }
        return sum.toLocaleString(undefined, { maximumFractionDigits: 1 });
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.page = 1;
        this._debouncedLoad();
    }

    toggleSort(col) {
        if (!col.sortable) return;
        if (this.state.sortField === col.key) {
            this.state.sortDir = this.state.sortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = col.key;
            this.state.sortDir = "desc";
        }
        this.loadPage();
    }

    goPage(delta) {
        const next = this.state.page + delta;
        if (next < 1 || next > this.state.pages) return;
        this.state.page = next;
        this.loadPage();
    }

    async exportCsv() {
        this.state.exporting = true;
        try {
            const r = await this.orm.call(MODEL, "export_widgets_csv", [this.props.filters, this.props.tableKey]);
            downloadBase64File(r);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.exporting = false;
        }
    }

    onRowClick(row) {
        if (this.props.onRowClick) this.props.onRowClick(row);
    }
}
