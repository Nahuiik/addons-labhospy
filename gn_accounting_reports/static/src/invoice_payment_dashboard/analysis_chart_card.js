/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { loadEcharts, disposeEchart, buildBarOption, buildPieOption, exportChartImage } from "./echarts_utils";
import { formatMoney, formatPct } from "./format_utils";

const ADVISOR_METRICS = [
    { id: "invoiced", label: _t("Facturado") },
    { id: "paid", label: _t("Pagado") },
    { id: "pending", label: _t("Saldo pendiente") },
    { id: "invoice_count", label: _t("Número de facturas") },
    { id: "recovery_pct", label: _t("Recuperación %") },
];

const CLIENT_METRICS = [
    { id: "paid", label: _t("Pagado") },
    { id: "invoiced", label: _t("Facturado") },
    { id: "pending", label: _t("Saldo pendiente") },
    { id: "avg_collection_days", label: _t("Días promedio de cobro") },
];

const CLIENT_TOP_OPTIONS = [5, 10, 20];

export class InvPayAnalysisChartCard extends Component {
    static template = "gn_accounting_reports.InvPayAnalysisChartCard";
    static props = {
        chartId: String,
        chartKey: String,
        chartType: { type: String, optional: true }, // advisor, client, distribution
        config: Object,
        currencySymbol: String,
        currencyId: Number,
        loading: { type: Boolean, optional: true },
        error: { type: String, optional: true },
        onChartClick: Function,
        onApplyFilter: Function,
        onViewDetail: Function,
        onRetry: { type: Function, optional: true },
        onExportData: { type: Function, optional: true },
    };

    setup() {
        this.chartRef = useRef("chart");
        this._chart = null;
        this.state = useState({
            metric: this.props.chartType === "client" ? "paid" : "paid",
            topN: 10,
            viewMode: "chart",
            distributionType: "donut",
        });
        onMounted(() => this._render());
        onPatched(() => this._render());
        onWillUnmount(() => {
            this._chart = disposeEchart(this._chart);
        });
    }

    get defaultMetric() {
        if (this.props.chartType === "client") return "paid";
        if (this.props.chartType === "advisor") return "paid";
        return "paid";
    }

    get metrics() {
        if (this.props.chartType === "client") return CLIENT_METRICS;
        if (this.props.chartType === "advisor") return ADVISOR_METRICS;
        return [];
    }

    get topOptions() {
        return this.props.chartType === "client" ? CLIENT_TOP_OPTIONS : [10];
    }

    get title() {
        const cfg = this.props.config || {};
        const metric = this.metrics.find((m) => m.id === this.state.metric);
        const mlabel = metric?.label || "";
        if (this.props.chartType === "advisor") {
            return _t("Top asesores por %(metric)s", { metric: mlabel.toLowerCase() });
        }
        if (this.props.chartType === "client") {
            return _t("Top %(n)s clientes por %(metric)s", { n: this.state.topN, metric: mlabel.toLowerCase() });
        }
        const names = {
            bank_distribution: _t("Distribución por banco — pagos"),
            category_distribution: _t("Distribución por categoría — facturado"),
        };
        return names[this.props.chartKey] || _t("Distribución");
    }

    get isEmpty() {
        const cfg = this.props.config || {};
        return !(cfg.labels?.length);
    }

    get slicedConfig() {
        const cfg = { ...(this.props.config || {}) };
        const n = this.state.topN;
        if (this.props.chartType === "client" && cfg.labels?.length > n) {
            const slice = (arr) => (arr || []).slice(0, n);
            cfg.labels = slice(cfg.labels);
            if (cfg.full_labels) cfg.full_labels = slice(cfg.full_labels);
            if (cfg.metrics) {
                cfg.metrics = Object.fromEntries(
                    Object.entries(cfg.metrics).map(([k, v]) => [k, slice(v)])
                );
            }
            cfg.meta = slice(cfg.meta);
            cfg.drilldown = slice(cfg.drilldown);
        }
        return cfg;
    }

    get chartData() {
        const cfg = this.slicedConfig;
        if (this.props.chartType === "distribution") {
            return {
                labels: cfg.labels || [],
                data: cfg.data || [],
                percentages: cfg.percentages || [],
                drilldown: cfg.drilldown || [],
            };
        }
        const metrics = cfg.metrics || cfg;
        const data = metrics[this.state.metric] || cfg[this.state.metric] || cfg.paid || [];
        return {
            labels: cfg.labels || [],
            fullLabels: cfg.full_labels || cfg.labels || [],
            data,
            meta: cfg.meta || [],
            drilldown: cfg.drilldown || [],
            isPct: this.state.metric === "recovery_pct",
            isDays: this.state.metric === "avg_collection_days",
        };
    }

    get tableRows() {
        const { labels, data, fullLabels, meta, isPct, isDays } = this.chartData;
        const sym = this.props.currencySymbol;
        return labels.map((label, i) => ({
            label,
            fullLabel: fullLabels[i] || label,
            value: data[i],
            display: isPct ? formatPct(data[i]) : isDays ? `${Number(data[i]).toFixed(1)} d` : formatMoney(data[i], this.props.currencyId),
            meta: meta[i] || {},
            index: i,
        }));
    }

    setMetric(metric) {
        this.state.metric = metric;
    }

    setTopN(n) {
        this.state.topN = n;
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    setDistributionType(type) {
        this.state.distributionType = type;
        this.state.viewMode = type === "table" ? "table" : "chart";
    }

    onBarClick(index) {
        const drill = this.chartData.drilldown[index];
        if (drill?.filter) {
            this.props.onApplyFilter(drill);
        }
    }

    onAction(action) {
        if (action === "detail") {
            this.props.onViewDetail(this.props.chartKey);
        } else if (action === "filter") {
            const drill = this.chartData.drilldown[0];
            if (drill) this.props.onApplyFilter(drill);
        } else if (action === "image") {
            exportChartImage(this._chart, `${this.props.chartId}.png`);
        } else if (action === "data" && this.props.onExportData) {
            this.props.onExportData(this.props.chartKey, this.chartData);
        }
    }

    async _render() {
        const el = this.chartRef.el;
        if (!el || this.state.viewMode === "table" || this.isEmpty || this.props.loading) {
            this._chart = disposeEchart(this._chart);
            return;
        }
        const echarts = await loadEcharts();
        this._chart = disposeEchart(this._chart);
        this._chart = echarts.init(el);
        const cd = this.chartData;
        const sym = this.props.currencySymbol || "";
        let option = {};
        if (this.props.chartType === "distribution") {
            if (this.state.distributionType === "bar") {
                option = buildBarOption(cd.labels, cd.data, true, {
                    currencySymbol: sym,
                    leftMargin: 140,
                    showEndLabels: true,
                });
            } else {
                option = buildPieOption(cd.labels, cd.data, {
                    currencySymbol: sym,
                    percentages: cd.percentages,
                });
            }
        } else {
            option = buildBarOption(cd.labels, cd.data, true, {
                currencySymbol: sym,
                fullLabels: cd.fullLabels,
                isPct: cd.isPct,
                isDays: cd.isDays,
                leftMargin: this.props.chartType === "advisor" ? 200 : 220,
                showEndLabels: this.props.chartType === "client",
            });
        }
        this._chart.setOption(option, true);
        this._chart.off("click");
        this._chart.on("click", (params) => {
            this.onBarClick(params.dataIndex);
        });
        this._chart.getZr().on("mousemove", (params) => {
            el.style.cursor = params.target ? "pointer" : "default";
        });
    }
}
