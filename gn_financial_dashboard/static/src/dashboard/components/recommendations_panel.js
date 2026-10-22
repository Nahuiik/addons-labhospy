/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Panel de "Recomendaciones automáticas".
 *
 * Lista priorizada de acciones sugeridas por el motor de scoring, cada una
 * con su prioridad (alta/media/baja), impacto esperado y, cuando aplica,
 * impacto económico estimado.
 *
 * Props:
 *  - recommendations: lista de objetos del motor.
 *  - title, icon (opcional).
 *  - fmt (opcional): función para formatear montos monetarios.
 */
export class RecommendationsPanel extends Component {
    static template = "gn_financial_dashboard.RecommendationsPanel";
    static props = {
        recommendations: Array,
        title: { type: String, optional: true },
        icon: { type: String, optional: true },
        fmt: { type: Function, optional: true },
    };

    priorityClass(p) {
        return {
            high: "gn-fd-reco--high",
            medium: "gn-fd-reco--medium",
            low: "gn-fd-reco--low",
        }[p] || "gn-fd-reco--low";
    }

    priorityLabel(p) {
        return {
            high: "Alta",
            medium: "Media",
            low: "Baja",
        }[p] || "Baja";
    }

    formatAmount(value) {
        if (!value) {
            return "";
        }
        if (this.props.fmt) {
            return this.props.fmt(value);
        }
        return value.toLocaleString("en-US");
    }
}
