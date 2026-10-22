/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { BankKpiCard } from "./bank_kpi_card";
import { loadBundle } from "@web/core/assets";

export class BankDashboard extends Component {
    static template = "gn_banks_ui.BankDashboard";
    static components = { Layout, BankKpiCard };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.cashflowRef = useRef("cashflowChart");
        this.checksRef = useRef("checksChart");
        this.posRef = useRef("posChart");
        this.balancesRef = useRef("balancesChart");
        this.state = useState({
            loading: true,
            data: null,
            error: null,
        });
        this.charts = [];

        onWillStart(() => this.loadData());
        onMounted(() => this.renderCharts());
    }

    async loadData() {
        try {
            this.state.data = await this.orm.call(
                "banks.treasury.dashboard",
                "get_dashboard_data",
                []
            );
        } catch (e) {
            this.state.error = e.message || "Error al cargar el dashboard";
        } finally {
            this.state.loading = false;
        }
    }

    async renderCharts() {
        if (!this.state.data) {
            return;
        }
        await loadBundle("web.chartjs_lib");
        const Chart = window.Chart;
        if (!Chart) {
            return;
        }
        this.destroyCharts();
        const charts = this.state.data.charts || {};
        this._renderCashflow(Chart, charts.weekly_cashflow);
        this._renderChecks(Chart, charts.checks_by_state);
        this._renderPos(Chart, charts.pos_by_date);
        this._renderBalances(Chart, charts.bank_balances);
    }

    destroyCharts() {
        for (const c of this.charts) {
            c.destroy();
        }
        this.charts = [];
    }

    _renderCashflow(Chart, data) {
        const el = this.cashflowRef.el;
        if (!el || !data) return;
        this.charts.push(new Chart(el, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    { label: "Entradas", data: data.inflows, backgroundColor: "#27ae60" },
                    { label: "Salidas", data: data.outflows, backgroundColor: "#e74c3c" },
                ],
            },
            options: { responsive: true, maintainAspectRatio: false },
        }));
    }

    _renderChecks(Chart, data) {
        const el = this.checksRef.el;
        if (!el || !data) return;
        this.charts.push(new Chart(el, {
            type: "doughnut",
            data: {
                labels: data.labels,
                datasets: [{ data: data.values, backgroundColor: ["#3498db", "#27ae60", "#e74c3c", "#8e44ad"] }],
            },
            options: { responsive: true, maintainAspectRatio: false },
        }));
    }

    _renderPos(Chart, data) {
        const el = this.posRef.el;
        if (!el || !data) return;
        this.charts.push(new Chart(el, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [{ label: "POS", data: data.values, borderColor: "#9b59b6", fill: false }],
            },
            options: { responsive: true, maintainAspectRatio: false },
        }));
    }

    _renderBalances(Chart, data) {
        const el = this.balancesRef.el;
        if (!el || !data) return;
        this.charts.push(new Chart(el, {
            type: "bar",
            data: {
                labels: data.map((b) => b.name),
                datasets: [{ label: "Saldo", data: data.map((b) => b.balance), backgroundColor: "#714b67" }],
            },
            options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
        }));
    }

    formatKpiValue(kpi) {
        const val = kpi.value;
        if (typeof val === "number" && kpi.key !== "pending_transfers" && kpi.key !== "pending_checks" && kpi.key !== "pending_pos" && kpi.key !== "pending_reconciliation") {
            return val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
        return val;
    }

    async openWeeklyBalance() {
        const action = await this.orm.call("banks.treasury.dashboard", "get_weekly_balance_action", []);
        this.action.doAction(action);
    }

    async openReports() {
        const action = await this.orm.call("banks.treasury.dashboard", "get_reports_action", []);
        this.action.doAction(action);
    }

    async refresh() {
        this.state.loading = true;
        await this.loadData();
        this.state.loading = false;
        await this.renderCharts();
    }
}

registry.category("actions").add("gn_banks_treasury_dashboard", BankDashboard);
