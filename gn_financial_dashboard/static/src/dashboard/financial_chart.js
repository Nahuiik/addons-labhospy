/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, useEffect } from "@odoo/owl";
import { loadChartJs, destroyChart } from "./chart_helpers";

/**
 * Generic Chart.js wrapper. Pass a `config` getter (Chart.js config object)
 * and the component renders/updates/destroys the chart for you.
 *
 * Props:
 *  - config: Chart.js config object.
 *  - fingerprint: opcional; cambia cuando los datos cambian (para re-render).
 *  - height: opcional, alto del lienzo en px.
 *  - onClick: opcional, callback de drill-down recibiendo
 *    ``{ datasetIndex, index, label, value }`` al hacer clic en un elemento
 *    del gráfico (barra, sección de dona, punto, etc.). Si se define, el
 *    cursor cambia a pointer.
 */
export class FinancialChart extends Component {
    static template = "gn_financial_dashboard.FinancialChart";
    static props = {
        config: Object,
        fingerprint: { type: String, optional: true },
        height: { type: Number, optional: true },
        onClick: { type: Function, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        onMounted(() => this._render());
        onWillUnmount(() => {
            this.chart = destroyChart(this.chart);
        });
        useEffect(
            () => {
                this._render();
            },
            () => [this.props.fingerprint]
        );
    }

    async _render() {
        const canvas = this.canvasRef.el;
        if (!canvas) {
            return;
        }
        await loadChartJs();
        if (typeof Chart === "undefined") {
            return;
        }
        this.chart = destroyChart(this.chart);
        // Si hay onClick, inyectamos onClick + onHover en el config sin
        // mutar el objeto original (clonamos sólo el nivel `options`).
        const config = this._withClick(this.props.config);
        this.chart = new Chart(canvas, config);
    }

    _withClick(config) {
        if (!this.props.onClick) {
            return config;
        }
        const onClick = this.props.onClick;
        const options = { ...(config.options || {}) };
        const data = config.data || {};
        options.onClick = (_evt, elements) => {
            if (!elements || !elements.length) {
                return;
            }
            const el = elements[0];
            const dsIdx = el.datasetIndex ?? 0;
            const idx = el.index;
            const dataset = data.datasets ? data.datasets[dsIdx] : null;
            const label = (data.labels || [])[idx];
            const value = dataset ? dataset.data[idx] : null;
            onClick({ datasetIndex: dsIdx, index: idx, label, value });
        };
        options.onHover = (evt, elements) => {
            if (!evt.native || !evt.native.target) return;
            evt.native.target.style.cursor = elements.length ? "pointer" : "default";
        };
        return { ...config, options };
    }
}
