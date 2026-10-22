/** @odoo-module **/

import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { debounce } from "@web/core/utils/timing";
import { formatMonetary } from "@web/views/fields/formatters";
import { formatDashboardDateTime, periodLabel } from "./date_utils";
import { downloadBase64File } from "./export_utils";
import {
    buildBarOption, buildTreemapOption, buildHeatmapOption,
    buildGaugeOption, buildPieOption, buildForecastOption,
    buildHistogramOption, buildParetoOption, buildBoxplotOption,
    buildSankeyOption, buildWaterfallOption,
} from "./echarts_utils";
import {
    mergeLayout, gridItemStyle, swapLayoutItems, resizeLayoutItem, layoutToPayload,
    visibleLayout, layoutMetaPayload, toggleLayoutFlag,
} from "./widget_layout";
import { PurchaseFilterBar } from "./components";
import { PurchaseKpiCard } from "./kpi_card";
import { PurchaseHealthGauge } from "./health_gauge";
import { PurchaseAlertsPanel } from "./alerts_panel";
import { PurchaseInsightsPanel } from "./insights_panel";
import { PurchaseWidgetShell } from "./widget_shell";
import { PurchaseWidgetContent } from "./widget_content";
import { PurchaseEntitySidePanel } from "./entity_side_panel";
import { PurchaseDrilldownNavigator } from "./drilldown_navigator";
import { PurchaseAlertCenter } from "./alert_center";
import { PurchaseNarrativeBanner } from "./narrative_banner";
import { PurchaseMaturityGauges } from "./maturity_gauges";
import { PurchaseSimulatorPanel } from "./simulator_panel";
import { PurchaseComparativePanel } from "./comparative_panel";
import { splitKpis, filterChipLabel } from "./kpi_semantics";

const MODEL = "purchase.dashboard.service";
const FILTER_FAV_KEY = "gn_pd_purchase_filter_favorites";
const FILTER_PANEL_KEY = "gn_pd_purchase_filters_expanded";

const WIDGET_BATCHES = [
    ["monthly_purchases", "top_categories", "purchases_by_company", "sankey_flow", "waterfall_financial", "top_vendors"],
    ["heatmap", "price_variation", "lead_time", "kanban_summary"],
    ["receipts", "forecast", "abc_analysis", "concentration"],
    ["financial", "buyers", "products"],
];

function defaultFilters() {
    return {
        company_id: false, period: "this_month", compare_mode: "previous",
        date_from: false, date_to: false, branch_id: false, buyer_id: false,
        vendor_id: false, category_id: false, warehouse_id: false, po_state: false,
        project_id: false, tag_id: false,
    };
}

export class PurchaseDashboardPremium extends Component {
    static template = "gn_purchase_dashboard.PurchaseDashboardPremium";
    static components = {
        Layout, PurchaseFilterBar, PurchaseKpiCard, PurchaseHealthGauge,
        PurchaseAlertsPanel, PurchaseInsightsPanel, PurchaseWidgetShell, PurchaseWidgetContent,
        PurchaseEntitySidePanel, PurchaseDrilldownNavigator, PurchaseAlertCenter,
        PurchaseNarrativeBanner, PurchaseMaturityGauges, PurchaseSimulatorPanel, PurchaseComparativePanel,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this._loadSeq = 0;
        this._refreshTimer = null;
        this._resizeState = null;
        this._onResizeMove = this._handleResizeMove.bind(this);
        this._onResizeEnd = this._handleResizeEnd.bind(this);
        this._saveLayoutDebounced = debounce(() => this._persistLayout(), 700);
        this._presentationTimer = null;
        this._presentationPage = 0;
        this._onKeydown = this._handleKeydown.bind(this);
        this.state = useState({
            loading: true, widgetsLoading: false, filtersApplying: false,
            exportingCsv: false, exportingPdf: false, loadError: null, darkMode: false,
            autoRefresh: false, fullscreen: false, layoutEditMode: false,
            presentationMode: false, executiveView: false, mobileView: false, commandPaletteOpen: false,
            sidePanelOpen: false, sidePanelEntity: null,
            alertCenterOpen: false, simulatorOpen: false, comparativeOpen: false,
            drilldownOpen: true, drilldownLoading: false, drilldownLevel: "total",
            drilldownContext: {}, drilldownRows: [], drilldownBreadcrumb: [],
            layouts: [], activeLayoutId: false,
            heatmapDimension: "month_vendor", abcTab: "vendors", drilldownChain: [],
            widgetLayout: mergeLayout([]),
            filterOptions: {}, draftFilters: defaultFilters(), appliedFilters: defaultFilters(),
            data: { header: {}, kpis: [], currency: {}, metadata: {} },
            advanced: {}, widgets: {},
            filterFavorites: [],
            filterFavoritesOpen: false,
            filtersExpanded: false,
            actionsMenuOpen: false,
        });
        try {
            this.state.filterFavorites = JSON.parse(localStorage.getItem(FILTER_FAV_KEY) || "[]");
            const savedExpanded = localStorage.getItem(FILTER_PANEL_KEY);
            this.state.filtersExpanded = savedExpanded === "true";
        } catch {
            this.state.filterFavorites = [];
            this.state.filtersExpanded = false;
        }
        onWillStart(async () => {
            try {
                const filters = defaultFilters();
                const [filterOptions, init, layoutResp, layoutsResp] = await Promise.all([
                    this.orm.call(MODEL, "get_filter_options", []),
                    this.orm.call(MODEL, "get_dashboard_init", [filters]),
                    this.orm.call(MODEL, "get_user_layout", []),
                    this.orm.call(MODEL, "list_user_layouts", []),
                ]);
                this.state.filterOptions = filterOptions;
                if (filterOptions.company_id) {
                    this.state.draftFilters.company_id = filterOptions.company_id;
                    this.state.appliedFilters.company_id = filterOptions.company_id;
                }
                if (init?.core?.success) this.state.data = init.core;
                if (init?.advanced) Object.assign(this.state.advanced, init.advanced);
                const saved = layoutResp?.layout || {};
                if (saved.heatmapDimension) this.state.heatmapDimension = saved.heatmapDimension;
                this.state.widgetLayout = mergeLayout(saved.widgets, saved);
                this.state.layouts = layoutsResp || [];
                this.state.activeLayoutId = layoutResp?.id || false;
                this.state.drilldownChain = await this.orm.call(MODEL, "get_drilldown_chain", [filters]);
                await Promise.all([this.loadWidgetsProgressive(), this.loadDrilldownLevel("total", {})]);
                document.addEventListener("keydown", this._onKeydown);
                this._detectMobileView();
            } catch (e) {
                this.state.loadError = e.message || String(e);
            } finally {
                this.state.loading = false;
            }
        });
        onWillUnmount(() => {
            if (this._refreshTimer) clearInterval(this._refreshTimer);
            if (this._presentationTimer) clearInterval(this._presentationTimer);
            document.removeEventListener("keydown", this._onKeydown);
            this._cleanupResize();
        });
    }

    get display() { return { controlPanel: false }; }
    get rootClassName() {
        let cls = "gn-purchase-dashboard gn-pd-root";
        if (this.state.darkMode) cls += " gn-pd-root--dark";
        if (this.state.layoutEditMode) cls += " gn-pd-root--edit-layout";
        if (this.state.presentationMode) cls += " gn-pd-root--presentation";
        if (this.state.executiveView) cls += " gn-pd-root--executive";
        if (this.state.mobileView) cls += " gn-pd-root--mobile";
        return cls;
    }

    get visibleWidgetLayout() {
        if (this.state.executiveView) return [];
        const items = visibleLayout(this.state.widgetLayout);
        if (!this.state.presentationMode) return items;
        const pages = this._presentationPages();
        return pages[this._presentationPage] || items;
    }

    get narrativeText() {
        return this.state.advanced?.narrative || "";
    }

    get maturityIndexes() {
        return this.state.advanced?.maturity || [];
    }

    get labels() {
        return {
            apply: _t("Aplicar"), reset: _t("Restablecer"), clear: _t("Limpiar filtros"),
            branch: _t("Sucursal"), buyer: _t("Comprador"), vendor: _t("Proveedor"),
            warehouse: _t("Almacén"), category: _t("Categoría"), refresh: _t("Actualizar"),
            export: _t("Exportar Excel"), pdf: _t("Exportar PDF"), period: _t("Período"),
            compare: _t("Comparación"), poState: _t("Estado"),
            layoutEdit: _t("Editar layout"), layoutDone: _t("Guardar layout"),
            executiveSubtitle: _t("Análisis ejecutivo de procurement y cadena de suministro"),
            subtitle: periodLabel(this.state.data.filters),
            lastUpdate: formatDashboardDateTime(this.state.data.header?.generated_at),
            lastUpdateShort: this.state.data.header?.generated_at
                ? formatDashboardDateTime(this.state.data.header.generated_at).split(" ")[1] || ""
                : "",
        };
    }

    get primaryKpis() { return splitKpis(this.state.data.kpis).primary; }
    get secondaryKpis() { return splitKpis(this.state.data.kpis).secondary; }
    get currencyId() { return this.state.data.currency?.id || this.state.filterOptions.currency_id; }

    get activeFilterChips() {
        const chips = [];
        const f = this.state.appliedFilters;
        const opts = this.state.filterOptions;
        const labels = this.labels;
        for (const field of ["period", "compare_mode", "company_id", "date_from", "date_to",
            "branch_id", "buyer_id", "vendor_id", "warehouse_id", "category_id", "po_state",
            "project_id", "tag_id"]) {
            const val = f[field];
            if (!val || (field === "period" && val === "this_month") || (field === "compare_mode" && val === "previous")) continue;
            const label = filterChipLabel(field, val, opts, labels);
            if (label) chips.push({ field, label });
        }
        return chips;
    }

    get headerMetaLine() {
        const parts = [];
        if (this.state.filterOptions.company_name) parts.push(this.state.filterOptions.company_name);
        if (this.labels.subtitle) parts.push(this.labels.subtitle);
        const ts = this.labels.lastUpdateShort || this.labels.lastUpdate;
        if (ts) parts.push(ts);
        return parts.join(" · ");
    }

    get kanbanColumns() {
        const cols = this.state.widgets.kanban_summary?.columns || {};
        const cards = this.state.widgets.kanban_summary?.cards || [];
        return Object.keys(cols).map((key) => ({
            key, label: cols[key], cards: cards.filter((c) => c.state === key),
        }));
    }

    get leadTimeKpi() {
        return (this.state.data.kpis || []).find((k) => k.key === "avg_lead_time_days");
    }

    get urgentOrdersCount() {
        const kpi = (this.state.data.kpis || []).find((k) => k.key === "urgent_orders");
        return Math.round(kpi?.value || 0);
    }

    get widgetContentProps() {
        return {
            widgets: this.state.widgets,
            widgetsLoading: this.state.widgetsLoading,
            appliedFilters: this.state.appliedFilters,
            currencyId: this.currencyId,
            leadTimeKpi: this.leadTimeKpi,
            urgentOrdersCount: this.urgentOrdersCount,
            heatmapConfig: this.heatmapConfig,
            heatmapDimension: this.state.heatmapDimension,
            abcTab: this.state.abcTab,
            kanbanColumns: this.kanbanColumns,
            drilldownChain: this.state.drilldownChain,
            fmtMoney: this.fmtMoney.bind(this),
            buildMonthlyOption: this.buildMonthlyOption,
            buildTreemapOption: this.buildTreemapOption,
            buildCompanyOption: this.buildCompanyOption,
            buildHeatmapOption: this.buildHeatmapOption,
            buildSankeyOption: this.buildSankeyOption,
            buildWaterfallOption: this.buildWaterfallOption,
            buildLeadGaugeOption: this.buildLeadGaugeOption,
            buildLeadHistogramOption: this.buildLeadHistogramOption,
            buildBoxplotOption: this.buildBoxplotOption,
            buildReceiptsOption: this.buildReceiptsOption,
            buildForecastOption: this.buildForecastOption,
            buildAbcParetoOption: this.buildAbcParetoOption,
            setHeatmapDimension: this.setHeatmapDimension.bind(this),
            setAbcTab: this.setAbcTab.bind(this),
            onPoClick: this.onPoClick.bind(this),
            onTableRowClick: this.onTableRowClick.bind(this),
            onDrilldownChain: this.onDrilldownChain.bind(this),
            onOpenSidePanel: this.openSidePanel.bind(this),
            onChartClick: this.onChartClick.bind(this),
            darkMode: this.state.darkMode,
        };
    }

    fmtMoney(v) { return formatMonetary(v || 0, { currencyId: this.currencyId }); }
    gridStyleFor(item) { return gridItemStyle(item); }

    get heatmapConfig() {
        const hm = this.state.widgets.heatmap;
        if (!hm) return {};
        const dim = hm.dimensions?.[this.state.heatmapDimension];
        return { ...hm, data: dim?.data || hm.data };
    }

    buildMonthlyOption = (cfg) => buildBarOption(cfg?.labels, cfg?.series, this.state.darkMode);
    buildTreemapOption = (cfg) => buildTreemapOption(cfg?.treemap, this.state.darkMode);
    buildCompanyOption = (cfg) => buildBarOption(cfg?.labels, cfg?.series, this.state.darkMode);
    buildHeatmapOption = (cfg) => buildHeatmapOption(cfg?.data, this.state.darkMode);
    buildSankeyOption = (cfg) => buildSankeyOption(cfg, this.state.darkMode);
    buildWaterfallOption = (cfg) => buildWaterfallOption(cfg, this.state.darkMode);
    buildLeadGaugeOption = (cfg) => buildGaugeOption(cfg?.avg_days, 60, this.state.darkMode);
    buildLeadHistogramOption = (cfg) => buildHistogramOption(cfg?.distribution, this.state.darkMode);
    buildAbcParetoOption = (cfg) => buildParetoOption(cfg?.pareto?.[this.state.abcTab], this.state.darkMode);
    buildBoxplotOption = (cfg) => buildBoxplotOption(cfg?.boxplot, this.state.darkMode);
    buildReceiptsOption = (cfg) => buildPieOption([
        { name: _t("A tiempo"), value: cfg?.on_time || 0 },
        { name: _t("Tardías"), value: cfg?.late || 0 },
        { name: _t("Parciales"), value: cfg?.partial || 0 },
        { name: _t("No entregadas"), value: cfg?.not_delivered || 0 },
    ], this.state.darkMode);
    buildForecastOption = (cfg) => buildForecastOption(cfg?.points, this.state.darkMode);

    onSelect(field, value) { this.state.draftFilters[field] = value; }

    removeFilterChip(field) {
        const defaults = defaultFilters();
        if (field in defaults) this.state.draftFilters[field] = defaults[field];
        if (field === "company_id" && this.state.filterOptions.company_id) {
            this.state.draftFilters.company_id = this.state.filterOptions.company_id;
        }
        this.applyFilters();
    }

    async applyFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.state.widgets = {};
        this.state.filtersApplying = true;
        try {
            await this.loadInit();
            await this.loadWidgetsProgressive();
        } finally {
            this.state.filtersApplying = false;
        }
    }

    resetFilters() {
        this.state.draftFilters = defaultFilters();
        if (this.state.filterOptions.company_id) {
            this.state.draftFilters.company_id = this.state.filterOptions.company_id;
        }
        this.applyFilters();
    }

    saveFilterFavorite() {
        const name = periodLabel(this.state.draftFilters) || _t("Filtro personalizado");
        const entry = {
            id: Date.now(),
            name,
            filters: { ...this.state.draftFilters },
            savedAt: new Date().toISOString(),
        };
        const favs = [...this.state.filterFavorites, entry].slice(-8);
        this.state.filterFavorites = favs;
        localStorage.setItem(FILTER_FAV_KEY, JSON.stringify(favs));
        this.notification.add(_t("Filtro guardado en favoritos."), { type: "success" });
    }

    applyFilterFavorite(fav) {
        if (!fav?.filters) return;
        this.state.draftFilters = { ...defaultFilters(), ...fav.filters };
        if (this.state.filterOptions.company_id && !this.state.draftFilters.company_id) {
            this.state.draftFilters.company_id = this.state.filterOptions.company_id;
        }
        this.state.filterFavoritesOpen = false;
        this.applyFilters();
    }

    removeFilterFavorite(favId, ev) {
        ev?.stopPropagation();
        const favs = this.state.filterFavorites.filter((f) => f.id !== favId);
        this.state.filterFavorites = favs;
        localStorage.setItem(FILTER_FAV_KEY, JSON.stringify(favs));
    }

    toggleFilterFavorites() {
        this.state.filterFavoritesOpen = !this.state.filterFavoritesOpen;
    }

    toggleFiltersPanel() {
        this.state.filtersExpanded = !this.state.filtersExpanded;
        localStorage.setItem(FILTER_PANEL_KEY, String(this.state.filtersExpanded));
    }

    toggleActionsMenu() {
        this.state.actionsMenuOpen = !this.state.actionsMenuOpen;
    }

    closeActionsMenu() {
        this.state.actionsMenuOpen = false;
    }

    runHeaderAction(action) {
        this.closeActionsMenu();
        const map = {
            exportCsv: () => this.onExportCsv(),
            exportPdf: () => this.onExportPdf(),
            share: () => this.shareDashboard(),
            layout: () => this.toggleLayoutEdit(),
            fullscreen: () => this.toggleFullscreen(),
            autoRefresh: () => this.toggleAutoRefresh(),
            darkMode: () => this.toggleDarkMode(),
            presentation: () => this.togglePresentationMode(),
            alerts: () => { this.state.alertCenterOpen = true; },
            simulator: () => { this.state.simulatorOpen = true; },
            compare: () => { this.state.comparativeOpen = true; },
        };
        map[action]?.();
    }

    async loadInit() {
        const seq = ++this._loadSeq;
        this.state.loading = true;
        try {
            const init = await this.orm.call(MODEL, "get_dashboard_init", [this.state.appliedFilters]);
            if (seq !== this._loadSeq) return;
            if (init?.core?.success) this.state.data = init.core;
            if (init?.advanced) Object.assign(this.state.advanced, init.advanced);
        } catch (e) {
            if (seq === this._loadSeq) {
                this.state.loadError = e.message || String(e);
                this.notification.add(this.state.loadError, { type: "danger" });
            }
        } finally {
            if (seq === this._loadSeq) this.state.loading = false;
        }
    }

    async loadWidgetsProgressive() {
        this.state.widgetsLoading = true;
        try {
            for (const batch of WIDGET_BATCHES) {
                const missing = batch.filter((k) => !this.state.widgets[k]);
                if (!missing.length) continue;
                const r = await this.orm.call(MODEL, "get_dashboard_widgets", [this.state.appliedFilters, missing]);
                if (r.widgets) Object.assign(this.state.widgets, r.widgets);
            }
        } finally {
            this.state.widgetsLoading = false;
        }
    }

    toggleLayoutEdit() {
        this.state.layoutEditMode = !this.state.layoutEditMode;
        if (!this.state.layoutEditMode) {
            this._persistLayout();
            this.notification.add(_t("Layout guardado."), { type: "success" });
        }
    }

    onWidgetDrop(draggedId, targetId) {
        this.state.widgetLayout = swapLayoutItems(this.state.widgetLayout, draggedId, targetId);
        this._saveLayoutDebounced();
    }

    onResizeStart(widgetId, ev) {
        const item = this.state.widgetLayout.find((i) => i.id === widgetId);
        if (!item) return;
        const grid = document.querySelector(".gn-pd-widget-grid");
        const rect = grid?.getBoundingClientRect();
        this._resizeState = {
            id: widgetId,
            startX: ev.clientX,
            startY: ev.clientY,
            startW: item.w,
            startH: item.h,
            colWidth: rect ? rect.width / 12 : 80,
            rowHeight: 120,
        };
        document.addEventListener("mousemove", this._onResizeMove);
        document.addEventListener("mouseup", this._onResizeEnd);
    }

    _handleResizeMove(ev) {
        if (!this._resizeState) return;
        const { id, startX, startY, startW, startH, colWidth, rowHeight } = this._resizeState;
        const deltaW = Math.round((ev.clientX - startX) / colWidth);
        const deltaH = Math.round((ev.clientY - startY) / rowHeight);
        const item = this.state.widgetLayout.find((i) => i.id === id);
        if (!item) return;
        const w = Math.min(12 - item.x, Math.max(item.minW || 2, startW + deltaW));
        const h = Math.max(item.minH || 1, startH + deltaH);
        item.w = w;
        item.h = h;
    }

    _handleResizeEnd() {
        if (this._resizeState) {
            this._saveLayoutDebounced();
        }
        this._cleanupResize();
    }

    _cleanupResize() {
        this._resizeState = null;
        document.removeEventListener("mousemove", this._onResizeMove);
        document.removeEventListener("mouseup", this._onResizeEnd);
    }

    async _persistLayout() {
        const meta = layoutMetaPayload(this.state.widgetLayout);
        await this.orm.call(MODEL, "save_user_layout", [{
            widgets: layoutToPayload(this.state.widgetLayout),
            heatmapDimension: this.state.heatmapDimension,
            ...meta,
        }, this.state.activeLayoutId || false]);
    }

    async restoreDefaultLayout() {
        const r = await this.orm.call(MODEL, "restore_default_user_layout", [this.state.activeLayoutId || false]);
        this.state.widgetLayout = mergeLayout(r.layout?.widgets, r.layout);
        this.notification.add(_t("Layout restaurado."), { type: "success" });
    }

    async shareCurrentLayout() {
        if (!this.state.activeLayoutId) return;
        const r = await this.orm.call(MODEL, "share_user_layout", [this.state.activeLayoutId]);
        if (r.share_token) {
            await navigator.clipboard.writeText(r.share_token);
            this.notification.add(_t("Token de layout copiado."), { type: "success" });
        }
    }

    toggleWidgetHidden(widgetId) {
        this.state.widgetLayout = toggleLayoutFlag(this.state.widgetLayout, widgetId, "hidden");
        this._saveLayoutDebounced();
    }

    toggleWidgetPinned(widgetId) {
        this.state.widgetLayout = toggleLayoutFlag(this.state.widgetLayout, widgetId, "pinned");
        this._saveLayoutDebounced();
    }

    _detectMobileView() {
        this.state.mobileView = window.matchMedia("(max-width: 767px)").matches;
    }

    _presentationPages() {
        const pinned = this.state.widgetLayout.filter((w) => w.pinned && !w.hidden);
        const rest = visibleLayout(this.state.widgetLayout).filter((w) => !w.pinned);
        const pages = [];
        if (pinned.length) pages.push(pinned);
        for (let i = 0; i < rest.length; i += 4) {
            pages.push(rest.slice(i, i + 4));
        }
        return pages.length ? pages : [visibleLayout(this.state.widgetLayout)];
    }

    togglePresentationMode() {
        this.state.presentationMode = !this.state.presentationMode;
        if (this._presentationTimer) clearInterval(this._presentationTimer);
        if (this.state.presentationMode) {
            this._presentationPage = 0;
            const el = document.querySelector(".gn-pd-shell");
            if (el?.requestFullscreen) el.requestFullscreen();
            this._presentationTimer = setInterval(async () => {
                const pages = this._presentationPages();
                this._presentationPage = (this._presentationPage + 1) % pages.length;
                await this.loadInit();
            }, 20000);
        } else if (document.fullscreenElement && document.exitFullscreen) {
            document.exitFullscreen();
        }
    }

    _handleKeydown(ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
            ev.preventDefault();
            this.state.commandPaletteOpen = !this.state.commandPaletteOpen;
        }
        if (ev.key === "Escape") {
            this.state.sidePanelOpen = false;
            this.state.alertCenterOpen = false;
            this.state.simulatorOpen = false;
            this.state.comparativeOpen = false;
            this.state.commandPaletteOpen = false;
        }
        if (ev.key === "r" && !ev.target.closest("input, textarea, select")) {
            this.loadInit();
        }
    }

    runCommand(cmd) {
        this.state.commandPaletteOpen = false;
        const map = {
            refresh: () => this.loadInit(),
            dark: () => this.toggleDarkMode(),
            presentation: () => this.togglePresentationMode(),
            alerts: () => { this.state.alertCenterOpen = true; },
            simulator: () => { this.state.simulatorOpen = true; },
            compare: () => { this.state.comparativeOpen = true; },
            export: () => this.onExportCsv(),
            layout: () => this.toggleLayoutEdit(),
        };
        map[cmd]?.();
    }

    async loadDrilldownLevel(level, context) {
        this.state.drilldownLoading = true;
        try {
            const r = await this.orm.call(MODEL, "get_drilldown_level", [
                this.state.appliedFilters, level, context,
            ]);
            this.state.drilldownLevel = r.level;
            this.state.drilldownContext = r.context || context;
            this.state.drilldownRows = r.rows || [];
            this.state.drilldownBreadcrumb = r.breadcrumb || [];
        } finally {
            this.state.drilldownLoading = false;
        }
    }

    async onDrilldownNavigate(level, context) {
        await this.loadDrilldownLevel(level, context);
    }

    async onDrilldownRowClick(level, row) {
        const next = row.next_level;
        const ctx = { ...this.state.drilldownContext };
        if (level === "vendor" && row.partner_id) ctx.vendor_id = row.partner_id;
        if (level === "category" && row.category_id) ctx.category_id = row.category_id;
        if (level === "product" && row.product_id) ctx.product_id = row.product_id;
        if (level === "order" && row.order_id) {
            await this.onPoClick({ id: row.order_id });
            return;
        }
        if (next) await this.loadDrilldownLevel(next, ctx);
    }

    openSidePanel(row) {
        const entityType = row.partner_id ? "vendor" : row.product_id ? "product" : "vendor";
        const entityId = row.partner_id || row.product_id;
        if (!entityId) return;
        this.state.sidePanelEntity = { type: entityType, id: entityId, label: row.name || row.vendor };
        this.state.sidePanelOpen = true;
    }

    _resolveEntityFromName(name) {
        if (!name) return null;
        const norm = (s) => String(s || "").trim().toLowerCase();
        const target = norm(name);
        const matchName = (row) => {
            const n = norm(row.name);
            return n === target || n.startsWith(target) || target.startsWith(n);
        };
        const vendorRow = (this.state.widgets.top_vendors?.rows || []).find(matchName);
        if (vendorRow?.partner_id) return { partner_id: vendorRow.partner_id, name: vendorRow.name };
        const concRow = (this.state.widgets.concentration?.rows || []).find(matchName);
        if (concRow?.partner_id) return { partner_id: concRow.partner_id, name: concRow.name };
        const productRow = (this.state.widgets.products?.rows || []).find(matchName);
        if (productRow?.product_id) return { product_id: productRow.product_id, name: productRow.name };
        const vendorOpt = (this.state.filterOptions.vendors || []).find((v) => norm(v.name) === target);
        if (vendorOpt?.id) return { partner_id: vendorOpt.id, name: vendorOpt.name };
        return null;
    }

    onChartClick(params, config, entityType) {
        let name = params?.name;
        if (params?.seriesType === "heatmap" && Array.isArray(params.data)) {
            const hmData = config?.data || this.heatmapConfig?.data || [];
            const vendors = [...new Set(hmData.map((d) => d[1]))];
            name = vendors[params.data[1]] || name;
        }
        if (params?.data?.name) name = params.data.name;
        const resolved = this._resolveEntityFromName(name);
        if (resolved) {
            this.openSidePanel(resolved);
            return;
        }
        if (entityType === "vendor" || entityType === "product") {
            this.notification.add(_t("Abra la tabla de proveedores o productos para ver el detalle."), { type: "info" });
        }
    }

    closeSidePanel() {
        this.state.sidePanelOpen = false;
        this.state.sidePanelEntity = null;
    }

    setHeatmapDimension(dim) {
        this.state.heatmapDimension = dim;
        this._saveLayoutDebounced();
    }

    setAbcTab(tab) { this.state.abcTab = tab; }

    toggleExecutiveView() {
        this.state.executiveView = !this.state.executiveView;
        if (this.state.executiveView && !this.state.widgets.forecast) {
            this.orm.call(MODEL, "get_dashboard_widgets", [this.state.appliedFilters, ["forecast"]])
                .then((r) => { if (r.widgets) Object.assign(this.state.widgets, r.widgets); });
        }
    }

    toggleDarkMode() { this.state.darkMode = !this.state.darkMode; }

    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
        if (this._refreshTimer) clearInterval(this._refreshTimer);
        if (this.state.autoRefresh) {
            this._refreshTimer = setInterval(() => this.loadInit(), 120000);
        }
    }

    toggleFullscreen() {
        const el = document.querySelector(".gn-pd-shell");
        if (!document.fullscreenElement && el?.requestFullscreen) {
            el.requestFullscreen();
            this.state.fullscreen = true;
        } else if (document.exitFullscreen) {
            document.exitFullscreen();
            this.state.fullscreen = false;
        }
    }

    async shareDashboard() {
        try {
            await navigator.clipboard.writeText(window.location.href);
            this.notification.add(_t("Enlace del dashboard copiado al portapapeles."), { type: "success" });
        } catch {
            this.notification.add(_t("No se pudo copiar el enlace."), { type: "warning" });
        }
    }

    async onExportPdf() {
        if (this.state.exportingPdf) return;
        this.state.exportingPdf = true;
        try {
            const action = await this.orm.call(MODEL, "get_executive_report_action", [this.state.appliedFilters]);
            if (action?.type) this.actionService.doAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.exportingPdf = false;
        }
    }

    async onExportCsv() {
        if (this.state.exportingCsv) return;
        this.state.exportingCsv = true;
        try {
            const r = await this.orm.call(MODEL, "export_kpis_csv", [this.state.appliedFilters]);
            downloadBase64File(r);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.exportingCsv = false;
        }
    }

    async onKpiClick(kpi) {
        const action = await this.orm.call(MODEL, "get_drilldown_action", [kpi.metric, [], this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onDrilldown(metric, extraDomain = []) {
        const action = await this.orm.call(MODEL, "get_drilldown_action", [metric, extraDomain, this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onVendorClick(row) {
        if (!row?.partner_id) return;
        this.openSidePanel(row);
    }

    async onPoClick(card) {
        if (!card?.id) return;
        this.actionService.doAction({
            type: "ir.actions.act_window", res_model: "purchase.order", res_id: card.id,
            views: [[false, "form"]], target: "current",
        });
    }

    async onInsightClick(insight) {
        if (!insight?.metric) return;
        await this.onDrilldown(insight.metric);
    }

    async onDrilldownChain(item) {
        if (!item) return;
        if (item.metric) {
            await this.onDrilldown(item.metric, item.domain || []);
            return;
        }
        const action = await this.orm.call(MODEL, "get_entity_drilldown", [
            this.state.appliedFilters, item.model, item.domain || [], item.label,
        ]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onAlertClick(alert) {
        if (!alert?.metric) return;
        await this.onDrilldown(alert.metric);
    }

    async onTableRowClick(row) {
        if (row?.partner_id) this.openSidePanel(row);
        else if (row?.product_id) this.openSidePanel(row);
    }
}
