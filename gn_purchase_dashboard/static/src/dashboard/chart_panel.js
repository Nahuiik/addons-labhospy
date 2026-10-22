/** @odoo-module **/

import { Component, onMounted, onWillUnmount, onPatched, useRef } from "@odoo/owl";
import { loadEcharts, disposeEchart } from "./echarts_utils";

export class PurchaseChartPanel extends Component {
    static template = "gn_purchase_dashboard.PurchaseChartPanel";
    static props = {
        title: { type: String, optional: true },
        chartType: { type: String, optional: true },
        config: { type: Object, optional: true },
        optionBuilder: { type: Function, optional: true },
        loading: { type: Boolean, optional: true },
        darkMode: { type: Boolean, optional: true },
        height: { type: [String, Number], optional: true },
        onChartClick: { type: Function, optional: true },
        entityType: { type: String, optional: true },
    };

    setup() {
        this.chartRef = useRef("chart");
        this._chart = null;
        this._onChartClick = this._handleChartClick.bind(this);
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => {
            if (this._chart) {
                this._chart.off("click", this._onChartClick);
            }
            this._chart = disposeEchart(this._chart);
        });
    }

    get panelTitle() {
        return this.props.config?.title || this.props.title || "";
    }

    get panelClass() {
        return this.panelTitle
            ? "gn-pd-panel gn-pd-chart-panel"
            : "gn-pd-chart-panel gn-pd-chart-panel--embedded";
    }

    get chartHeight() {
        const h = this.props.height;
        if (h === undefined || h === null || h === "") return "280px";
        if (typeof h === "number") return `${h}px`;
        return h;
    }

    async renderChart() {
        if (this.props.loading || !this.chartRef.el) return;
        const echarts = await loadEcharts();
        if (!this._chart) {
            this._chart = echarts.init(this.chartRef.el);
        }
        const option = this.props.optionBuilder
            ? this.props.optionBuilder(this.props.config, this.props.darkMode)
            : (this.props.config?.option || {});
        this._chart.setOption(option, true);
        this._chart.resize();
        this._chart.off("click", this._onChartClick);
        if (this.props.onChartClick) {
            this._chart.on("click", this._onChartClick);
            this.chartRef.el.style.cursor = "pointer";
        }
    }

    _handleChartClick(params) {
        if (this.props.onChartClick) {
            this.props.onChartClick(params, this.props.config, this.props.entityType);
        }
    }
}
