/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { loadEcharts, disposeEchart } from "./echarts_utils";
import { formatMonetary } from "@web/views/fields/formatters";

export class SalesForecastChart extends Component {
    static template = "gn_sales_dashboard.SalesForecastChart";
    static props = {
        config: Object,
        currencyId: { type: Number, optional: true },
        darkMode: { type: Boolean, optional: true },
        loading: { type: Boolean, optional: true },
    };

    setup() {
        this.chartRoot = useRef("chartRoot");
        this.chartInstance = null;
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => { this.chartInstance = disposeEchart(this.chartInstance); });
    }

    fmt(v) {
        return formatMonetary(v || 0, { currencyId: this.props.currencyId });
    }

    async renderChart() {
        const el = this.chartRoot.el;
        const cfg = this.props.config;
        if (!el || this.props.loading || cfg?.insufficient_data) {
            this.chartInstance = disposeEchart(this.chartInstance);
            return;
        }
        const echarts = await loadEcharts();
        this.chartInstance = disposeEchart(this.chartInstance);
        this.chartInstance = echarts.init(el);
        const labels = [...(cfg.historical_labels || []), ...(cfg.forecast_labels || [])];
        const hist = [...(cfg.historical_data || []), ...Array((cfg.forecast_labels || []).length).fill(null)];
        const fc = [...Array((cfg.historical_labels || []).length).fill(null), ...(cfg.forecast_data || [])];
        this.chartInstance.setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["Histórico", "Pronóstico"] },
            xAxis: { type: "category", data: labels },
            yAxis: { type: "value" },
            series: [
                { name: "Histórico", type: "line", data: hist, smooth: true },
                { name: "Pronóstico", type: "line", data: fc, smooth: true, lineStyle: { type: "dashed" } },
            ],
        }, true);
        this.chartInstance.resize();
    }
}
