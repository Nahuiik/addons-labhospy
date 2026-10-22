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

export class BalanceEvolutionChart extends Component {
    static template = "gn_banks_balance.BalanceEvolutionChart";
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
        const closing = data.closing || [];
        const hasMovement = closing.some((v, i) => {
            const open = data.opening?.[i] ?? v;
            return Math.abs(v - open) > 0.009 || Math.abs(data.diff_previous?.[i] ?? 0) > 0.009;
        });
        if (data.labels.length < 2 && !hasMovement) {
            return { kind: "no_activity" };
        }
        if (!hasMovement && closing.every((v) => v === closing[0])) {
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
            opening: data.opening,
            closing: data.closing,
            average: data.average,
            week_keys: data.week_keys,
        });
    }

    _averageBand(data) {
        const upper = [];
        const lower = [];
        (data.average || []).forEach((avg, i) => {
            const open = data.opening?.[i] ?? avg;
            const close = data.closing?.[i] ?? avg;
            const spread = Math.max(Math.abs(close - open) / 2, Math.abs(avg) * 0.015, 1);
            upper.push(avg + spread);
            lower.push(avg - spread);
        });
        return { upper, lower };
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
        const weekKeys = data.week_keys || [];
        const ranges = data.date_ranges || [];
        const minIdx = weekKeys.indexOf(data.min_week_key);
        const maxIdx = weekKeys.indexOf(data.max_week_key);
        const band = this._averageBand(data);

        const pointRadius = data.closing.map((_, i) =>
            i === minIdx || i === maxIdx ? 7 : 4
        );
        const pointStyle = data.closing.map((_, i) =>
            i === minIdx ? "triangle" : i === maxIdx ? "rectRot" : "circle"
        );

        if (this.chart) {
            this.chart.data.labels = data.labels;
            this.chart.data.datasets[0].data = band.upper;
            this.chart.data.datasets[1].data = band.lower;
            this.chart.data.datasets[2].data = data.opening;
            this.chart.data.datasets[3].data = data.closing;
            this.chart.data.datasets[3].pointRadius = pointRadius;
            this.chart.data.datasets[3].pointStyle = pointStyle;
            this.chart.data.datasets[4].data = data.average;
            this.chart.update("none");
            attachWeekHover(this.chart, weekKeys, this.props.weekSync);
            return;
        }

        this.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: _t("Banda promedio (sup.)"),
                        data: band.upper,
                        borderColor: "transparent",
                        backgroundColor: "rgba(111, 66, 193, 0.08)",
                        pointRadius: 0,
                        fill: "+1",
                        tension: 0.35,
                    },
                    {
                        label: _t("Banda promedio (inf.)"),
                        data: band.lower,
                        borderColor: "transparent",
                        backgroundColor: "transparent",
                        pointRadius: 0,
                        fill: false,
                        tension: 0.35,
                    },
                    {
                        label: _t("Saldo inicial"),
                        data: data.opening,
                        borderColor: CHART_COLORS.balanceLine,
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        tension: 0.35,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: _t("Saldo final"),
                        data: data.closing,
                        borderColor: CHART_COLORS.closingLine,
                        backgroundColor: CHART_COLORS.balance,
                        borderWidth: 2.5,
                        tension: 0.35,
                        fill: true,
                        pointRadius,
                        pointStyle,
                        pointHoverRadius: 8,
                    },
                    {
                        label: _t("Saldo promedio"),
                        data: data.average,
                        borderColor: CHART_COLORS.averageLine,
                        borderDash: [6, 4],
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                        tension: 0.35,
                    },
                ],
            },
            options: {
                ...baseChartOptions(),
                animation: { duration: 450, easing: "easeOutQuart" },
                scales: {
                    x: axisShortLabels(0),
                    y: { beginAtZero: false },
                },
                plugins: {
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
                            beforeBody: (items) => {
                                const idx = items[0]?.dataIndex;
                                const open = data.opening?.[idx];
                                const close = data.closing?.[idx];
                                const variation = close !== undefined && open !== undefined ? close - open : null;
                                const lines = [];
                                if (open !== undefined) {
                                    lines.push(`${_t("Saldo inicial")}: ${formatChartMoney(open, symbol)}`);
                                }
                                if (close !== undefined) {
                                    lines.push(`${_t("Saldo final")}: ${formatChartMoney(close, symbol)}`);
                                }
                                if (variation !== null) {
                                    const sign = variation >= 0 ? "+" : "";
                                    lines.push(`${_t("Variación")}: ${sign}${formatChartMoney(variation, symbol)}`);
                                }
                                return lines;
                            },
                            label: () => "",
                            footer: (items) => {
                                const idx = items[0]?.dataIndex;
                                const diff = data.diff_previous?.[idx];
                                if (diff === undefined) {
                                    return "";
                                }
                                const sign = diff >= 0 ? "+" : "";
                                return `${_t("vs semana anterior")}: ${sign}${formatChartMoney(diff, symbol)}`;
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
