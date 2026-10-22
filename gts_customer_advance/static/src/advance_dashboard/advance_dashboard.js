/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { FilterPanel } from "./filter_panel";
import { KpiCard } from "./kpi_card";
import { DataTable } from "./data_table";

export class GtsAdvanceDashboard extends Component {
    static template = "gts_customer_advance.AdvanceDashboard";
    static components = { Layout, FilterPanel, KpiCard, DataTable };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            sidebarVisible: true,
            filterOptions: { creators: [] },
            filters: {
                period: "this_month",
                date_from: "",
                date_to: "",
                creator_id: false,
            },
            data: {},
        });

        onWillStart(async () => {
            this.state.filterOptions = await this.orm.call(
                "gts.advance.dashboard", "get_filter_options", []
            );
            await this.loadData();
        });
    }

    get display() {
        return { controlPanel: {} };
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "gts.advance.dashboard", "get_dashboard_data",
                [this.state.filters]
            );
        } catch (e) {
            console.error("Dashboard load error:", e);
        }
        this.state.loading = false;
    }

    async onFiltersChanged(filters) {
        Object.assign(this.state.filters, filters);
        await this.loadData();
    }

    async onDrilldown(rowKey) {
        const action = await this.orm.call(
            "gts.advance.dashboard", "get_drilldown_action",
            [this.state.filters, rowKey, false]
        );
        if (action && action.type) {
            if (!action.views) {
                action.views = [[false, "list"], [false, "form"]];
            }
            this.actionService.doAction(action);
        }
    }

    toggleSidebar() {
        this.state.sidebarVisible = !this.state.sidebarVisible;
    }

    _fmt(v) {
        if (v === undefined || v === null) return "0.00";
        return Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    get kpis() {
        const d = this.state.data;
        if (!d || !d.kpis) return [];
        const k = d.kpis;
        return [
            {
                label: "Total Abonos/Anticipos",
                value: String(k.total_advances || 0),
                icon: "fa-money",
                color: "",
            },
            {
                label: "Total Monto",
                value: "$" + this._fmt(k.total_amount),
                icon: "fa-dollar",
                color: "",
            },
            {
                label: "Con Cotizaciones Vinculadas",
                value: String(k.advances_with_links || 0),
                icon: "fa-link",
                color: "",
            },
        ];
    }
}

registry.category("actions").add("gts_advance_dashboard", GtsAdvanceDashboard);
