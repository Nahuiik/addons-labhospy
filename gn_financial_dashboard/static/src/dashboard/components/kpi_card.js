/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Tarjeta KPI reutilizable.
 *
 * Muestra valor, comparativo (variación absoluta y %, flecha y color
 * favorable/desfavorable) y un tooltip de ayuda contable (qué es, cómo se
 * calcula, qué cuentas usa e interpretación).
 *
 * Props:
 *  - card: objeto preparado por el contenedor (label, value, icon, tone,
 *    delta, deltaAbs, dir, trend, meta).
 *  - onClick: callback opcional para drill-down al hacer clic.
 */
export class KpiCard extends Component {
    static template = "gn_financial_dashboard.KpiCard";
    static props = {
        card: Object,
        onClick: { type: Function, optional: true },
    };

    onCardClick() {
        if (this.props.onClick) {
            this.props.onClick(this.props.card);
        }
    }
}
