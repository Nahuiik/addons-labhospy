/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const PAGE_SIZE = 80;

export class GnStockAgePreview extends Component {
    static template = "gn_stock_kardex.StockAgePreview";

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            rows: [],
            brackets: [],
            companyName: "",
            warehouseName: "",
            breakdownDays: 60,
            search: "",
            currentPage: 1,
        });
        this._readContext();
    }

    _readContext() {
        const ctx = this.props.action.context || {};
        this.state.rows = ctx.age_rows || [];
        this.state.brackets = ctx.age_brackets || [];
        this.state.companyName = ctx.age_company_name || "";
        this.state.warehouseName = ctx.age_warehouse_name || "";
        this.state.breakdownDays = ctx.age_breakdown_days || 60;
    }

    getFilteredRows() {
        const term = this.state.search.toLowerCase().trim();
        if (!term) return this.state.rows;
        return this.state.rows.filter(
            (r) =>
                r.product_name.toLowerCase().includes(term) ||
                (r.default_code && r.default_code.toLowerCase().includes(term)) ||
                (r.categ_name && r.categ_name.toLowerCase().includes(term))
        );
    }

    getTotalPages() {
        return Math.max(1, Math.ceil(this.getFilteredRows().length / PAGE_SIZE));
    }

    getVisibleRows() {
        const all = this.getFilteredRows();
        const start = (this.state.currentPage - 1) * PAGE_SIZE;
        return all.slice(start, start + PAGE_SIZE);
    }

    getPageFrom() {
        const total = this.getFilteredRows().length;
        if (!total) return 0;
        return (this.state.currentPage - 1) * PAGE_SIZE + 1;
    }

    getPageTo() {
        return Math.min(this.state.currentPage * PAGE_SIZE, this.getFilteredRows().length);
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.currentPage = 1;
    }

    prevPage() { if (this.state.currentPage > 1) this.state.currentPage--; }
    nextPage() { if (this.state.currentPage < this.getTotalPages()) this.state.currentPage++; }

    fmt(n) {
        if (n === undefined || n === null || Number.isNaN(n)) return "0.00";
        return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    async openWizard() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Antigüedad de Stock"),
            res_model: "gn.stock.age.wizard",
            views: [[false, "form"]],
            target: "new",
        });
    }
}

registry.category("actions").add("gn_stock_age_preview", GnStockAgePreview);
