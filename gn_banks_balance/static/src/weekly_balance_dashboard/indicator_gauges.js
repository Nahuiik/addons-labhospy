/** @odoo-module **/

import { Component, useRef, onWillStart, useEffect, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { loadChartJs, destroyChart } from "./chart_utils";
import { WbEmptyState, WbLoadingSkeleton } from "./empty_state";

const STATUS_COLORS = {
    healthy: "#16a34a",
    warning: "#f59e0b",
    risk: "#dc2626",
    unavailable: "#9ca3af",
};
const STATUS_LABELS = {
    healthy: () => _t("Saludable"),
    warning: () => _t("Atención"),
    risk: () => _t("Riesgo"),
    unavailable: () => _t("No disponible"),
};

const UNIT_AXIS = {
    score: { min: 0, max: 100, decimals: 0, suffix: "" },
    percent: { min: 0, max: 100, decimals: 1, suffix: " %" },
    ratio: { min: 0, max: 3, decimals: 2, suffix: "" },
    days: { min: 0, max: 90, decimals: 1, suffix: " d" },
};

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

/**
 * Doughnut-based gauge using Chart.js (same library as Odoo's web.GaugeField).
 * Reuses ``circumference: 180`` + ``rotation: 270`` + ``cutout: 70%`` for the
 * native semi-donut look, and colors the active arc according to ``status``.
 */
export class IndicatorGauge extends Component {
    static template = "gn_banks_balance.IndicatorGauge";
    static props = {
        gauge: { type: Object },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onWillStart(async () => {
            await loadChartJs();
        });

        useEffect(
            () => {
                this.renderChart();
            },
            () => [
                this.props.gauge.value,
                this.props.gauge.available,
                this.props.gauge.status,
                JSON.stringify(this.props.gauge.thresholds || {}),
            ]
        );

        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
    }

    get axis() {
        const unit = this.props.gauge.unit || "ratio";
        const base = UNIT_AXIS[unit] || UNIT_AXIS.ratio;
        const t = this.props.gauge.thresholds || {};
        const value = this.props.gauge.value;
        const candidates = [base.max, t.warning, t.risk]
            .filter((v) => Number.isFinite(v) && v > 0);
        const numericValue = Number.isFinite(value) ? Math.abs(value) : 0;
        const dynamicMax = Math.max(numericValue * 1.2, ...candidates, 1);
        return { ...base, max: dynamicMax };
    }

    get available() {
        return Boolean(this.props.gauge.available);
    }

    get statusColor() {
        return STATUS_COLORS[this.props.gauge.status] || STATUS_COLORS.unavailable;
    }

    get statusLabel() {
        if (this.props.gauge.status_label) {
            return this.props.gauge.status_label;
        }
        const fn = STATUS_LABELS[this.props.gauge.status];
        return fn ? fn() : "";
    }

    get formattedValue() {
        if (!this.available || !Number.isFinite(this.props.gauge.value)) {
            return "—";
        }
        const axis = this.axis;
        const value = this.props.gauge.value;
        return `${value.toFixed(axis.decimals)}${axis.suffix}`;
    }

    get rangeLabel() {
        return this.props.gauge.healthy_range || "";
    }

    get axisRangeLabel() {
        const axis = this.axis;
        return `${axis.min.toFixed(axis.decimals)} – ${axis.max.toFixed(axis.decimals)}`;
    }

    renderChart() {
        if (!this.canvasRef.el || typeof Chart === "undefined") {
            return;
        }
        this.chart = destroyChart(this.chart);

        const axis = this.axis;
        const span = axis.max - axis.min;
        const value = Number.isFinite(this.props.gauge.value)
            ? clamp(this.props.gauge.value, axis.min, axis.max)
            : axis.min;
        const filled = this.available ? value - axis.min : 0;
        const remaining = Math.max(span - filled, 0);
        const fillColor = this.available ? this.statusColor : "#e5e7eb";

        // Build a 3-color background hint behind the arc using thresholds.
        // We render two stacked datasets: outer thin band shows healthy/warn/risk
        // segments tinted, inner one shows the actual value.
        const t = this.props.gauge.thresholds || {};
        const unit = this.props.gauge.unit || "ratio";
        const lowerIsBetter = unit === "percent" || unit === "days";
        let bandColors;
        let bandValues;
        if (lowerIsBetter) {
            const w = Number.isFinite(t.warning) ? clamp(t.warning - axis.min, 0, span) : span / 3;
            const r = Number.isFinite(t.risk) ? clamp(t.risk - axis.min, 0, span) : (span * 2) / 3;
            bandValues = [w, Math.max(r - w, 0), Math.max(span - r, 0)];
            bandColors = [
                "rgba(22, 163, 74, 0.15)",
                "rgba(245, 158, 11, 0.18)",
                "rgba(220, 38, 38, 0.18)",
            ];
        } else {
            const r = Number.isFinite(t.risk) ? clamp(t.risk - axis.min, 0, span) : span / 3;
            const w = Number.isFinite(t.warning) ? clamp(t.warning - axis.min, 0, span) : (span * 2) / 3;
            bandValues = [r, Math.max(w - r, 0), Math.max(span - w, 0)];
            bandColors = [
                "rgba(220, 38, 38, 0.18)",
                "rgba(245, 158, 11, 0.18)",
                "rgba(22, 163, 74, 0.15)",
            ];
        }

        const config = {
            type: "doughnut",
            data: {
                datasets: [
                    {
                        data: bandValues,
                        backgroundColor: bandColors,
                        borderWidth: 0,
                        weight: 0.45,
                    },
                    {
                        data: [filled, remaining],
                        backgroundColor: [fillColor, "#e5e7eb"],
                        borderWidth: 0,
                        weight: 1,
                    },
                ],
            },
            options: {
                circumference: 180,
                rotation: 270,
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                aspectRatio: 2,
                layout: { padding: { top: 6, bottom: 0, left: 4, right: 4 } },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: this.available,
                        displayColors: false,
                        callbacks: {
                            label: () => this.formattedValue,
                        },
                    },
                },
            },
        };
        this.chart = new Chart(this.canvasRef.el, config);
    }
}

export class IndicatorGaugesPanel extends Component {
    static template = "gn_banks_balance.IndicatorGaugesPanel";
    static components = { IndicatorGauge, WbEmptyState, WbLoadingSkeleton };
    static props = {
        indicatorData: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
    };
    static defaultProps = {
        loading: false,
    };

    get groups() {
        const data = this.props.indicatorData || {};
        return data.groups || [];
    }

    get hasAny() {
        return this.groups.some((g) => (g.gauges || []).some((x) => x));
    }

    get emptyTitle() {
        return _t("Sin indicadores para mostrar");
    }

    get emptyDescription() {
        return _t(
            "Aún no hay datos suficientes para calcular los indicadores de salud financiera " +
            "del período. Asegúrate de que existan movimientos contabilizados en los diarios " +
            "bancarios seleccionados."
        );
    }

    get emptyHint() {
        return _t(
            "Sugerencia: amplía el rango (mes/año) o registra movimientos en los diarios " +
            "marcados como “incluir en dashboard”."
        );
    }
}
