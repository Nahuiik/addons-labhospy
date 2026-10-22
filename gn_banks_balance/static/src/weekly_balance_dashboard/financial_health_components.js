/** @odoo-module **/

import { Component, useRef, onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import {
    CHART_COLORS,
    loadChartJs,
    destroyChart,
    baseChartOptions,
    formatChartMoney,
} from "./chart_utils";

export function statusClass(status) {
    const map = {
        healthy: "success",
        warning: "warning",
        risk: "danger",
        danger: "danger",
        success: "success",
        info: "info",
        positive: "success",
        negative: "danger",
        neutral: "secondary",
        unavailable: "muted",
        excellent: "success",
        good: "success",
        improving: "success",
        stable: "info",
        deteriorating: "danger",
        green: "success",
        yellow: "warning",
        red: "danger",
        low: "success",
        medium: "warning",
        high: "danger",
    };
    return map[status] || "info";
}

export function scoreBand(score) {
    if (score <= 40) return "danger";
    if (score <= 70) return "warning";
    return "success";
}

export class FinancialHealthUnavailable extends Component {
    static template = "gn_banks_balance.FinancialHealthUnavailable";
    static props = {
        message: { type: String, optional: true },
        compact: { type: Boolean, optional: true },
    };
}

export class LiquidityScoreGauge extends Component {
    static template = "gn_banks_balance.LiquidityScoreGauge";
    static props = {
        scoreData: { type: Object, optional: true },
    };

    get score() {
        return this.props.scoreData?.score ?? 0;
    }

    get bandClass() {
        return `gn-wb-fh-gauge-compact--${scoreBand(this.score)}`;
    }

    get strokeDash() {
        const pct = Math.max(0, Math.min(100, this.score));
        return `${(pct / 100) * 283} 283`;
    }

    get levelLabel() {
        return this.props.scoreData?.label || this.props.scoreData?.level || "";
    }
}

export class LiquidityScoreBreakdown extends Component {
    static template = "gn_banks_balance.LiquidityScoreBreakdown";
    static props = {
        scoreData: { type: Object, optional: true },
    };

    get components() {
        return this.props.scoreData?.components || [];
    }
}

export class LiquidityRiskCard extends Component {
    static template = "gn_banks_balance.LiquidityRiskCard";
    static props = {
        riskData: { type: Object, optional: true },
    };

    get levelClass() {
        return `gn-wb-fh-risk--${this.props.riskData?.level || "green"}`;
    }
}

export class FinancialHealthHeader extends Component {
    static template = "gn_banks_balance.FinancialHealthHeader";
    static components = { LiquidityScoreGauge, LiquidityRiskCard };
    static props = {
        summary: { type: Object, optional: true },
        scoreData: { type: Object, optional: true },
        riskData: { type: Object, optional: true },
    };

    get severityClass() {
        return statusClass(this.props.summary?.severity || "info");
    }
}

export class CashRunwayCard extends Component {
    static template = "gn_banks_balance.CashRunwayCard";
    static components = { FinancialHealthUnavailable };
    static props = {
        runwayData: { type: Object, optional: true },
    };

    get isEmpty() {
        return this.props.runwayData?.coverage_days === null &&
            this.props.runwayData?.empty_reason === "no_outflows";
    }
}

export class CashForecastPanel extends Component {
    static template = "gn_banks_balance.CashForecastPanel";
    static props = {
        forecastData: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.props.currencyId });
    }

    get trendClass() {
        return statusClass(this.props.forecastData?.trend);
    }

    get allNegative() {
        return this.props.forecastData?.all_negative_projection;
    }
}

export class ProjectedTrajectoryChart extends Component {
    static template = "gn_banks_balance.ProjectedTrajectoryChart";
    static components = { FinancialHealthUnavailable };
    static props = {
        forecastData: { type: Object, optional: true },
        currencySymbol: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
    }

    get hasData() {
        const f = this.props.forecastData || {};
        return (f.historical_series?.length || 0) + (f.projected_series?.length || 0) > 0;
    }

    async renderChart() {
        const canvas = this.canvasRef.el;
        const data = this.props.forecastData || {};
        const historical = data.historical_series || [];
        const projected = data.projected_series || [];
        if (!canvas || (!historical.length && !projected.length)) {
            this.chart = destroyChart(this.chart);
            return;
        }
        await loadChartJs();
        this.chart = destroyChart(this.chart);
        const symbol = this.props.currencySymbol || "$";
        const histLabels = historical.map((s) => s.label);
        const projLabels = projected.map((s) => s.label);
        const labels = [...histLabels, ...projLabels];
        const histValues = historical.map((s) => s.value);
        const projValues = projected.map((s) => s.value);
        const histData = [...histValues, ...Array(projValues.length).fill(null)];
        const projData = [...Array(histValues.length).fill(null), ...projValues];
        if (histValues.length && projValues.length) {
            histData[histValues.length - 1] = histValues[histValues.length - 1];
            projData[histValues.length - 1] = histValues[histValues.length - 1];
        }

        this.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: _t("Histórico"),
                        data: histData,
                        borderColor: CHART_COLORS.balanceBorder,
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        tension: 0.25,
                        pointRadius: 3,
                        spanGaps: false,
                    },
                    {
                        label: _t("Proyectado"),
                        data: projData,
                        borderColor: CHART_COLORS.netBorder,
                        backgroundColor: CHART_COLORS.balance,
                        borderWidth: 2,
                        borderDash: [6, 4],
                        fill: true,
                        tension: 0.25,
                        pointRadius: 4,
                        spanGaps: false,
                    },
                ],
            },
            options: {
                ...baseChartOptions(),
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) =>
                                `${ctx.dataset.label}: ${formatChartMoney(ctx.parsed.y, symbol)}`,
                        },
                    },
                },
            },
        });
    }
}

export class FinancialRatioTooltip extends Component {
    static template = "gn_banks_balance.FinancialRatioTooltip";
    static props = {
        ratioData: { type: Object, optional: true },
    };

    setup() {
        this.state = useState({ open: false });
    }

    toggleHelp(ev) {
        ev.stopPropagation();
        this.state.open = !this.state.open;
    }

    closeHelp() {
        this.state.open = false;
    }

    get helpLines() {
        const d = this.props.ratioData || {};
        const lines = [];
        if (d.formula) {
            lines.push({ label: _t("Fórmula"), text: d.formula });
        }
        if (d.message) {
            lines.push({ label: _t("Significado"), text: d.message });
        }
        if (d.healthy_range) {
            lines.push({ label: _t("Rango saludable"), text: d.healthy_range });
        }
        return lines;
    }
}

const GAUGE_SCALE_MAX = {
    current_ratio: 3.0,
    quick_ratio: 2.0,
    cash_flow_coverage: 1.5,
};

export class MiniFinancialGauge extends Component {
    static template = "gn_banks_balance.MiniFinancialGauge";
    static props = {
        value: { type: Number, optional: true },
        status: { type: String, optional: true },
        ratioId: { type: String, optional: true },
        thresholds: { type: Object, optional: true },
        available: { type: Boolean, optional: true },
    };

    get arcLength() {
        return Math.PI * 26;
    }

    get fillDash() {
        if (!this.props.available || this.props.value === null || this.props.value === undefined) {
            return `0 ${this.arcLength}`;
        }
        const warn = this.props.thresholds?.warning || 1;
        const scaleMax = Math.min(
            Math.max(GAUGE_SCALE_MAX[this.props.ratioId] || 2, warn * 1.5, this.props.value),
            (GAUGE_SCALE_MAX[this.props.ratioId] || 2) * 1.5
        );
        const pct = Math.min(1, Math.max(0, this.props.value / scaleMax));
        return `${(pct * this.arcLength).toFixed(2)} ${this.arcLength.toFixed(2)}`;
    }

    get toneClass() {
        return `gn-wb-fh-mini-gauge--${statusClass(this.props.status || "unavailable")}`;
    }
}

export class FinancialRatioCard extends Component {
    static template = "gn_banks_balance.FinancialRatioCard";
    static components = { MiniFinancialGauge, FinancialRatioTooltip };
    static props = {
        ratioData: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
        showGauge: { type: Boolean, optional: true },
    };

    get statusTone() {
        return statusClass(this.props.ratioData?.status);
    }

    get disabled() {
        return !this.props.ratioData?.available;
    }

    get withGauge() {
        return this.props.showGauge !== false && !this.props.ratioData?.value_is_money;
    }

    fmtValue() {
        const data = this.props.ratioData || {};
        if (!data.available) {
            return _t("N/D");
        }
        return data.value !== undefined && data.value !== null
            ? Number(data.value).toFixed(2)
            : _t("N/D");
    }
}

export class WorkingCapitalCard extends Component {
    static template = "gn_banks_balance.WorkingCapitalCard";
    static components = { FinancialRatioTooltip };
    static props = {
        ratioData: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    get statusTone() {
        return statusClass(this.props.ratioData?.status);
    }

    get disabled() {
        return !this.props.ratioData?.available;
    }

    get borderClass() {
        return `gn-wb-fh-wc-card--${this.statusTone}`;
    }

    fmt(amount) {
        if (amount === null || amount === undefined) {
            return _t("N/D");
        }
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }

    fmtValue() {
        const data = this.props.ratioData || {};
        if (!data.available) {
            return _t("N/D");
        }
        return this.fmt(data.value);
    }
}

export class FinancialRatiosGrid extends Component {
    static template = "gn_banks_balance.FinancialRatiosGrid";
    static components = {
        FinancialRatioCard,
        WorkingCapitalCard,
        FinancialHealthUnavailable,
    };
    static props = {
        ratios: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    get gaugeRatios() {
        const r = this.props.ratios || {};
        return [r.current_ratio, r.quick_ratio, r.cash_flow_coverage].filter(Boolean);
    }

    get workingCapital() {
        return this.props.ratios?.working_capital;
    }

    get allUnavailable() {
        const items = [...this.gaugeRatios, this.workingCapital].filter(Boolean);
        return items.length > 0 && items.every((i) => !i.available);
    }

    get gaugeRow1() {
        return this.gaugeRatios.slice(0, 2);
    }

    get cashFlowRatio() {
        return this.gaugeRatios[2] || null;
    }
}

export class LiquidityTrendCard extends Component {
    static template = "gn_banks_balance.LiquidityTrendCard";
    static components = { FinancialHealthUnavailable };
    static props = {
        trendData: { type: Object, optional: true },
    };

    setup() {
        this.canvasRef = useRef("spark");
        this.chart = null;
        onMounted(() => this.renderSpark());
        onPatched(() => this.renderSpark());
        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
    }

    get statusTone() {
        return statusClass(this.props.trendData?.status);
    }

    get isEmpty() {
        return !this.props.trendData?.available || !(this.props.trendData?.series?.length);
    }

    async renderSpark() {
        const canvas = this.canvasRef.el;
        const series = this.props.trendData?.series || [];
        if (!canvas || !series.length) {
            this.chart = destroyChart(this.chart);
            return;
        }
        await loadChartJs();
        this.chart = destroyChart(this.chart);
        this.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: series.map((s) => s.label),
                datasets: [{
                    data: series.map((s) => s.value),
                    borderColor: CHART_COLORS.balanceBorder,
                    borderWidth: 2,
                    pointRadius: 2,
                    tension: 0.35,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { display: false } },
            },
        });
    }
}

export class BankConcentrationPanel extends Component {
    static template = "gn_banks_balance.BankConcentrationPanel";
    static components = { FinancialHealthUnavailable };
    static props = {
        concentrationData: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
    }

    get riskTone() {
        return statusClass(this.props.concentrationData?.risk_level);
    }

    get isEmpty() {
        const d = this.props.concentrationData;
        return !d?.available || !(d?.balance_distribution?.length);
    }

    get tableRows() {
        const conc = this.props.concentrationData || {};
        const movMap = Object.fromEntries(
            (conc.movement_distribution || []).map((m) => [m.journal_id, m.percentage])
        );
        return (conc.balance_distribution || []).map((b) => ({
            ...b,
            movement_percentage: movMap[b.journal_id] || 0,
        }));
    }

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.props.currencyId });
    }

    async renderChart() {
        const canvas = this.canvasRef.el;
        const banks = this.props.concentrationData?.balance_distribution || [];
        if (!canvas || !banks.length) {
            this.chart = destroyChart(this.chart);
            return;
        }
        await loadChartJs();
        this.chart = destroyChart(this.chart);
        const palette = ["#0d6efd", "#198754", "#334155", "#ffc107", "#6c757d", "#dc3545"];
        this.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: banks.map((b) => b.bank_name),
                datasets: [{
                    label: _t("% saldo"),
                    data: banks.map((b) => b.percentage),
                    backgroundColor: banks.map((_, i) => palette[i % palette.length]),
                    borderWidth: 0,
                }],
            },
            options: {
                indexAxis: "y",
                ...baseChartOptions(),
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.x.toFixed(2)}%` } },
                },
                scales: {
                    x: { max: 100, ticks: { callback: (v) => `${v}%`, font: { size: 10 } } },
                    y: { ticks: { font: { size: 10 } } },
                },
            },
        });
    }
}

export class HistoricalComparisonPanel extends Component {
    static template = "gn_banks_balance.HistoricalComparisonPanel";
    static components = { FinancialHealthUnavailable };
    static props = {
        comparisonData: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
    };

    fmt(amount, key) {
        if (amount === null || amount === undefined) {
            return "—";
        }
        if (key === "coverage_days") {
            return Number(amount).toFixed(2);
        }
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }

    fmtPct(v) {
        if (v === null || v === undefined) return "—";
        const sign = v >= 0 ? "+" : "";
        return `${sign}${Number(v).toFixed(2)}%`;
    }

    get rows() {
        const cmp = this.props.comparisonData?.comparisons || {};
        const labels = {
            final_balance: _t("Saldo final"),
            net_flow: _t("Flujo neto"),
            total_inflows: _t("Ingresos"),
            total_outflows: _t("Salidas"),
            coverage_days: _t("Días cobertura"),
        };
        return Object.entries(labels).map(([key, label]) => ({
            key,
            label,
            data: cmp[key],
        }));
    }
}

export class SmartAlertsPanel extends Component {
    static template = "gn_banks_balance.SmartAlertsPanel";
    static props = {
        alerts: { type: Array, optional: true },
        currencyId: { type: Number, optional: true },
    };

    fmt(value) {
        if (value === null || value === undefined) return "";
        return formatMonetary(value, { currencyId: this.props.currencyId });
    }
}

export class RecommendationsPanel extends Component {
    static template = "gn_banks_balance.RecommendationsPanel";
    static props = {
        recommendations: { type: Array, optional: true },
    };
}

export class FinancialTimeline extends Component {
    static template = "gn_banks_balance.FinancialTimeline";
    static components = { FinancialHealthUnavailable };
    static props = {
        events: { type: Array, optional: true },
        currencyId: { type: Number, optional: true },
    };

    iconFor(type) {
        const map = {
            inflow: "fa-arrow-down",
            outflow: "fa-arrow-up",
            risk: "fa-exclamation-circle",
            concentration: "fa-university",
            forecast: "fa-line-chart",
            ratio: "fa-balance-scale",
            info: "fa-info-circle",
        };
        return map[type] || "fa-circle";
    }

    fmt(amount) {
        if (amount === null || amount === undefined) return "";
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }
}

export class FinancialHealthSkeleton extends Component {
    static template = "gn_banks_balance.FinancialHealthSkeleton";
}

export class FinancialHealthEmptyState extends Component {
    static template = "gn_banks_balance.FinancialHealthEmptyState";
    static props = { message: { type: String, optional: true } };
}

export class FinancialHealthErrorState extends Component {
    static template = "gn_banks_balance.FinancialHealthErrorState";
    static props = { message: String, onRetry: Function };
}

// Legacy alias
export class CashForecastChart extends ProjectedTrajectoryChart {}
