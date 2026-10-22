/** @odoo-module **/
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

export class GnStockDashboard extends Component {
    static template = "gn_stock_kardex.StockDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.chartRef = useRef("stockChart");
        this.pieRef = useRef("locChart");
        this.rotationChartRef = useRef("rotationChart");
        this.overstockChartRef = useRef("overstockChart");
        this.turnoverBarRef = useRef("turnoverBarChart");
        this.turnoverLineRef = useRef("turnoverLineChart");
        this._charts = [];

        this.state = useState({
            loading: true,
            data: null,
            productSearch: "",
            selectedProductId: false,
            dropdownOpen: false,
            searchResults: [],
            activeTab: "general",
            rotationFilter: null,
        });

        onMounted(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this._loadData();
        });

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    _destroyCharts() {
        for (const c of this._charts) {
            try { c.destroy(); } catch (_e) { /* noop */ }
        }
        this._charts = [];
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("gn.stock.dashboard", "get_dashboard_data", [], {
                product_id: this.state.selectedProductId || false,
            });
            this.state.data = data;
            this.state.loading = false;
            await new Promise((r) => setTimeout(r, 50));
            this._renderChartsForTab();
        } catch (e) {
            console.error(e);
            this.state.loading = false;
        }
    }

    // ── Tab management ──

    async onTabChange(tab) {
        this.state.activeTab = tab;
        this.state.rotationFilter = null;
        await new Promise((r) => setTimeout(r, 50));
        this._renderChartsForTab();
    }

    _renderChartsForTab() {
        this._destroyCharts();
        const tab = this.state.selectedProductId ? "general" : this.state.activeTab;
        switch (tab) {
            case "general":
                this._renderLineChart();
                this._renderPieChart();
                break;
            case "rotation":
                this._renderRotationChart();
                break;
            case "overstock":
                this._renderOverstockChart();
                break;
            case "turnover":
                this._renderTurnoverBarChart();
                this._renderTurnoverLineChart();
                break;
        }
    }

    // ── General tab charts ──

    _renderLineChart() {
        const el = this.chartRef.el;
        if (!el || !this.state.data?.stock_history?.length) return;
        const ctx = el.getContext("2d");
        const hist = this.state.data.stock_history;
        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: hist.map((h) => h.month),
                datasets: [
                    {
                        label: "Entradas",
                        data: hist.map((h) => h.qty_in),
                        borderColor: "#4caf50",
                        backgroundColor: "rgba(76,175,80,0.1)",
                        tension: 0.3,
                        fill: true,
                    },
                    {
                        label: "Salidas",
                        data: hist.map((h) => h.qty_out),
                        borderColor: "#e53935",
                        backgroundColor: "rgba(229,57,53,0.1)",
                        tension: 0.3,
                        fill: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "top" } },
                scales: {
                    y: { beginAtZero: true, ticks: { font: { size: 10 } } },
                    x: { ticks: { font: { size: 10 } } },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderPieChart() {
        const el = this.pieRef.el;
        if (!el || !this.state.data?.locations?.length) return;
        const ctx = el.getContext("2d");
        const locs = this.state.data.locations;
        const colors = ["#5b2c6f", "#2196f3", "#4caf50", "#ff9800", "#e53935", "#795548", "#607d8b", "#9c27b0"];
        const chart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: locs.map((l) => l.name),
                datasets: [{
                    data: locs.map((l) => l.qty),
                    backgroundColor: colors.slice(0, locs.length),
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12 } },
                },
            },
        });
        this._charts.push(chart);
    }

    // ── Rotation chart ──

    _renderRotationChart() {
        const el = this.rotationChartRef.el;
        const rot = this.state.data?.stock_rotation;
        if (!el || !rot?.summary?.length) return;
        const ctx = el.getContext("2d");
        const colorMap = {
            fast: "#4caf50",
            medium: "#ff9800",
            slow: "#e53935",
            none: "#9e9e9e",
        };
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: rot.summary.map((s) => s.label),
                datasets: [{
                    label: "Productos",
                    data: rot.summary.map((s) => s.count),
                    backgroundColor: rot.summary.map((s) => colorMap[s.key] || "#607d8b"),
                    borderRadius: 6,
                    barThickness: 40,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => {
                                const s = rot.summary[ctx.dataIndex];
                                return `Valor: ${this.state.data.currency_symbol} ${this.fmt(s.value)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } },
                    y: { ticks: { font: { size: 11 } } },
                },
            },
        });
        this._charts.push(chart);
    }

    // ── Overstock chart ──

    _renderOverstockChart() {
        const el = this.overstockChartRef.el;
        const ov = this.state.data?.overstock;
        if (!el || !ov?.products?.length) return;
        const ctx = el.getContext("2d");
        const top10 = ov.products.slice(0, 10);
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: top10.map((p) => this._truncate(p.name, 20)),
                datasets: [{
                    label: "Valor Exceso",
                    data: top10.map((p) => p.excess_value),
                    backgroundColor: "#e53935",
                    borderRadius: 6,
                    barThickness: 28,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                return `${this.state.data.currency_symbol} ${this.fmt(ctx.raw)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { beginAtZero: true, ticks: { font: { size: 10 } } },
                    y: { ticks: { font: { size: 10 } } },
                },
            },
        });
        this._charts.push(chart);
    }

    // ── Turnover charts ──

    _renderTurnoverBarChart() {
        const el = this.turnoverBarRef.el;
        const tv = this.state.data?.turnover;
        if (!el || !tv?.categories?.length) return;
        const ctx = el.getContext("2d");
        const cats = tv.categories.slice(0, 12);
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: cats.map((c) => this._truncate(c.name, 18)),
                datasets: [{
                    label: "Ratio de Rotación",
                    data: cats.map((c) => c.ratio),
                    backgroundColor: "#5b2c6f",
                    borderRadius: 6,
                    barThickness: 28,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => {
                                const c = cats[ctx.dataIndex];
                                return `DSI: ${this.fmt(c.dsi)} días`;
                            }
                        }
                    }
                },
                scales: {
                    x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
                    y: { beginAtZero: true, title: { display: true, text: "Ratio" } },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderTurnoverLineChart() {
        const el = this.turnoverLineRef.el;
        const tv = this.state.data?.turnover;
        if (!el || !tv?.monthly?.length) return;
        const ctx = el.getContext("2d");
        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: tv.monthly.map((m) => m.month),
                datasets: [
                    {
                        label: "Costo de Ventas",
                        data: tv.monthly.map((m) => m.cogs),
                        borderColor: "#e53935",
                        backgroundColor: "rgba(229,57,53,0.1)",
                        tension: 0.3,
                        fill: true,
                        yAxisID: "y",
                    },
                    {
                        label: "Ratio Anualizado",
                        data: tv.monthly.map((m) => m.ratio),
                        borderColor: "#5b2c6f",
                        borderDash: [5, 3],
                        tension: 0.3,
                        yAxisID: "y1",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "top" } },
                scales: {
                    y: {
                        beginAtZero: true,
                        position: "left",
                        title: { display: true, text: "Costo" },
                        ticks: { font: { size: 10 } },
                    },
                    y1: {
                        beginAtZero: true,
                        position: "right",
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: "Ratio" },
                        ticks: { font: { size: 10 } },
                    },
                    x: { ticks: { font: { size: 10 } } },
                },
            },
        });
        this._charts.push(chart);
    }

    // ── Rotation helpers ──

    filterRotation(key) {
        this.state.rotationFilter = this.state.rotationFilter === key ? null : key;
    }

    getFilteredRotationProducts() {
        const prods = this.state.data?.stock_rotation?.products || [];
        if (!this.state.rotationFilter) return prods;
        return prods.filter((p) => p.classification === this.state.rotationFilter);
    }

    getRotationLabel(cls) {
        const map = { fast: "Rápido", medium: "Medio", slow: "Lento", none: "Sin mov." };
        return map[cls] || cls;
    }

    getNoMovementCount() {
        const rot = this.state.data?.stock_rotation;
        if (!rot?.summary) return 0;
        const item = rot.summary.find((s) => s.key === "none");
        return item ? item.count : 0;
    }

    // ── Product search ──

    async onProductSearch(ev) {
        const term = ev.target.value;
        this.state.productSearch = term;
        if (term.length < 2) {
            this.state.searchResults = [];
            this.state.dropdownOpen = false;
            return;
        }
        const results = await this.orm.searchRead(
            "product.product",
            [["is_storable", "=", true], "|", ["name", "ilike", term], ["default_code", "ilike", term]],
            ["id", "display_name"],
            { limit: 10 }
        );
        this.state.searchResults = results;
        this.state.dropdownOpen = true;
    }

    async selectProduct(p) {
        this.state.selectedProductId = p.id;
        this.state.productSearch = p.display_name;
        this.state.dropdownOpen = false;
        this.state.activeTab = "general";
        await this._loadData();
    }

    async clearProduct() {
        this.state.selectedProductId = false;
        this.state.productSearch = "";
        this.state.dropdownOpen = false;
        await this._loadData();
    }

    getMoveTypeClass(type) {
        if (type === "in") return "o_sd_badge_in";
        if (type === "out") return "o_sd_badge_out";
        return "o_sd_badge_int";
    }

    // ── Formatters ──

    fmt(n) {
        if (n === undefined || n === null) return "0.00";
        return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    fmtInt(n) {
        if (n === undefined || n === null) return "0";
        return Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    _truncate(str, len) {
        if (!str) return "";
        return str.length > len ? str.substring(0, len) + "…" : str;
    }
}

registry.category("actions").add("gn_stock_dashboard", GnStockDashboard);
