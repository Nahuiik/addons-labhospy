/** @odoo-module **/

import { Component, useRef, onWillUnmount, useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    CHART_COLORS,
    loadChartJs,
    destroyChart,
    baseChartOptions,
    formatChartMoney,
    waterfallConnectorPlugin,
    axisShortLabels,
} from "./chart_utils";

export class WaterfallCashflowChart extends Component {
    static template = "gn_banks_balance.WaterfallCashflowChart";
    static props = {
        chartData: Object,
        currencySymbol: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        // ``useEffect`` already fires after mount; calling ``renderChart``
        // from both ``onMounted`` and ``useEffect`` produced two concurrent
        // ``destroyChart`` + ``new Chart`` paths, which the user perceived
        // as flickering. Keeping a single entry point is enough.
        useEffect(
            () => {
                this.renderChart();
            },
            () => [JSON.stringify(this.props.chartData?.steps || [])],
        );
        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
    }

    _colorForType(type) {
        if (type === "inflow") {
            return CHART_COLORS.inflow;
        }
        if (type === "outflow") {
            return CHART_COLORS.outflow;
        }
        if (type === "subtotal") {
            return CHART_COLORS.subtotal;
        }
        if (type === "initial" || type === "final" || type === "total") {
            return CHART_COLORS.total;
        }
        return CHART_COLORS.totalMuted;
    }

    _movementLabel(type) {
        const map = {
            initial: _t("Saldo inicial"),
            final: _t("Saldo final"),
            inflow: _t("Ingresos"),
            outflow: _t("Salidas"),
            subtotal: _t("Saldo acumulado"),
        };
        return map[type] || type;
    }

    async renderChart() {
        const canvas = this.canvasRef.el;
        const steps = this.props.chartData?.steps || this.props.chartData || [];
        if (!canvas || !steps.length) {
            return;
        }
        await loadChartJs();
        if (typeof Chart === "undefined") {
            return;
        }
        this.chart = destroyChart(this.chart);
        const symbol = this.props.currencySymbol || "$";
        let running = 0;
        const labels = [];
        const bases = [];
        const values = [];
        const colors = [];
        const meta = [];
        for (const step of steps) {
            labels.push(step.short_label || step.label);
            colors.push(this._colorForType(step.type));
            const amount = Number(step.amount ?? step.value ?? 0);
            meta.push(step);
            if (
                step.type === "initial" ||
                step.type === "final" ||
                step.type === "total" ||
                step.type === "subtotal"
            ) {
                // Nivel de saldo: barra anclada en cero hacia arriba o hacia abajo según signo.
                if (amount >= 0) {
                    bases.push(0);
                    values.push(amount);
                } else {
                    bases.push(amount);
                    values.push(Math.abs(amount));
                }
                running = step.running_balance ?? amount;
            } else if (step.type === "inflow") {
                bases.push(running);
                values.push(Math.abs(amount));
                running = step.running_balance ?? running + amount;
            } else {
                bases.push(running + amount);
                values.push(Math.abs(amount));
                running = step.running_balance ?? running + amount;
            }
        }
        this.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "base",
                        data: bases,
                        backgroundColor: "transparent",
                        borderWidth: 0,
                        barPercentage: 0.65,
                    },
                    {
                        label: "value",
                        data: values,
                        backgroundColor: colors,
                        borderWidth: 1,
                        barPercentage: 0.65,
                    },
                ],
            },
            options: {
                ...baseChartOptions(),
                scales: {
                    x: { stacked: true, ...axisShortLabels(0) },
                    y: { stacked: true, beginAtZero: false },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const step = meta[items[0]?.dataIndex];
                                return step?.label || items[0]?.label || "";
                            },
                            afterTitle: (items) => {
                                const step = meta[items[0]?.dataIndex];
                                if (step?.date_from && step?.date_to) {
                                    return `${step.date_from} — ${step.date_to}`;
                                }
                                return "";
                            },
                            label: (ctx) => {
                                const step = meta[ctx.dataIndex];
                                const lines = [];
                                lines.push(
                                    `${this._movementLabel(step?.type)}: ${formatChartMoney(step?.amount ?? step?.value, symbol)}`
                                );
                                if (step?.running_balance !== undefined) {
                                    lines.push(
                                        `${_t("Saldo acumulado")}: ${formatChartMoney(step.running_balance, symbol)}`
                                    );
                                }
                                return lines;
                            },
                        },
                    },
                },
            },
            plugins: [waterfallConnectorPlugin],
        });
    }
}
