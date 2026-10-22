/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { debounce } from "@web/core/utils/timing";
import {
    Component,
    useState,
    onWillStart,
    onMounted,
    onWillUnmount,
    onPatched,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { formatDashboardDate, formatDashboardDateTime } from "./date_utils";
import { loadChartJs } from "./chart_utils";
import { drawSemicircleGauge } from "./gauge_utils";
import { InvDashboardFilterBar, InvDashboardLayoutEditor } from "./components";
import { InvVizWidget } from "./viz_widget";
import { AdvancedDataTable } from "./advanced_data_table";

const MODEL = "inventory.dashboard.service";

const DEFAULT_WIDGETS = [
    "executive_header", "executive_kpis", "hero_chart", "alerts_insights",
    "financial", "advanced_charts", "activity", "quick_actions", "tables",
];

const WIDGET_ALIASES = {
    health: "executive_header",
    kpis: "executive_kpis",
    charts: "advanced_charts",
    ai: "alerts_insights",
    insights: "alerts_insights",
    alerts: "alerts_insights",
};

function defaultFilters() {
    return {
        company_id: false,
        branch_id: false,
        warehouse_id: false,
        location_id: false,
        category_id: false,
        product_id: false,
        lot_id: false,
        supplier_id: false,
        customer_id: false,
        responsible_id: false,
        operation_type_id: false,
        period: "this_month",
        date_from: false,
        date_to: false,
    };
}

function normalizeWidgets(widgets) {
    if (!widgets?.length) {
        return DEFAULT_WIDGETS.map((id, order) => ({ id, type: id, visible: true, order }));
    }
    return widgets.map((w, i) => {
        const id = WIDGET_ALIASES[w.id] || w.id;
        return { ...w, id, type: id, order: w.order ?? i };
    });
}

export class InventoryDashboardPremium extends Component {
    static template = "dev_advance_inventory_dashboard.InventoryDashboardPremium";
    static components = {
        Layout,
        InvDashboardFilterBar,
        InvDashboardLayoutEditor,
        InvVizWidget,
        AdvancedDataTable,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this._refreshTimer = null;
        this.state = useState({
            coreLoading: true,
            widgetsLoading: {},
            widgetErrors: {},
            loadError: null,
            showAllKpis: false,
            showLayoutEditor: false,
            darkMode: false,
            refreshMinutes: 0,
            sparklineDays: 30,
            activeChartKey: "inventory_trend",
            activeTableKey: "out_of_stock",
            filterOptions: {},
            draftFilters: defaultFilters(),
            appliedFilters: defaultFilters(),
            layoutWidgets: normalizeWidgets(null),
            data: {
                header: {}, health: {}, kpis: [], alerts: [], insights: [],
                recommendations: [], charts: {}, quick_actions: [],
                activity_feed: [], financial_panel: {}, hero_chart: null,
            },
            layouts: [],
            activeLayoutId: false,
        });
        this._debouncedApply = debounce(() => this.applyFilters(), 500);
        onWillStart(() => this.bootstrap());
        onMounted(() => {
            this.setupAutoRefresh();
        });
        onPatched(() => this.scheduleHealthGaugeDraw());
        onWillUnmount(() => {
            this.clearAutoRefresh();
        });
    }

    get labels() {
        return {
            commandCenter: _t("Inventory Command Center"),
            apply: _t("Aplicar"),
            reset: _t("Restablecer"),
            branch: _t("Sucursal"),
            warehouse: _t("Almacén"),
            refresh: _t("Actualizar"),
            executiveReport: _t("Generar reporte ejecutivo"),
            inventoryHealth: _t("Inventory Health Score"),
            alertCenter: _t("Inventory Alert Center"),
            insights: _t("Operational Insights"),
            aiRecommendations: _t("AI Recommendations"),
            quickActions: _t("Acciones rápidas"),
            charts: _t("Análisis avanzado"),
            heroChart: _t("Gráfico principal"),
            executiveKpis: _t("Executive KPIs"),
            financialPanel: _t("Dashboard financiero"),
            activityFeed: _t("Actividad reciente"),
            tables: _t("Tablas operativas"),
            view: _t("Ver"),
            resolve: _t("Resolver"),
            showMore: _t("Ver más KPIs"),
            showLess: _t("Ver menos"),
            configureLayout: _t("Configurar layout"),
            exportPng: _t("PNG"),
            exportCsv: _t("CSV"),
            exportExcel: _t("Excel"),
            fullscreen: _t("Pantalla completa"),
            search: _t("Buscar…"),
            updatedAt: _t("Actualizado"),
            sparklinePeriod: _t("Historial sparkline"),
            insufficientHistory: _t("Historial insuficiente"),
            vsPrevious: _t("vs período anterior"),
            loadingWidget: _t("Cargando…"),
        };
    }

    get heroVizConfig() {
        return this.state.data.hero_chart
            || this.state.data.charts?.inventory_trend
            || this.state.data.charts?.receipts_vs_deliveries
            || null;
    }

    get activeChartConfig() {
        return this.state.data.charts?.[this.state.activeChartKey] || null;
    }

    isWidgetLoading(widgetId) {
        return !!this.state.widgetsLoading[widgetId];
    }

    widgetError(widgetId) {
        return this.state.widgetErrors[widgetId] || null;
    }

    isWidgetVisible(widgetId) {
        const resolved = WIDGET_ALIASES[widgetId] || widgetId;
        const w = this.state.layoutWidgets.find((x) => x.id === resolved || x.type === resolved);
        return w ? w.visible !== false : true;
    }

    get visibleKpis() {
        const kpis = this.state.data.kpis || [];
        return this.state.showAllKpis ? kpis : kpis.slice(0, 12);
    }

    get chartTabs() {
        return Object.keys(this.state.data.charts || {})
            .filter((k) => k !== "health_gauge")
            .map((key) => ({ id: key, label: this._chartTitle(key) }));
    }

    get tableTabs() {
        return [
            { id: "out_of_stock", label: _t("Agotados") },
            { id: "top_selling", label: _t("Más vendidos") },
            { id: "receipts", label: _t("Recepciones") },
            { id: "deliveries", label: _t("Entregas") },
        ];
    }

    formatUpdatedAt() {
        return formatDashboardDateTime(this.state.data.updated_at);
    }

    formatHeaderDate() {
        return formatDashboardDate(this.state.data.header?.today);
    }

    formatActivityDateTime(value) {
        return formatDashboardDateTime(value);
    }

    _chartTitle(key) {
        const map = {
            top_products: _t("Top productos"),
            receipts_vs_deliveries: _t("Recepciones vs entregas"),
            receipt_status: _t("Estado recepciones"),
            delivery_status: _t("Estado entregas"),
            top_categories: _t("Top categorías"),
            inventory_aging: _t("Inventory Aging"),
            stock_vs_reserved: _t("Disponible vs reservado"),
            abc_analysis: _t("Análisis ABC"),
            pareto: _t("Pareto"),
            waterfall: _t("Waterfall"),
            inventory_trend: _t("Inventory Turnover Trend"),
            supplier_performance: _t("Supplier Performance"),
            warehouse_capacity: _t("Warehouse Capacity"),
            movement_heatmap: _t("Heatmap"),
            xyz_analysis: _t("Análisis XYZ"),
            monthly_inventory_value: _t("Monthly Inventory Value"),
            sales_vs_inventory: _t("Sales vs Inventory"),
            dead_stock_analysis: _t("Dead Stock Analysis"),
        };
        return map[key] || key;
    }

    async bootstrap() {
        try {
            await loadChartJs();
            const opts = await this.orm.call(MODEL, "get_filter_options", []);
            this.state.filterOptions = opts;
            if (!this.state.draftFilters.company_id) {
                this.state.draftFilters.company_id = opts.company_id;
                this.state.appliedFilters.company_id = opts.company_id;
            }
            const layouts = await this.orm.call(MODEL, "get_user_layouts", []);
            this.state.layouts = layouts;
            const active = layouts.find((l) => l.is_default) || layouts[0];
            if (active) {
                this.state.activeLayoutId = active.id;
                const layout = active.layout || {};
                this.state.layoutWidgets = normalizeWidgets(layout.widgets);
                this.state.refreshMinutes = layout.refresh_minutes || 0;
                this.state.darkMode = layout.dark_mode || false;
            }
            await this.loadData();
        } catch (e) {
            this.state.loadError = e.message || String(e);
        }
    }

    async loadData() {
        this.state.loadError = null;
        await this.loadCore();
        await this.loadWidgetsProgressive();
    }

    async loadCore() {
        this.state.coreLoading = true;
        try {
            const core = await this.orm.call(MODEL, "get_dashboard_core", [
                this.state.appliedFilters,
                this.state.sparklineDays,
            ]);
            Object.assign(this.state.data, core);
            this.scheduleHealthGaugeDraw();
        } catch (e) {
            this.state.loadError = e.message || String(e);
        } finally {
            this.state.coreLoading = false;
        }
    }

    async loadWidgetsProgressive() {
        const groups = [
            { id: "alerts_insights", keys: ["alerts", "insights", "recommendations"] },
            { id: "financial", keys: ["financial"] },
            { id: "hero_chart", keys: ["hero_chart", "charts"] },
            { id: "advanced_charts", keys: ["charts"] },
            { id: "activity", keys: ["activity"] },
            { id: "quick_actions", keys: ["quick_actions"] },
        ];
        const tasks = groups
            .filter((g) => this.isWidgetVisible(g.id))
            .map(async (g) => {
                this.state.widgetsLoading[g.id] = true;
                this.state.widgetErrors[g.id] = null;
                try {
                    const payload = await this.orm.call(MODEL, "get_dashboard_widgets", [
                        this.state.appliedFilters,
                        g.keys,
                    ]);
                    Object.assign(this.state.data, payload);
                    if (payload.charts && !payload.charts[this.state.activeChartKey]) {
                        const keys = Object.keys(payload.charts);
                        this.state.activeChartKey = keys.includes("inventory_trend")
                            ? "inventory_trend"
                            : keys[0] || this.state.activeChartKey;
                    }
                } catch (e) {
                    this.state.widgetErrors[g.id] = e.message || String(e);
                } finally {
                    this.state.widgetsLoading[g.id] = false;
                }
            });
        await Promise.all(tasks);
    }

    onSparklineDaysChange(ev) {
        const days = parseInt(ev.target.value, 10);
        this.state.sparklineDays = [7, 30, 90, 365].includes(days) ? days : 30;
        this.loadCore();
    }

    onDraftChange(patch) {
        Object.assign(this.state.draftFilters, patch);
        this._debouncedApply();
    }

    applyFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.loadData();
    }

    resetFilters() {
        this.state.draftFilters = { ...defaultFilters(), company_id: this.state.filterOptions.company_id };
        this.applyFilters();
    }

    formatKpiVariation(kpi) {
        const pct = kpi.variation_pct ?? 0;
        const abs = kpi.variation_abs ?? 0;
        const sign = pct > 0 ? "+" : "";
        return `${sign}${Number(pct).toFixed(1)}% (${sign}${Number(abs).toLocaleString(undefined, { maximumFractionDigits: 1 })})`;
    }

    formatKpiPrevious(kpi) {
        return this.formatKpiValue({ ...kpi, value: kpi.previous_value });
    }

    formatKpiValue(kpi) {
        const v = kpi.value ?? kpi.count ?? 0;
        if (kpi.format === "money") {
            return formatMonetary(v, { currencyId: this.state.filterOptions.currency_id });
        }
        if (kpi.format === "percent") {
            return `${Number(v).toFixed(1)}%`;
        }
        if (["hours", "days", "ratio"].includes(kpi.format)) {
            return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
        }
        return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    formatFinValue(fin) {
        return this.formatKpiValue({ value: fin.value, count: fin.value, format: fin.format });
    }

    sparklinePath(points) {
        const vals = points || [];
        if (!vals.length) return "";
        const max = Math.max(...vals, 1);
        return vals.map((v, i) => {
            const x = (i / Math.max(vals.length - 1, 1)) * 80;
            const y = 24 - (v / max) * 24;
            return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }

    formatHealthScore() {
        return Math.round(this.state.data.health?.score ?? 0);
    }

    scheduleHealthGaugeDraw() {
        if (!this.state.data.health || this.state.coreLoading) {
            return;
        }
        requestAnimationFrame(() => {
            requestAnimationFrame(() => this.drawHealthGauge());
        });
    }

    drawHealthGauge() {
        const canvas = document.getElementById("inv_health_gauge");
        if (!canvas) return;
        drawSemicircleGauge(canvas, this.state.data.health?.score ?? 0, {
            label: "",
            textColor: "#ffffff",
            subtextColor: "rgba(255,255,255,0.85)",
            trackColor: "rgba(255,255,255,0.2)",
        });
    }

    setChartTab(key) {
        this.state.activeChartKey = key;
    }

    async onKpiClick(kpi) {
        const action = await this.orm.call(MODEL, "get_drilldown_action", [kpi.metric, [], this.state.appliedFilters]);
        if (action) this.actionService.doAction(action);
    }

    async onFinancialClick(fin) {
        if (!fin.metric) return;
        await this.onKpiClick({ metric: fin.metric });
    }

    async onActivityClick(act) {
        if (!act?.id || !act?.model) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: act.model,
            res_id: act.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onAlertClick(alert, resolve = false) {
        const method = resolve ? "get_resolve_action" : "get_drilldown_action";
        const args = resolve
            ? [alert.metric, this.state.appliedFilters]
            : [alert.metric, [], this.state.appliedFilters];
        const action = await this.orm.call(MODEL, method, args);
        if (action) this.actionService.doAction(action);
    }

    async onTableRowClick(row) {
        if (!row?.id || !row?.model) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: row.model,
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onQuickAction(action) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: action.label,
            res_model: action.model,
            view_mode: action.view === "form" ? "form" : "list,form",
            views: action.view === "form" ? [[false, "form"]] : [[false, "list"], [false, "form"]],
            target: "current",
            context: action.context || {},
        });
    }

    toggleDarkMode() {
        this.state.darkMode = !this.state.darkMode;
        this.scheduleHealthGaugeDraw();
    }

    setupAutoRefresh() {
        this.clearAutoRefresh();
        const mins = this.state.refreshMinutes;
        if (mins > 0) {
            this._refreshTimer = setInterval(() => this.loadData(), mins * 60 * 1000);
        }
    }

    clearAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
            this._refreshTimer = null;
        }
    }

    setRefreshMinutes(mins) {
        this.state.refreshMinutes = mins;
        this.setupAutoRefresh();
    }

    onRefreshIntervalChange(ev) {
        this.setRefreshMinutes(parseInt(ev.target.value, 10) || 0);
    }

    setTableTab(key) {
        this.state.activeTableKey = key;
    }

    async downloadExecutiveReport() {
        try {
            const action = await this.orm.call(
                MODEL, "get_executive_report_action", [this.state.appliedFilters]
            );
            this.actionService.doAction(action);
        } catch (_e) {
            await loadJS("/dev_advance_inventory_dashboard/static/lib/html2pdf.bundle.min.js");
            const element = document.getElementById("inv_dashboard_root");
            if (element && typeof html2pdf !== "undefined") {
                html2pdf().set({
                    margin: 8,
                    filename: "InventoryExecutiveReport.pdf",
                    html2canvas: { scale: 2 },
                    jsPDF: { unit: "mm", format: "a3", orientation: "landscape" },
                }).from(element).save();
            }
        }
    }

    toggleLayoutEditor() {
        this.state.showLayoutEditor = !this.state.showLayoutEditor;
    }

    onToggleWidget(widgetId) {
        const w = this.state.layoutWidgets.find((x) => x.id === widgetId);
        if (w) w.visible = !w.visible;
    }

    onMoveWidget(widgetId, delta) {
        const widgets = [...this.state.layoutWidgets];
        const idx = widgets.findIndex((x) => x.id === widgetId);
        const target = idx + delta;
        if (idx < 0 || target < 0 || target >= widgets.length) return;
        [widgets[idx], widgets[target]] = [widgets[target], widgets[idx]];
        widgets.forEach((w, i) => { w.order = i; });
        this.state.layoutWidgets = widgets;
    }

    onDragReorder(sourceId, targetId) {
        const widgets = [...this.state.layoutWidgets];
        const from = widgets.findIndex((x) => x.id === sourceId);
        const to = widgets.findIndex((x) => x.id === targetId);
        if (from < 0 || to < 0) return;
        const [item] = widgets.splice(from, 1);
        widgets.splice(to, 0, item);
        widgets.forEach((w, i) => { w.order = i; });
        this.state.layoutWidgets = widgets;
    }

    async applyLayoutPreset(presetId) {
        const preset = await this.orm.call(MODEL, "get_layout_preset", [presetId]);
        this.state.layoutWidgets = normalizeWidgets(preset.widgets);
        this.notification.add(_t("Plantilla aplicada."), { type: "info" });
    }

    async saveLayout() {
        const layout_json = {
            widgets: this.state.layoutWidgets,
            kpi_keys: [],
            chart_keys: [],
            refresh_minutes: this.state.refreshMinutes,
            dark_mode: this.state.darkMode,
        };
        const layoutId = await this.orm.call(MODEL, "save_user_layout", [
            this.state.activeLayoutId || false,
            _t("Predeterminado"),
            layout_json,
            true,
        ]);
        this.state.activeLayoutId = layoutId;
        this.state.showLayoutEditor = false;
        this.setupAutoRefresh();
        this.notification.add(_t("Layout guardado."), { type: "success" });
    }

    async resetLayout() {
        await this.orm.call(MODEL, "reset_user_layout", [this.state.activeLayoutId || false]);
        this.state.layoutWidgets = normalizeWidgets(null);
        this.notification.add(_t("Layout restablecido."), { type: "info" });
    }
}

registry.category("actions").add("open_inventory_dashboard", InventoryDashboardPremium);
