/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Centro de decisiones: acciones prioritarias con impacto, beneficio y tiempo
 * estimado. Presenta el top-N de las recomendaciones, optimizado para
 * pantalla ejecutiva.
 *
 * Props:
 *  - decisions: lista del motor (subconjunto priorizado de recomendaciones).
 *  - title, icon (opcional).
 *  - fmt (opcional): formateador monetario.
 */
export class DecisionCenter extends Component {
    static template = "gn_financial_dashboard.DecisionCenter";
    static props = {
        decisions: Array,
        title: { type: String, optional: true },
        icon: { type: String, optional: true },
        fmt: { type: Function, optional: true },
    };

    priorityClass(p) {
        return {
            high: "gn-fd-decision--high",
            medium: "gn-fd-decision--medium",
            low: "gn-fd-decision--low",
        }[p] || "gn-fd-decision--low";
    }

    priorityLabel(p) {
        return { high: "Alta", medium: "Media", low: "Baja" }[p] || "Baja";
    }

    formatAmount(value) {
        if (!value) {
            return "—";
        }
        if (this.props.fmt) {
            return this.props.fmt(value);
        }
        return value.toLocaleString("en-US");
    }
}
