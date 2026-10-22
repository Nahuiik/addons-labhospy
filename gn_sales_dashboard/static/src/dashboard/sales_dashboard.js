/** @odoo-module **/

import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { formatDashboardDateTime, periodLabel } from "./date_utils";
import { downloadBase64File } from "./export_utils";
import { aggregateHeroChart } from "./echarts_utils";
import { SalesFilterBar } from "./components";
import { SalesKpiCard } from "./kpi_card";
import { SalesHeroChart } from "./hero_chart";
import { SalesRankingPanel } from "./sales_ranking_panel";
import { SalesPipelineChart } from "./sales_pipeline_chart";
import { SalesDataTable } from "./sales_data_table";
import { SalesHealthGauge } from "./sales_health_gauge";
import { SalesAlertsPanel } from "./sales_alerts_panel";
import { SalesForecastChart } from "./sales_forecast_chart";
import { SalesGoalTrackerCard } from "./goal_tracker_card";
import { SalesInsightsPanel } from "./insights_panel";
import { SalesTopRankingCard } from "./top_ranking_card";
import { splitKpis, filterChipLabel } from "./kpi_semantics";

const MODEL = "sales.dashboard.service";

const SECTIONS = [
    { id: "summary", label: _t("Resumen") },
    { id: "sellers", label: _t("Vendedores") },
    { id: "products", label: _t("Productos") },
    { id: "customers", label: _t("Clientes") },
    { id: "pipeline", label: _t("Pipeline") },
    { id: "analytics", label: _t("Análisis") },
    { id: "forecast", label: _t("Pronóstico") },
    { id: "alerts", label: _t("Alertas") },
    { id: "operations", label: _t("Operaciones") },
];

const WIDGET_MAP = {
    sellers: ["seller_ranking", "team_ranking"],
    products: ["top_products"],
    customers: ["top_customers"],
    pipeline: ["pipeline_funnel", "pipeline_chart"],
};

const ADVANCED_MAP = {
    summary: ["health", "goal_tracker", "alerts"],
    analytics: ["waterfall", "rfm", "pareto_customers", "pareto_products", "cohorts"],
    forecast: ["forecast"],
    alerts: ["alerts"],
};

function defaultFilters() {
    return {
        company_id: false, period: "this_month", compare_mode: "previous",
        date_from: false, date_to: false, branch_id: false, team_id: false,
        user_id: false, journal_id: false, warehouse_id: false, channel_id: false,
        partner_id: false, category_id: false, product_id: false, order_state: false,
    };
}

export class SalesDashboardPremium extends Component {
    static template = "gn_sales_dashboard.SalesDashboardPremium";
    static components = {
        Layout, SalesFilterBar, SalesKpiCard, SalesHeroChart, SalesRankingPanel,
        SalesPipelineChart, SalesDataTable, SalesHealthGauge, SalesAlertsPanel,
        SalesForecastChart, SalesGoalTrackerCard, SalesInsightsPanel, SalesTopRankingCard,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this._loadSeq = 0;
        this.sections = SECTIONS;
        this.state = useState({
            loading: true, widgetsLoading: false, advancedLoading: false,
            filtersApplying: false, exportingCsv: false, exportingPdf: false,
            loadError: null, heroError: "",
            activeSection: "summary", heroGroupBy: "day",
            filterOptions: {}, draftFilters: defaultFilters(), appliedFilters: defaultFilters(),
            data: { header: {}, kpis: [], charts: {}, currency: {}, metadata: {} },
            widgets: {}, advanced: {},
        });
        onWillStart(async () => {
            try {
                const filters = defaultFilters();
                const [filterOptions, init] = await Promise.all([
                    this.orm.call(MODEL, "get_filter_options", []),
                    this.orm.call(MODEL, "get_dashboard_init", [filters, 30]),
                ]);
                this.state.filterOptions = filterOptions;
                if (filterOptions.company_id) {
                    this.state.draftFilters.company_id = filterOptions.company_id;
                    this.state.appliedFilters.company_id = filterOptions.company_id;
                }
                if (init?.core?.success) {
                    this.state.data = init.core;
                }
                if (init?.advanced) {
                    Object.assign(this.state.advanced, init.advanced);
                }
            } catch (e) {
                this.state.loadError = e.message || String(e);
            } finally {
                this.state.loading = false;
                this.state.advancedLoading = false;
            }
        });
    }

    get display() { return { controlPanel: false }; }
    get rootClassName() { return "gn-sales-dashboard gn-sd-root"; }

    get labels() {
        return {
            apply: _t("Aplicar"), reset: _t("Restablecer"), clear: _t("Limpiar filtros"),
            branch: _t("Sucursal"), team: _t("Equipo comercial"), salesperson: _t("Vendedor"),
            journal: _t("Diario"), refresh: _t("Actualizar"), export: _t("Exportar"),
            pdf: _t("PDF ejecutivo"), period: _t("Período"), compare: _t("Comparación"),
            executiveSubtitle: _t("Resumen ejecutivo del rendimiento comercial"),
            subtitle: periodLabel(this.state.data.filters),
            lastUpdate: formatDashboardDateTime(this.state.data.header?.generated_at),
            compareLabel: this._compareLabel(),
        };
    }

    _compareLabel() {
        const mode = this.state.appliedFilters.compare_mode;
        const found = (this.state.filterOptions.compare_modes || []).find((c) => c.id === mode);
        return found?.label || mode;
    }

    get primaryKpis() { return splitKpis(this.state.data.kpis).primary; }
    get secondaryKpis() { return splitKpis(this.state.data.kpis).secondary; }

    get activeFilterChips() {
        const chips = [];
        const f = this.state.appliedFilters;
        const opts = this.state.filterOptions;
        const labels = this.labels;
        const fields = [
            "period", "compare_mode", "company_id", "date_from", "date_to",
            "branch_id", "team_id", "user_id", "journal_id", "warehouse_id",
            "category_id", "channel_id", "order_state",
        ];
        for (const field of fields) {
            const val = f[field];
            if (!val || (field === "period" && val === "this_month") || (field === "compare_mode" && val === "previous")) {
                continue;
            }
            const label = filterChipLabel(field, val, opts, labels);
            if (label) chips.push({ field, label });
        }
        return chips;
    }

    get canConfigureGoal() {
        return !!this.state.advanced.goal_tracker?.configure_action;
    }

    get currencyId() {
        return this.state.data.currency?.id || this.state.filterOptions.currency_id;
    }

    get heroChart() {
        const raw = this.state.data.charts?.hero_sales || {};
        return aggregateHeroChart(raw, this.state.heroGroupBy);
    }

    fmtMoney(v) { return formatMonetary(v || 0, { currencyId: this.currencyId }); }

    onSelect(field, value) { this.state.draftFilters[field] = value; }

    removeFilterChip(field) {
        const defaults = defaultFilters();
        if (field in defaults) {
            this.state.draftFilters[field] = defaults[field];
        }
        if (field === "company_id" && this.state.filterOptions.company_id) {
            this.state.draftFilters.company_id = this.state.filterOptions.company_id;
        }
        this.applyFilters();
    }

    setHeroGroupBy(mode) { this.state.heroGroupBy = mode; }

    async onConfigureGoal(action) {
        if (action?.type) this.actionService.doAction(action);
    }

    async onInsightClick(insight) {
        if (!insight?.metric) return;
        if (insight.metric === "pareto_customers") {
            this.state.activeSection = "analytics";
            await this.loadSectionData("analytics");
            return;
        }
        const action = await this.orm.call(MODEL, "get_drilldown_action", [insight.metric, [], this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onViewAllSection(section) {
        this.state.activeSection = section;
        await this.loadSectionData(section);
    }

    async onViewAllAlerts() {
        this.state.activeSection = "alerts";
        await this.loadSectionData("alerts");
    }

    async onTop5RowClick(section, row) {
        if (section === "sellers" || section === "products") {
            await this.onRankingClick(row);
        } else if (section === "customers") {
            await this.onCustomerClick(row);
        }
    }

    async onFactorClick(metric) {
        await this.onKpiClick({ metric });
    }

    async applyFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.state.widgets = {};
        this.state.advanced = {};
        this.state.filtersApplying = true;
        try {
            await this.loadInit();
            await this.loadSectionData(this.state.activeSection);
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

    async loadInit() {
        const seq = ++this._loadSeq;
        this.state.loading = true;
        this.state.advancedLoading = true;
        this.state.heroError = "";
        try {
            const init = await this.orm.call(
                MODEL, "get_dashboard_init", [this.state.appliedFilters, 30],
            );
            if (seq !== this._loadSeq) return;
            if (init?.core?.success) {
                this.state.data = init.core;
            }
            if (init?.advanced) {
                Object.assign(this.state.advanced, init.advanced);
            }
        } catch (e) {
            if (seq === this._loadSeq) {
                this.state.heroError = e.message || String(e);
                this.state.loadError = this.state.heroError;
                this.notification.add(this.state.heroError, { type: "danger" });
            }
        } finally {
            if (seq === this._loadSeq) {
                this.state.loading = false;
                this.state.advancedLoading = false;
            }
        }
    }

    async loadData() {
        const seq = ++this._loadSeq;
        this.state.loading = true;
        try {
            const result = await this.orm.call(MODEL, "get_dashboard_core", [this.state.appliedFilters, 30]);
            if (seq === this._loadSeq && result.success) this.state.data = result;
        } catch (e) {
            if (seq === this._loadSeq) {
                this.state.heroError = e.message || String(e);
                this.notification.add(this.state.heroError, { type: "danger" });
            }
        } finally {
            if (seq === this._loadSeq) this.state.loading = false;
        }
    }

    async setSection(sectionId) {
        this.state.activeSection = sectionId;
        await this.loadSectionData(sectionId);
    }

    async loadSectionData(sectionId) {
        if (sectionId === "operations") return;
        await Promise.all([
            this.loadWidgets(sectionId),
            this.loadAdvanced(sectionId),
        ]);
    }

    async loadWidgets(sectionId) {
        const keys = WIDGET_MAP[sectionId];
        if (!keys?.length) return;
        const missing = keys.filter((k) => !this.state.widgets[k]);
        if (!missing.length) return;
        this.state.widgetsLoading = true;
        try {
            const r = await this.orm.call(MODEL, "get_dashboard_widgets", [this.state.appliedFilters, missing]);
            if (r.widgets) Object.assign(this.state.widgets, r.widgets);
        } finally { this.state.widgetsLoading = false; }
    }

    async loadAdvanced(sectionId) {
        const keys = ADVANCED_MAP[sectionId];
        if (!keys?.length) return;
        const missing = keys.filter((k) => !this.state.advanced[k]);
        if (!missing.length) return;
        this.state.advancedLoading = true;
        try {
            const r = await this.orm.call(MODEL, "get_dashboard_advanced", [this.state.appliedFilters, missing]);
            if (r.advanced) Object.assign(this.state.advanced, r.advanced);
        } finally { this.state.advancedLoading = false; }
    }

    async onExportCsv() {
        if (this.state.loading || this.state.exportingCsv) return;
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

    async onExportPdf() {
        if (this.state.loading || this.state.exportingPdf) return;
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

    async onKpiClick(kpi) {
        const action = await this.orm.call(MODEL, "get_drilldown_action", [kpi.metric, [], this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onHeroDrilldown(metric) {
        const action = await this.orm.call(MODEL, "get_drilldown_action", [metric || "net_sales", [], this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onRankingClick(row) {
        if (!row?.model) return;
        const action = await this.orm.call(MODEL, "get_entity_drilldown", [
            this.state.appliedFilters, row.model, row.domain || [], row.name,
        ]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onPipelineStage(stageId, stageName) {
        const domain = stageId ? [["stage_id", "=", stageId]] : [["stage_id", "=", false]];
        const action = await this.orm.call(MODEL, "get_entity_drilldown", [
            this.state.appliedFilters, "crm.lead", domain, stageName,
        ]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onTableRowClick(row) {
        if (!row?.id || !row?.model) return;
        this.actionService.doAction({
            type: "ir.actions.act_window", res_model: row.model, res_id: row.id,
            views: [[false, "form"]], target: "current",
        });
    }

    async onProductClick(row) {
        const action = await this.orm.call(MODEL, "get_entity_drilldown", [
            this.state.appliedFilters, "account.move.line",
            row.domain || [["product_id", "=", row.product_id]], row.name,
        ]);
        if (action?.type) this.actionService.doAction(action);
    }

    async onCustomerClick(row) {
        if (!row?.partner_id) return;
        this.actionService.doAction({
            type: "ir.actions.act_window", res_model: "res.partner", res_id: row.partner_id,
            views: [[false, "form"]], target: "current",
        });
    }

    async onAlertClick(alert) {
        if (!alert?.metric) return;
        const action = await this.orm.call(MODEL, "get_drilldown_action", [alert.metric, [], this.state.appliedFilters]);
        if (action?.type) this.actionService.doAction(action);
    }
}
