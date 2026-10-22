/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Velocímetro SVG de riesgo financiero (5 estados).
 *
 * Props:
 *  - risk: { value (0-100), level, label }.
 */
export class RiskGauge extends Component {
    static template = "gn_financial_dashboard.RiskGauge";
    static props = {
        risk: Object,
    };

    // Geometría del velocímetro semicircular (180°).
    static GEOMETRY = {
        cx: 100,
        cy: 100,
        r: 80,
        stroke: 16,
    };

    // 5 tramos del arco: muy bajo riesgo (verde) → crítico (rojo).
    static BANDS = [
        { from: 0, to: 20, color: "#dc3545", labelKey: "critical" },
        { from: 20, to: 40, color: "#e67e22", labelKey: "high" },
        { from: 40, to: 60, color: "#f1c40f", labelKey: "moderate" },
        { from: 60, to: 80, color: "#3498db", labelKey: "low" },
        { from: 80, to: 100, color: "#198754", labelKey: "very_low" },
    ];

    get geometry() {
        return this.constructor.GEOMETRY;
    }

    get bands() {
        return this.constructor.BANDS;
    }

    // Convierte un valor 0..100 a coordenadas (x, y) sobre el arco semicircular.
    pointAt(value) {
        const g = this.geometry;
        const v = Math.max(0, Math.min(100, value));
        const angle = Math.PI - (v / 100) * Math.PI;
        return {
            x: g.cx + g.r * Math.cos(angle),
            y: g.cy - g.r * Math.sin(angle),
        };
    }

    // Devuelve el path SVG (arco) entre dos valores 0..100.
    arcPath(from, to) {
        const a = this.pointAt(from);
        const b = this.pointAt(to);
        const r = this.geometry.r;
        // largeArcFlag siempre 0 (cada banda < 180°), sweep 1 (horario).
        return `M ${a.x} ${a.y} A ${r} ${r} 0 0 1 ${b.x} ${b.y}`;
    }

    get value() {
        return Math.max(0, Math.min(100, this.props.risk?.value || 0));
    }

    get needlePoint() {
        return this.pointAt(this.value);
    }

    get levelLabel() {
        return this.props.risk?.label || "";
    }

    get levelKey() {
        return this.props.risk?.level || "moderate";
    }
}
