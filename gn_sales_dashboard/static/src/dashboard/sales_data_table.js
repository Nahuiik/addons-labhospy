/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

const MODEL = "sales.dashboard.service";

export class SalesDataTable extends Component {
    static template = "gn_sales_dashboard.SalesDataTable";
    static props = {
        tableKey: String,
        filters: Object,
        currencyId: { type: Number, optional: true },
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
            search: "",
            sortField: "date",
            sortDir: "desc",
            page: 1,
            pages: 1,
            total: 0,
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

    async loadPage() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const order = this.state.sortField
                ? `${this.state.sortField} ${this.state.sortDir}`
                : "";
            const data = await this.orm.call(MODEL, "get_table_page", [
                this.props.filters,
                this.props.tableKey,
                this.state.page,
                this.props.pageSize || 20,
                this.state.search,
                order,
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
        if (v === undefined || v === null) return "—";
        if (col.type === "currency") {
            return formatMonetary(v, { currencyId: this.props.currencyId });
        }
        if (col.type === "number") {
            return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
        }
        return v;
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

    onRowClick(row) {
        if (this.props.onRowClick) {
            this.props.onRowClick(row);
        }
    }
}
