/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { loadEcharts, disposeEchart, buildTimelineOption, buildBarOption, buildPieOption, buildGaugeOption } from "./echarts_utils";

export class InvPayChartPanel extends Component {
    static template = "gn_accounting_reports.InvPayChartPanel";
    static props = {
        chartId: String,
        chartKey: { type: String, optional: true },
        config: Object,
        type: { type: String, optional: true },
        currencySymbol: { type: String, optional: true },
        thresholds: { type: Object, optional: true },
        height: { type: String, optional: true },
        onChartClick: { type: Function, optional: true },
    };

    setup() {
        this.chartRef = useRef("chart");
        this._chart = null;
        onMounted(() => this._render());
        onPatched(() => this._render());
        onWillUnmount(() => {
            this._chart = disposeEchart(this._chart);
        });
    }

    async _render() {
        const el = this.chartRef.el;
        if (!el || !this.props.config) return;
        const echarts = await loadEcharts();
        this._chart = disposeEchart(this._chart);
        this._chart = echarts.init(el);
        const cfg = this.props.config;
        const sym = this.props.currencySymbol || "";
        let option = {};
        if (this.props.type === "gauge") {
            option = buildGaugeOption(cfg.value || 0, this.props.thresholds);
        } else if (this.props.type === "bar_h") {
            option = buildBarOption(cfg.labels || [], cfg.data || cfg.paid || [], true, {
                currencySymbol: sym,
                leftMargin: 160,
            });
        } else if (this.props.type === "bar") {
            option = buildBarOption(cfg.labels || [], cfg.data || cfg.invoiced || [], false, {
                currencySymbol: sym,
            });
        } else if (this.props.type === "pie") {
            option = buildPieOption(cfg.labels || [], cfg.data || [], {
                currencySymbol: sym,
                percentages: cfg.percentages || [],
            });
        } else {
            option = buildTimelineOption(cfg, sym);
        }
        this._chart.setOption(option);
        this._chart.off("click");
        if (this.props.onChartClick && this.props.chartKey) {
            this._chart.on("click", (params) => {
                this.props.onChartClick(this.props.chartKey, params.dataIndex, params.name);
            });
            this._chart.getZr().on("mousemove", (params) => {
                const over = params.target;
                el.style.cursor = over ? "pointer" : "default";
            });
        }
    }
}
