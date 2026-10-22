/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, onPatched } from "@odoo/owl";

/**
 * IndicatorGauge: medidor semicircular tipo "punto de referencia".
 *
 * Renderiza un gauge con 3 zonas de color (rojo / ámbar / verde) y una
 * aguja que apunta al valor actual. Las zonas, el rango (min/max) y la
 * dirección (higher_better / lower_better) vienen del backend.
 *
 * Props (`indicator`):
 *   key, name, formula, value, display, unit,
 *   min, max, direction, zones[{limit, color}], status,
 *   ok, warn, bad
 */
export class IndicatorGauge extends Component {
    static template = "gn_financial_dashboard.IndicatorGauge";
    static props = {
        indicator: Object,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this._chart = null;
        onMounted(() => this._render());
        onPatched(() => this._render());
        onWillUnmount(() => this._destroy());
    }

    _destroy() {
        if (this._chart) {
            try { this._chart.destroy(); } catch (e) { /* ignore */ }
            this._chart = null;
        }
    }

    _render() {
        if (!window.Chart) {
            return;
        }
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        this._destroy();

        const ind = this.props.indicator;
        const min = Number(ind.min ?? 0);
        const max = Number(ind.max ?? 100);
        const range = Math.max(max - min, 1e-9);

        const slices = [];
        const colors = [];
        let prev = min;
        for (const z of ind.zones || []) {
            const limit = Math.min(Math.max(Number(z.limit ?? max), min), max);
            const w = Math.max(limit - prev, 0);
            if (w > 0) {
                slices.push(w);
                colors.push(z.color);
                prev = limit;
            }
        }
        if (prev < max) {
            slices.push(max - prev);
            colors.push("#e5e7eb");
        }

        const rawValue = Number(ind.value ?? 0);
        const needleValue = Math.min(Math.max(rawValue, min), max);
        const needlePos = (needleValue - min) / range;
        this._overflow = rawValue > max ? "high" : (rawValue < min ? "low" : null);

        const needlePlugin = {
            id: "gn_fd_needle_" + ind.key,
            afterDatasetDraw: (chart) => {
                const { ctx, chartArea } = chart;
                const meta = chart.getDatasetMeta(0);
                const arc = meta.data[0];
                if (!arc) return;
                const cx = arc.x;
                const cy = arc.y;
                const outerR = arc.outerRadius;
                const innerR = arc.innerRadius;
                const angle = Math.PI + Math.PI * needlePos;

                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(angle);
                ctx.beginPath();
                ctx.moveTo(-3, 0);
                ctx.lineTo(0, -(outerR - 2));
                ctx.lineTo(3, 0);
                ctx.closePath();
                ctx.fillStyle = "#1f2937";
                ctx.fill();
                ctx.beginPath();
                ctx.arc(0, 0, 5, 0, 2 * Math.PI);
                ctx.fillStyle = "#1f2937";
                ctx.fill();
                ctx.restore();

                // Etiquetas de mínimo y máximo
                ctx.save();
                ctx.fillStyle = "#6b7280";
                ctx.font = "10px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText(this._fmtLimit(min), cx - (outerR + innerR) / 2, cy + 12);
                ctx.fillText(this._fmtLimit(max), cx + (outerR + innerR) / 2, cy + 12);
                ctx.restore();
            },
        };

        this._chart = new window.Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                datasets: [{
                    data: slices,
                    backgroundColor: colors,
                    borderWidth: 0,
                    circumference: 180,
                    rotation: 270,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                },
                animation: { duration: 300 },
            },
            plugins: [needlePlugin],
        });
    }

    _fmtLimit(v) {
        const n = Number(v);
        if (!isFinite(n)) return "";
        if (Math.abs(n) >= 1000) {
            try { return n.toLocaleString("en-US", { maximumFractionDigits: 0 }); }
            catch (e) { return String(Math.round(n)); }
        }
        return Number.isInteger(n) ? String(n) : n.toFixed(1);
    }

    get statusClass() {
        return ({
            good: "gn-fd-indicator gn-fd-indicator--good",
            warning: "gn-fd-indicator gn-fd-indicator--warn",
            danger: "gn-fd-indicator gn-fd-indicator--danger",
        })[this.props.indicator.status] || "gn-fd-indicator";
    }
}
