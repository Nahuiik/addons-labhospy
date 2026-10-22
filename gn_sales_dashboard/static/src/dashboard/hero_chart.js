/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import { loadEcharts, disposeEchart, buildHeroChartOption, exportEchartPng } from "./echarts_utils";
import { SalesEmptyState } from "./empty_state";

export class SalesHeroChart extends Component {
    static template = "gn_sales_dashboard.SalesHeroChart";
    static components = { SalesEmptyState };
    static props = {
        config: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        groupBy: { type: String, optional: true },
        error: { type: [String, { value: null, optional: true }] },
        onDrilldown: { type: Function, optional: true },
        onGroupByChange: { type: Function, optional: true },
        onRetry: { type: Function, optional: true },
    };

    setup() {
        this.chartRoot = useRef("chartRoot");
        this.chartInstance = null;
        this._renderQueued = false;
        this._resizeObserver = null;
        this.state = useState({ exportBusy: false });

        onMounted(() => {
            this._setupResizeObserver();
            this.queueRender();
        });
        onWillUpdateProps((nextProps) => {
            if (
                nextProps.config !== this.props.config
                || nextProps.groupBy !== this.props.groupBy
                || nextProps.loading !== this.props.loading
                || nextProps.error !== this.props.error
            ) {
                this.queueRender();
            }
        });
        onPatched(() => {
            if (this._renderQueued) {
                this.queueRender(false);
            } else if (this.chartInstance && this.chartRoot.el) {
                this.chartInstance.resize();
            }
        });
        onWillUnmount(() => {
            this._teardownResizeObserver();
            this.destroyChart();
        });
    }

    _setupResizeObserver() {
        if (typeof ResizeObserver === "undefined") return;
        this._resizeObserver = new ResizeObserver(() => {
            if (this.chartInstance && this.chartRoot.el?.offsetWidth > 0) {
                this.chartInstance.resize();
            }
        });
    }

    _teardownResizeObserver() {
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
    }

    queueRender(retry = true) {
        if (this.props.loading || this.props.error || !this.displayConfig?.labels?.length) {
            this.destroyChart();
            return;
        }
        if (!this.chartRoot.el) {
            if (retry) this._renderQueued = true;
            return;
        }
        this._renderQueued = false;
        this.renderChart();
    }

    destroyChart() {
        if (this._resizeObserver && this.chartRoot.el) {
            try { this._resizeObserver.unobserve(this.chartRoot.el); } catch (_) { /* noop */ }
        }
        this.chartInstance = disposeEchart(this.chartInstance);
    }

    get displayConfig() {
        return this.props.config || {};
    }

    async renderChart() {
        const el = this.chartRoot.el;
        const cfg = this.displayConfig;
        if (!el || this.props.loading || this.props.error || !cfg?.labels?.length) return;
        if (el.offsetWidth === 0 || el.offsetHeight === 0) {
            this._renderQueued = true;
            return;
        }
        this.destroyChart();
        try {
            const echarts = await loadEcharts();
            const dom = this.chartRoot.el;
            if (!dom || dom.offsetWidth === 0) {
                this._renderQueued = true;
                return;
            }
            this.chartInstance = echarts.init(dom, null, { renderer: "canvas" });
            this.chartInstance.on("click", (params) => {
                if (this.props.onDrilldown && params?.name) {
                    this.props.onDrilldown(cfg.drilldown?.metric, params.name);
                }
            });
            const option = buildHeroChartOption(cfg, false);
            this.chartInstance.setOption(option, true);
            this.chartInstance.resize();
            if (this._resizeObserver) {
                this._resizeObserver.observe(dom);
            }
        } catch (e) {
            console.error("SalesHeroChart:", e);
        }
    }

    setGroupBy(mode) {
        if (this.props.onGroupByChange) {
            this.props.onGroupByChange(mode);
        }
    }

    async onExportPng() {
        if (!this.chartInstance || this.state.exportBusy) return;
        this.state.exportBusy = true;
        try {
            exportEchartPng(this.chartInstance, "tendencia-ventas.png");
        } finally {
            this.state.exportBusy = false;
        }
    }

    onRetryClick() {
        if (this.props.onRetry) {
            this.props.onRetry();
        }
    }
}
