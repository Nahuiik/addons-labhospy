/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Centro de decisiones priorizado (V20 Fase 6, #22).
 *
 * Recibe la lista del backend (get_decisions_data) y la renderiza como
 * tarjetas con urgencia y acción sugerida. Diferente de
 * `DecisionCenter` (legacy) — ese trabaja con el motor de
 * recomendaciones; este consume el motor V20.
 *
 * Props:
 *  - decisions: Array
 *  - total: Number
 *  - onDrill: Function (decision)
 */
export class DecisionHub extends Component {
    static template = "gn_financial_dashboard.DecisionHub";
    static props = {
        decisions: Array,
        total: { type: Number, optional: true },
        onDrill: { type: Function, optional: true },
    };

    urgencyClass(u) {
        if (u >= 5) return "gn-fd-deck-card--critical";
        if (u >= 4) return "gn-fd-deck-card--high";
        if (u >= 3) return "gn-fd-deck-card--medium";
        return "gn-fd-deck-card--low";
    }

    urgencyLabel(u) {
        if (u >= 5) return _t("Urgente");
        if (u >= 4) return _t("Alta");
        if (u >= 3) return _t("Media");
        return _t("Baja");
    }

    kindIcon(k) {
        return ({
            alert: "fa-exclamation-triangle",
            opportunity: "fa-lightbulb-o",
            optimization: "fa-rocket",
            insight: "fa-line-chart",
        })[k] || "fa-flag";
    }

    categoryLabel(c) {
        return ({
            liquidity: _t("Liquidez"),
            profitability: _t("Rentabilidad"),
            working_capital: _t("Capital de trabajo"),
            risk: _t("Riesgo"),
            growth: _t("Crecimiento"),
            other: _t("Otras"),
        })[c] || c || "—";
    }

    canDrill(d) {
        return !!(d.drilldown && Object.keys(d.drilldown).length);
    }

    onCardClick(d) {
        if (this.props.onDrill && this.canDrill(d)) {
            this.props.onDrill(d);
        }
    }
}
