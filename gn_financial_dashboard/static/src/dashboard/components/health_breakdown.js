/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { formatDate } from "../chart_helpers";

/**
 * Desglose explicable del score financiero.
 *
 * Muestra el score global, el nivel y un panel desplegable con las
 * categorías que lo componen (puntos sumados/restados) y, dentro de cada
 * categoría, los criterios concretos que aportaron o restaron puntos
 * ("¿por qué obtuvo este puntaje?").
 *
 * Props:
 *  - health: payload de salud financiera (score, level, label, categories,
 *    alerts). Las categorías incluyen su lista de criterios.
 *  - period: { date_from, date_to } para mostrar el rango.
 */
export class HealthBreakdown extends Component {
    static template = "gn_financial_dashboard.HealthBreakdown";
    static props = {
        health: Object,
        period: { type: Object, optional: true },
    };

    setup() {
        this.ui = useState({ expanded: false, openCategory: null });
    }

    toggle() {
        this.ui.expanded = !this.ui.expanded;
    }

    openCategory(key) {
        this.ui.openCategory = this.ui.openCategory === key ? null : key;
    }

    get categories() {
        return this.props.health.categories || [];
    }

    pointsClass(points) {
        if (points > 0) {
            return "gn-fd-breakdown__pts gn-fd-breakdown__pts--up";
        }
        if (points < 0) {
            return "gn-fd-breakdown__pts gn-fd-breakdown__pts--down";
        }
        return "gn-fd-breakdown__pts";
    }

    pointsLabel(points) {
        if (points > 0) {
            return `+${points}`;
        }
        return `${points}`;
    }

    criterionIcon(c) {
        if (c.met) {
            return "fa-check-circle";
        }
        if (c.severity === "danger") {
            return "fa-times-circle";
        }
        return "fa-exclamation-triangle";
    }

    criterionClass(c) {
        if (c.met) {
            return "gn-fd-breakdown__crit--ok";
        }
        if (c.severity === "danger") {
            return "gn-fd-breakdown__crit--danger";
        }
        return "gn-fd-breakdown__crit--warn";
    }

    fmtDate(value) {
        return formatDate(value);
    }
}
