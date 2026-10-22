/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatDate } from "../chart_helpers";

/**
 * Panel de Objetivos Estratégicos (V20 Fase 2, #19).
 *
 * Muestra las metas activas, su progreso y estado (en curso, alcanzado,
 * vencido) con un semáforo visual y barra de progreso.
 */
export class GoalsPanel extends Component {
    static template = "gn_financial_dashboard.GoalsPanel";
    static props = {
        payload: Object,
        onGoalClick: { type: Function, optional: true },
    };

    progressWidth(g) {
        const p = Math.max(0, Math.min(100, Number(g.progress || 0)));
        return p + "%";
    }

    statusLabel(g) {
        switch (g.status) {
            case "attained": return "Alcanzado";
            case "overdue": return "Vencido";
            default: return "En curso";
        }
    }

    statusTone(g) {
        switch (g.status) {
            case "attained": return "ok";
            case "overdue": return "danger";
            default: return "info";
        }
    }

    directionLabel(g) {
        return g.direction === "above" ? "Alcanzar o superar la meta"
                                       : "Mantenerse por debajo de la meta";
    }

    fmtDate(value) {
        return formatDate(value);
    }

    onClick(g) {
        if (this.props.onGoalClick) this.props.onGoalClick(g);
    }
}
