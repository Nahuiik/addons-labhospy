/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { GnEmptyState, GnLoadingSkeleton } from "./empty_state";

const STATUS_COLORS = {
    healthy: "#059669",
    warning: "#d97706",
    risk: "#dc2626",
    unavailable: "#94a3b8",
};

const STATUS_LABELS = {
    healthy: () => _t("Saludable"),
    warning: () => _t("Atención"),
    risk: () => _t("Riesgo"),
    unavailable: () => _t("N/D"),
};

const UNIT_AXIS = {
    score: { min: 0, max: 100, decimals: 0, suffix: "" },
    percent: { min: 0, max: 100, decimals: 1, suffix: "%" },
    ratio: { min: 0, max: 3, decimals: 2, suffix: "" },
    days: { min: 0, max: 90, decimals: 1, suffix: " d" },
};

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

/**
 * Compact scorecard: title + badge + value + progress bar (~70% less height than gauges).
 */
export class TreasuryIndicatorScorecard extends Component {
    static template = "gn_banks_dashboard.IndicatorScorecard";
    static props = {
        gauge: { type: Object },
    };

    get axis() {
        const unit = this.props.gauge.unit || "ratio";
        const base = UNIT_AXIS[unit] || UNIT_AXIS.ratio;
        const t = this.props.gauge.thresholds || {};
        const value = this.props.gauge.value;
        const candidates = [base.max, t.warning, t.risk]
            .filter((v) => Number.isFinite(v) && v > 0);
        const numericValue = Number.isFinite(value) ? Math.abs(value) : 0;
        const dynamicMax = Math.max(numericValue * 1.15, ...candidates, 1);
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
        const suffix = axis.suffix ? (axis.suffix.startsWith(" ") ? axis.suffix : ` ${axis.suffix}`) : "";
        return `${value.toFixed(axis.decimals)}${suffix}`;
    }

    get fillPct() {
        if (!this.available || !Number.isFinite(this.props.gauge.value)) {
            return 0;
        }
        const axis = this.axis;
        const span = axis.max - axis.min || 1;
        const value = clamp(this.props.gauge.value, axis.min, axis.max);
        return Math.round(((value - axis.min) / span) * 100);
    }

    get rangeLabel() {
        const range = this.props.gauge.healthy_range;
        if (!range) {
            return "";
        }
        return _t("Rango saludable: %s", range);
    }

    get metaLabel() {
        const parts = [];
        if (this.rangeLabel) {
            parts.push(this.rangeLabel);
        }
        if (this.props.gauge.message) {
            parts.push(this.props.gauge.message);
        }
        return parts.join(" · ");
    }

    get tooltipText() {
        const g = this.props.gauge;
        const parts = [g.title];
        if (g.formula) {
            parts.push(g.formula);
        }
        if (g.message) {
            parts.push(g.message);
        }
        return parts.filter(Boolean).join(" — ");
    }
}

export class TreasuryIndicatorGaugesPanel extends Component {
    static template = "gn_banks_dashboard.IndicatorGaugesPanel";
    static components = { TreasuryIndicatorScorecard, GnEmptyState, GnLoadingSkeleton };
    static props = {
        indicatorData: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        onApplyDefaults: { type: Function, optional: true },
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

    get panelTitle() {
        return _t("Indicadores operativos");
    }

    get panelSubtitle() {
        return _t("Calidad de datos y riesgo del período");
    }

    get emptyTitle() {
        return _t("Sin operaciones en el período");
    }

    get emptyDescription() {
        return _t(
            "No hay movimientos validados con los filtros actuales. " +
            "Los indicadores aparecerán cuando exista actividad."
        );
    }

    get emptyHint() {
        return _t("Amplía fechas o restablece filtros de banco y sucursal.");
    }

    get emptyAction() {
        return _t("Restablecer filtros");
    }
}
