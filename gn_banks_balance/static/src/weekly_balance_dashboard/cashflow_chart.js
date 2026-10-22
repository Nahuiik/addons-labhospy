/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { DashboardStatePanel } from "./dashboard_state";
import {
    CHART_COLORS,
    loadChartJs,
    destroyChart,
    baseChartOptions,
    formatChartMoney,
    attachWeekHover,
    weekHighlightPlugin,
    axisShortLabels,
    useWeeklyChart,
} from "./chart_utils";

export class CashflowChart extends Component {
    static template = "gn_banks_balance.CashflowChart";
    static components = { DashboardStatePanel };
    static props = {
        chartData: Object,
        weekSync: { type: Object, optional: true },
        highlightedWeekKey: { type: String, optional: true },
        currencySymbol: { type: String, optional: true },
    };

    setup() {
        useWeeklyChart(this, { fingerprint: () => this._chartFingerprint() });
    }

    get chartState() {
        const data = this.props.chartData;
        if (!data?.labels?.length) {
            return { kind: "empty" };
        }
        const inflows = data.inflows || [];
        const outflows = data.outflows || [];
        const hasActivity = inflows.some((v) => Math.abs(v) > 0.009) || outflows.some((v) => Math.abs(v) > 0.009);
        if (!hasActivity) {
            return { kind: "no_activity" };
        }
        return { kind: "ready" };
    }

    _chartFingerprint() {
        const data = this.props.chartData;
        if (!data?.labels?.length) {
            return "empty";
        }
        return JSON.stringify({
            labels: data.labels,
            inflows: data.inflows,
            outflows: data.outflows,
            net: data.net,
            week_keys: data.week_keys,
        });
    }

    async renderChart() {
        const canvas = this.canvasRef.el;
        const data = this.props.chartData;
        if (!canvas || this.chartState.kind !== "ready") {
            this.chart = destroyChart(this.chart);
            return;
        }
        await loadChartJs();
        if (typeof Chart === "undefined") {
            return;
        }

        this.highlightRef.key =
            this.props.weekSync?.weekKey || this.props.highlightedWeekKey || null;

        const symbol = this.props.currencySymbol || "$";
        const ranges = data.date_ranges || [];
        const weekKeys = data.week_keys || [];
        const netColors = (data.net || []).map((v) =>
            v < 0 ? CHART_COLORS.netNegative : CHART_COLORS.netBorder
        );
        const inflowColors = (data.net || []).map((v, i) =>
            data.negative_weeks?.includes(weekKeys[i]) ? CHART_COLORS.inflowMuted : CHART_COLORS.inflow
        );
        const outflowColors = (data.net || []).map((v, i) =>
            data.negative_weeks?.includes(weekKeys[i]) ? CHART_COLORS.outflowMuted : CHART_COLORS.outflow
        );

        if (this.chart) {
            this.chart.data.labels = data.labels;
            this.chart.data.datasets[0].data = data.inflows;
            this.chart.data.datasets[0].backgroundColor = inflowColors;
            this.chart.data.datasets[1].data = data.outflows;
            this.chart.data.datasets[1].backgroundColor = outflowColors;
            this.chart.data.datasets[2].data = data.net;
            this.chart.data.datasets[2].pointBackgroundColor = netColors;
            this.chart.update("none");
            attachWeekHover(this.chart, weekKeys, this.props.weekSync);
            return;
        }

        this.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: _t("Ingresos"),
                        data: data.inflows,
                        backgroundColor: inflowColors,
                        borderColor: CHART_COLORS.inflowBorder,
                        borderWidth: 1,
                        order: 2,
                    },
                    {
                        label: _t("Salidas"),
                        data: data.outflows,
                        backgroundColor: outflowColors,
                        borderColor: CHART_COLORS.outflowBorder,
                        borderWidth: 1,
                        order: 3,
                    },
                    {
                        label: _t("Flujo neto"),
                        data: data.net,
                        type: "line",
                        borderColor: CHART_COLORS.netBorder,
                        backgroundColor: "transparent",
                        borderWidth: 3,
                        pointBackgroundColor: netColors,
                        pointRadius: 4,
                        tension: 0.25,
                        order: 1,
                    },
                ],
            },
            options: {
                ...baseChartOptions(),
                animation: { duration: 450, easing: "easeOutQuart" },
                scales: {
                    x: axisShortLabels(0),
                    y: { beginAtZero: true },
                },
                plugins: {
                    legend: { position: "top" },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const idx = items[0]?.dataIndex;
                                return data.labels[idx] || "";
                            },
                            afterTitle: (items) => {
                                const idx = items[0]?.dataIndex;
                                const r = ranges[idx];
                                return r ? `${r.from} — ${r.to}` : "";
                            },
                            footer: (items) => {
                                const idx = items[0]?.dataIndex;
                                const closing = data.closing?.[idx];
                                if (closing === undefined) {
                                    return "";
                                }
                                return `${_t("Saldo final")}: ${formatChartMoney(closing, symbol)}`;
                            },
                            label: (ctx) => {
                                const val = ctx.parsed.y ?? 0;
                                return `${ctx.dataset.label}: ${formatChartMoney(val, symbol)}`;
                            },
                        },
                    },
                },
            },
            plugins: [weekHighlightPlugin(this.highlightRef, weekKeys)],
        });
        attachWeekHover(this.chart, weekKeys, this.props.weekSync);
    }
}
