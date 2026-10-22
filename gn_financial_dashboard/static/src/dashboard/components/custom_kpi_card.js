/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Tarjeta para KPIs personalizados (V20 Fase 2, #1).
 *
 * Muestra valor formateado, comparativo (cuando hay periodo previo),
 * estado vs. umbral/meta y soporta drill-down hacia las cuentas que
 * componen el KPI (cuando aplica).
 */
export class CustomKpiCard extends Component {
    static template = "gn_financial_dashboard.CustomKpiCard";
    static props = {
        kpi: Object,
        onClick: { type: Function, optional: true },
    };

    get tone() {
        const k = this.props.kpi;
        if (k.error) return "muted";
        const val = Number(k.value || 0);
        const target = Number(k.target_value || 0);
        const trend = k.trend_mode || "higher_better";
        if (target) {
            const reached = trend === "higher_better" ? val >= target : val <= target;
            if (reached) return "ok";
        }
        const warn = Number(k.warning_threshold || 0);
        if (warn) {
            const breach = trend === "higher_better" ? val < warn : val > warn;
            if (breach) return "warn";
        }
        if (trend === "neutral") return "muted";
        return "info";
    }

    get deltaInfo() {
        const k = this.props.kpi;
        if (k.error || k.prev_value === null || k.prev_value === undefined) {
            return null;
        }
        const cur = Number(k.value || 0);
        const prev = Number(k.prev_value || 0);
        const diff = cur - prev;
        if (Math.abs(diff) < 0.01) return null;
        const pct = prev ? ((diff / Math.abs(prev)) * 100) : 0;
        const direction = diff > 0 ? "up" : "down";
        // "trend" visual: bueno/malo según la dirección deseada del KPI.
        const desired = k.trend_mode || "higher_better";
        let visual = "neutral";
        if (desired === "higher_better") visual = diff > 0 ? "good" : "bad";
        else if (desired === "lower_better") visual = diff < 0 ? "good" : "bad";
        return {
            label: (pct >= 0 ? "+" : "") + pct.toFixed(1) + "%",
            direction,
            visual,
        };
    }

    onCardClick() {
        if (this.props.onClick) this.props.onClick(this.props.kpi);
    }
}
