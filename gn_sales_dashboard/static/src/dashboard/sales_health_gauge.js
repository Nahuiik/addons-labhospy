/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { SalesEmptyState } from "./empty_state";

export class SalesHealthGauge extends Component {
    static template = "gn_sales_dashboard.SalesHealthGauge";
    static components = { SalesEmptyState };
    static props = {
        health: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        onFactorClick: { type: Function, optional: true },
        onShowFullBreakdown: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ showAllFactors: false });
    }

    get score() {
        return this.props.health?.score ?? 0;
    }

    get dashOffset() {
        const pct = Math.min(100, Math.max(0, this.score)) / 100;
        return 2 * Math.PI * 48 * (1 - pct);
    }

    get statusClass() {
        const s = this.score;
        if (s >= 80) return "gn-sd-health--good";
        if (s >= 60) return "gn-sd-health--ok";
        if (s >= 40) return "gn-sd-health--warn";
        return "gn-sd-health--bad";
    }

    get scoreDeltaLabel() {
        const d = this.props.health?.score_delta ?? 0;
        const sign = d > 0 ? "+" : "";
        return `${sign}${Number(d).toFixed(1)} vs período anterior`;
    }

    get topFactors() {
        const factors = [...(this.props.health?.factors || [])];
        if (this.state.showAllFactors) return factors;
        return factors.slice(0, 6);
    }

    get executiveBrief() {
        const h = this.props.health;
        if (!h) return null;
        const factors = h.factors || [];
        const strengths = factors.filter((f) => (f.normalized_score || 0) >= 70).slice(0, 2);
        const risks = factors.filter((f) => (f.normalized_score || 0) < 45).slice(0, 2);
        let recommendation = "";
        if (this.score >= 80) {
            recommendation = _t("Desempeño sólido. Mantenga el ritmo comercial y proteja márgenes.");
        } else if (this.score >= 60) {
            recommendation = _t("Resultados aceptables con oportunidades de mejora en factores débiles.");
        } else {
            recommendation = _t("Priorice acciones correctivas sobre meta, margen y pipeline.");
        }
        return { strengths, risks, recommendation, status: h.status };
    }

    factorBarClass(f) {
        return `gn-sd-health__bar-fill gn-sd-health__bar-fill--${f.status || "warn"}`;
    }

    onFactorClick(f, ev) {
        ev.stopPropagation();
        if (this.props.onFactorClick && f?.metric) {
            this.props.onFactorClick(f.metric);
        }
    }

    toggleBreakdown() {
        this.state.showAllFactors = !this.state.showAllFactors;
    }
}
