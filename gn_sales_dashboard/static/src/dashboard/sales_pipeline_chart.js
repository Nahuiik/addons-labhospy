/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { loadEcharts, disposeEchart } from "./echarts_utils";

export class SalesPipelineChart extends Component {
    static template = "gn_sales_dashboard.SalesPipelineChart";
    static props = {
        config: { type: Object, optional: true },
        darkMode: { type: Boolean, optional: true },
        loading: { type: Boolean, optional: true },
        onStageClick: { type: Function, optional: true },
    };

    setup() {
        this.chartRoot = useRef("chartRoot");
        this.chartInstance = null;
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(() => {
            this.chartInstance = disposeEchart(this.chartInstance);
        });
    }

    async renderChart() {
        const el = this.chartRoot.el;
        const cfg = this.props.config;
        if (!el || this.props.loading || !cfg?.labels?.length) {
            this.chartInstance = disposeEchart(this.chartInstance);
            return;
        }
        const echarts = await loadEcharts();
        this.chartInstance = disposeEchart(this.chartInstance);
        this.chartInstance = echarts.init(el);
        this.chartInstance.on("click", (params) => {
            const idx = params.dataIndex;
            if (this.props.onStageClick && cfg.stage_ids) {
                this.props.onStageClick(cfg.stage_ids[idx], cfg.labels[idx]);
            }
        });
        const textColor = this.props.darkMode ? "#94A3B8" : "#64748B";
        const data = (cfg.series?.[0]?.data || []).map((v, i) => ({
            value: v,
            name: `${cfg.labels[i]} (${cfg.counts?.[i] || 0})`,
        }));
        this.chartInstance.setOption({
            backgroundColor: "transparent",
            tooltip: { trigger: "item", formatter: "{b}: {c}" },
            series: [{
                type: "funnel",
                left: "10%",
                width: "80%",
                minSize: "10%",
                maxSize: "100%",
                sort: "descending",
                gap: 4,
                label: { color: textColor, fontSize: 11 },
                data,
            }],
            color: ["#3B82F6", "#6366F1", "#8B5CF6", "#A855F7", "#10B981", "#F59E0B"],
        }, true);
        this.chartInstance.resize();
    }
}
