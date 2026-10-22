/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Reusable empty/skeleton/loading components aligned with Odoo 19 UI.
 *
 * - GnEmptyState: icono + título + descripción + sugerencia/CTA opcional.
 * - GnLoadingSkeleton: bloques con shimmer (modo "card", "chart", "gauges").
 * - GnChartEmpty: overlay con ejes fantasma para mostrar la estructura
 *   del gráfico aún sin datos.
 */

export class GnEmptyState extends Component {
    static template = "gn_banks_dashboard.GnEmptyState";
    static props = {
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
        title: { type: String, optional: true },
        description: { type: String, optional: true },
        hint: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
        compact: { type: Boolean, optional: true },
    };
    static defaultProps = {
        icon: "fa-inbox",
        tone: "neutral",
        compact: false,
    };

    get toneClass() {
        return `gn-empty--${this.props.tone}`;
    }
}

export class GnLoadingSkeleton extends Component {
    static template = "gn_banks_dashboard.GnLoadingSkeleton";
    static props = {
        variant: { type: String, optional: true },
        rows: { type: Number, optional: true },
        height: { type: String, optional: true },
    };
    static defaultProps = {
        variant: "card",
        rows: 3,
        height: "auto",
    };

    get rowsArray() {
        return Array.from({ length: this.props.rows || 1 });
    }
}

export class GnChartEmpty extends Component {
    static template = "gn_banks_dashboard.GnChartEmpty";
    static props = {
        title: { type: String, optional: true },
        description: { type: String, optional: true },
        icon: { type: String, optional: true },
    };
    static defaultProps = {
        icon: "fa-line-chart",
    };
}
