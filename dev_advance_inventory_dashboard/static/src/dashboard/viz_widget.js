/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
    onPatched,
    useRef,
    useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadEcharts, disposeEchart, exportEchartPng, applyEchartsTheme } from "./echarts_utils";
import { loadChartJs, destroyChart, destroyCanvasChart, buildChartConfig } from "./chart_utils";

const MODEL = "inventory.dashboard.service";

/**
 * Widget genérico de visualización.
 * Recibe `config` normalizado del backend (engine, echarts_option, chartjs_def, drilldown…).
 */
export class InvVizWidget extends Component {
    static template = "dev_advance_inventory_dashboard.InvVizWidget";
    static props = {
        config: { type: Object, optional: true },
        darkMode: { type: Boolean, optional: true },
        height: { type: String, optional: true },
        filters: { type: Object, optional: true },
        onDrilldown: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.vizRoot = useRef("vizRoot");
        this.chartInstance = null;
        this.canvasChart = null;
        this._renderQueued = false;
        this.state = useState({ loading: false, error: null, fullscreen: false });

        onMounted(() => this.queueRender());
        onWillUpdateProps((nextProps) => {
            if (nextProps.config !== this.props.config || nextProps.darkMode !== this.props.darkMode) {
                this.queueRender();
            }
        });
        onPatched(() => {
            if (this._renderQueued) {
                this.queueRender(false);
            }
        });
        onWillUnmount(() => this.destroyViz());
    }

    get canvasId() {
        return `inv_viz_${this.props.config?.id || "chart"}`;
    }

    get isEcharts() {
        return this.props.config?.engine === "echarts";
    }

    queueRender(retry = true) {
        if (!this.props.config) {
            this.state.loading = false;
            return;
        }
        if (!this.vizRoot.el) {
            if (retry) {
                this._renderQueued = true;
            }
            return;
        }
        this._renderQueued = false;
        this.renderViz();
    }

    async renderViz() {
        this.destroyViz();
        this.state.error = null;
        const cfg = this.props.config;
        if (!cfg) {
            this.state.loading = false;
            return;
        }
        const el = this.vizRoot.el;
        if (!el) {
            this._renderQueued = true;
            return;
        }

        this.state.loading = true;
        try {
            if (cfg.engine === "echarts" && cfg.echarts_option) {
                const echarts = await loadEcharts();
                const dom = this.vizRoot.el;
                if (!dom) {
                    this._renderQueued = true;
                    return;
                }
                const option = applyEchartsTheme(cfg.echarts_option, this.props.darkMode);
                this.chartInstance = echarts.init(dom);
                this.chartInstance.setOption(option, true);
                this.chartInstance.on("click", (params) => this._onEchartsClick(params));
                this.chartInstance.resize();
            } else if (cfg.chartjs_def) {
                await loadChartJs();
                const canvas = this.vizRoot.el;
                if (!canvas || canvas.tagName !== "CANVAS") {
                    this._renderQueued = true;
                    return;
                }
                destroyCanvasChart(canvas);
                this.canvasChart = new Chart(
                    canvas.getContext("2d"),
                    buildChartConfig(cfg.chartjs_def)
                );
            } else {
                this.state.error = _t("Configuración de gráfico no válida");
            }
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    destroyViz() {
        this.chartInstance = disposeEchart(this.chartInstance);
        if (this.canvasChart) {
            const canvas = this.vizRoot.el;
            if (canvas && canvas.tagName === "CANVAS") {
                destroyCanvasChart(canvas);
            }
            this.canvasChart = destroyChart(this.canvasChart);
        }
    }

    async _onEchartsClick(params) {
        const drill = this.props.config?.drilldown;
        if (!drill?.enabled || !drill.metric) return;
        if (this.props.onDrilldown) {
            this.props.onDrilldown(drill.metric, params);
            return;
        }
        const action = await this.orm.call(MODEL, "get_drilldown_action", [
            drill.metric, [], this.props.filters || {},
        ]);
        if (action) this.actionService.doAction(action);
    }

    exportPng() {
        if (this.chartInstance) {
            exportEchartPng(this.chartInstance, `${this.props.config.id}.png`);
        } else if (this.canvasChart) {
            const canvas = this.vizRoot.el;
            if (canvas && canvas.tagName === "CANVAS") {
                const link = document.createElement("a");
                link.download = `${this.props.config.id}.png`;
                link.href = canvas.toDataURL("image/png");
                link.click();
            }
        }
    }

    toggleFullscreen() {
        this.state.fullscreen = !this.state.fullscreen;
        setTimeout(() => {
            this.queueRender();
            if (this.chartInstance) {
                this.chartInstance.resize();
            }
        }, 120);
    }
}
