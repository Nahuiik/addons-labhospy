/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Lightweight SVG sparkline (no Chart.js dependency) for KPI cards.
 *
 * Props:
 *   - series: number[]  — points to plot (≥ 2 to render a line)
 *   - color: string     — line/area color (CSS color string)
 *   - height: number    — px height (default 28)
 *   - filled: boolean   — render area fill below the line
 *
 * The SVG uses ``preserveAspectRatio="none"`` to stretch nicely inside
 * the KPI card while keeping numeric resolution above 100 logical units.
 */
export class KpiSparkline extends Component {
    static template = "gn_banks_dashboard.KpiSparkline";
    static props = {
        series: { type: Array, optional: true },
        color: { type: String, optional: true },
        height: { type: Number, optional: true },
        filled: { type: Boolean, optional: true },
    };
    static defaultProps = {
        series: [],
        color: "#6366f1",
        height: 28,
        filled: true,
    };

    get hasSeries() {
        return Array.isArray(this.props.series) && this.props.series.length >= 2;
    }

    get viewBox() {
        return `0 0 100 ${this.props.height}`;
    }

    get path() {
        if (!this.hasSeries) {
            return "";
        }
        const data = this.props.series;
        const min = Math.min(...data, 0);
        const max = Math.max(...data, 0);
        const range = max - min || 1;
        const w = 100;
        const h = this.props.height;
        const stepX = w / Math.max(data.length - 1, 1);
        return data
            .map((v, i) => {
                const x = i * stepX;
                const y = h - ((v - min) / range) * (h - 2) - 1;
                return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
            })
            .join(" ");
    }

    get areaPath() {
        if (!this.hasSeries || !this.props.filled) {
            return "";
        }
        const linePath = this.path;
        const last = this.props.series.length - 1;
        const stepX = 100 / Math.max(last, 1);
        const xLast = (last * stepX).toFixed(2);
        const h = this.props.height;
        return `${linePath} L${xLast},${h} L0,${h} Z`;
    }

    get fillColor() {
        return this.props.color
            .replace(/^#/, "rgba(")
            .replace(")", "")
            .startsWith("rgba")
            ? this.props.color
            : this.hexToRgba(this.props.color, 0.18);
    }

    hexToRgba(hex, alpha) {
        const clean = (hex || "").replace("#", "");
        if (clean.length !== 6) {
            return `rgba(99, 102, 241, ${alpha})`;
        }
        const r = parseInt(clean.slice(0, 2), 16);
        const g = parseInt(clean.slice(2, 4), 16);
        const b = parseInt(clean.slice(4, 6), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
}
