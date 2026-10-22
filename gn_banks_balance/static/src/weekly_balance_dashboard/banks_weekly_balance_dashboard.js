/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { BanksWeeklyBalanceFilterPanel } from "./filter_panel";
import { BanksWeeklyBalanceTable } from "./balance_table";
import { KpiCards } from "./kpi_cards";
import { CashflowChart } from "./cashflow_chart";
import { BalanceEvolutionChart } from "./balance_evolution_chart";
import { WaterfallCashflowChart } from "./waterfall_chart";
import { WeeklySummaryTable } from "./weekly_summary_table";
import { FinancialInsights } from "./financial_insights";
import { MovementDrilldownModal } from "./movement_drilldown_modal";
import { BanksWeeklyBalanceSkeleton } from "./skeleton";
import { BanksWeeklyBalanceEmptyState, DashboardStatePanel } from "./dashboard_state";
import { DashboardErrorState } from "./error_state";
import { ChartWeekSync } from "./chart_sync";
import { FinancialHealthTab } from "./financial_health_tab";
import { ExecutiveStickyBar } from "./executive_sticky_bar";
import {
    SmartAlertsPanel,
    RecommendationsPanel,
    HistoricalComparisonPanel,
} from "./financial_health_components";

const { DateTime } = luxon;

function defaultFilters(now) {
    return {
        company_id: false,
        year: now.year,
        month: String(now.month),
        journal_ids: [],
        compare_previous: false,
        use_custom_range: false,
        date_from: false,
        date_to: false,
        group_by: "week",
    };
}

export class BanksWeeklyBalanceDashboard extends Component {
    static template = "gn_banks_balance.BanksWeeklyBalanceDashboard";
    static components = {
        Layout,
        BanksWeeklyBalanceFilterPanel,
        BanksWeeklyBalanceTable,
        KpiCards,
        CashflowChart,
        BalanceEvolutionChart,
        WaterfallCashflowChart,
        WeeklySummaryTable,
        FinancialInsights,
        BanksWeeklyBalanceSkeleton,
        BanksWeeklyBalanceEmptyState,
        DashboardErrorState,
        FinancialHealthTab,
        ExecutiveStickyBar,
        SmartAlertsPanel,
        RecommendationsPanel,
        HistoricalComparisonPanel,
        DashboardStatePanel,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.rootRef = useRef("root");
        this.mainScrollRef = useRef("mainScroll");
        this.weekSync = new ChartWeekSync();
        this._contextJournalIds = null;
        this._healthCacheKey = null;
        this._onMainScroll = null;
        this._dataLoadToken = 0;
        this._healthLoadToken = 0;

        const now = DateTime.local();
        const initialFilters = defaultFilters(now);
        this.state = useState({
            loading: true,
            loadError: null,
            sidebarVisible: true,
            fullscreen: false,
            activeMainTab: "panel",
            filtersDirty: false,
            filterOptions: { journals: [], months: [], companies: [] },
            appliedFilters: { ...initialFilters },
            draftFilters: { ...initialFilters },
            data: {
                has_data: false,
                error_message: "",
                journal_columns: [],
                week_blocks: [],
                summary_lines: [],
                weeks: [],
                insights: [],
                kpis: {},
                charts: {},
            },
            healthLoading: false,
            healthLoadError: null,
            healthData: {
                has_data: false,
                error_message: "",
            },
            showStickyBar: false,
        });

        onWillStart(async () => {
            this._applyActionContext();
            await this.reloadFilterOptions();
            await this.loadData();
        });

        onMounted(() => {
            const el = this.mainScrollRef.el;
            if (!el) {
                return;
            }
            this._onMainScroll = () => {
                this.state.showStickyBar = el.scrollTop > 100;
            };
            el.addEventListener("scroll", this._onMainScroll, { passive: true });
        });

        onWillUnmount(() => {
            const el = this.mainScrollRef.el;
            if (this._onMainScroll && el) {
                el.removeEventListener("scroll", this._onMainScroll);
            }
        });
    }

    _applyActionContext() {
        const ctx = this.props.action?.context || {};
        const journalIds = ctx.dashboard_journal_ids;
        const companyId = ctx.dashboard_company_id;
        if (companyId) {
            this.state.draftFilters.company_id = companyId;
            this.state.appliedFilters.company_id = companyId;
        }
        if (Array.isArray(journalIds) && journalIds.length) {
            this.state.draftFilters.journal_ids = [...journalIds];
            this.state.appliedFilters.journal_ids = [...journalIds];
            this._contextJournalIds = [...journalIds];
        }
    }

    get display() {
        return { controlPanel: {} };
    }

    get title() {
        return _t("Balance semanal bancario");
    }

    get sidebarToggleTitle() {
        return this.state.sidebarVisible ? _t("Ocultar filtros") : _t("Mostrar filtros");
    }

    get refreshTitle() {
        return _t("Refrescar");
    }

    get fullscreenTitle() {
        return _t("Pantalla completa");
    }

    get shareTitle() {
        return _t("Compartir enlace");
    }

    get favoritesTitle() {
        return _t("Favoritos");
    }

    get exportXlsxTitle() {
        return _t("Exportar Excel");
    }

    get exportPdfTitle() {
        return _t("Exportar PDF");
    }

    get emptyStateMessage() {
        return _t(
            "No hay datos para los filtros seleccionados. Pruebe ampliar el rango o seleccionar otros bancos."
        );
    }

    get currencyId() {
        return this.state.data.currency?.id || this.state.data.currency_id || this.state.filterOptions.currency_id;
    }

    get currencySymbol() {
        return this.state.data.currency?.symbol || "$";
    }

    get generatedAtLabel() {
        const raw = this.state.data.generated_at;
        if (!raw) {
            return "";
        }
        const dt = DateTime.fromISO(raw);
        return dt.isValid ? dt.toLocaleString(DateTime.DATETIME_MED) : raw;
    }

    get waterfallData() {
        return {
            steps: this.state.data.waterfall || this.state.data.charts?.waterfall?.steps || [],
        };
    }

    get stickyMetrics() {
        const k = this.state.data.kpis || {};
        const h = this.state.healthData || {};
        const score = h.liquidity_score || {};
        const risk = h.liquidity_risk || {};
        return {
            finalBalance: k.final_balance ?? k.total_balance,
            netFlow: k.net_flow ?? k.total_net,
            score: score.score,
            scoreLabel: score.label || (score.score !== undefined ? String(score.score) : null),
            riskLabel: risk.label,
            riskLevel: risk.level,
        };
    }

    get executiveHealthSections() {
        const h = this.state.healthData || {};
        return {
            alerts: h.smart_alerts || [],
            recommendations: h.recommendations || [],
            historicalComparison: h.historical_comparison || null,
        };
    }

    get showExecutiveSections() {
        return Boolean(this.state.healthData?.has_data);
    }

    get canViewFinancialHealth() {
        return this.state.filterOptions?.can_view_financial_health !== false;
    }

    _trendFor(value) {
        if (value > 0) {
            return "up";
        }
        if (value < 0) {
            return "down";
        }
        return "flat";
    }

    _fmtDelta(cmp, key) {
        const v = cmp[key];
        if (v === undefined || v === null) {
            return "";
        }
        const sign = v >= 0 ? "+" : "";
        return `${sign}${this.fmt(v)} vs mes ant.`;
    }

    _fmtPct(v) {
        return v === null || v === undefined ? "N/A" : `${Number(v).toFixed(2)}%`;
    }

    get primaryKpiCards() {
        const k = this.state.data.kpis || {};
        if (k.final_balance === undefined && k.total_balance === undefined) {
            return [];
        }
        const cmp = k.compare || {};
        return [
            {
                id: "initial",
                label: _t("Saldo inicial"),
                value: this.fmt(k.initial_balance),
                subValue: _t("Al inicio del período"),
                icon: "fa-calendar-o",
                tone: "balance",
                trend: "flat",
            },
            {
                id: "final",
                label: _t("Saldo final"),
                value: this.fmt(k.final_balance ?? k.total_balance),
                subValue: this._fmtDelta(cmp, "total_balance_delta"),
                icon: "fa-university",
                tone: "balance",
                trend: this._trendFor((k.final_balance ?? 0) - (k.initial_balance ?? 0)),
            },
            {
                id: "inflows",
                label: _t("Total ingresos"),
                value: this.fmt(k.total_inflows),
                subValue: this._fmtDelta(cmp, "total_inflows_delta"),
                icon: "fa-arrow-down",
                tone: "success",
                trend: "up",
            },
            {
                id: "outflows",
                label: _t("Total salidas"),
                value: this.fmt(k.total_outflows),
                subValue: this._fmtDelta(cmp, "total_outflows_delta"),
                icon: "fa-arrow-up",
                tone: "danger",
                trend: "down",
            },
            {
                id: "net",
                label: _t("Flujo neto"),
                value: this.fmt(k.net_flow),
                subValue: this._fmtDelta(cmp, "net_flow_delta"),
                icon: "fa-exchange",
                tone: (k.net_flow ?? 0) >= 0 ? "success" : "warning",
                trend: this._trendFor(k.net_flow),
            },
        ];
    }

    get secondaryKpiCards() {
        const k = this.state.data.kpis || {};
        const mainBank = k.main_bank || k.top_bank || {};
        const critical = k.critical_week || {};
        return [
            {
                id: "critical",
                label: _t("Semana crítica"),
                value: this.fmt(critical.value ?? critical.final_balance),
                subValue: critical.label || "",
                icon: "fa-exclamation-triangle",
                tone: "warning",
                trend: "down",
            },
            {
                id: "main_bank",
                label: _t("Banco principal"),
                value: this.fmt(mainBank.value ?? mainBank.amount),
                subValue: mainBank.name || "",
                icon: "fa-trophy",
                tone: "neutral",
                trend: "flat",
            },
            {
                id: "ratio",
                label: _t("Ratio ing./sal."),
                value: this._fmtPct(k.income_expense_ratio),
                subValue: _t("Cobertura"),
                icon: "fa-percent",
                tone: "neutral",
                trend: (k.income_expense_ratio ?? 0) >= 100 ? "up" : "down",
            },
            {
                id: "avg_liq",
                label: _t("Liquidez prom."),
                value: this.fmt(k.average_liquidity ?? k.average_weekly_liquidity),
                subValue: _t("Saldo final prom."),
                icon: "fa-line-chart",
                tone: "balance",
                trend: "flat",
            },
            {
                id: "variation",
                label: _t("Variación período"),
                value: this._fmtPct(k.variation_period ?? k.variation_previous_period),
                subValue: _t("Final vs inicial"),
                icon: "fa-area-chart",
                tone: "neutral",
                trend: this._trendFor(k.variation_period ?? k.variation_previous_period),
            },
        ];
    }

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.currencyId });
    }

    _cloneFilters(f) {
        return { ...f, journal_ids: [...(f.journal_ids || [])] };
    }

    _filtersEqual(a, b) {
        const keys = Object.keys(a);
        for (const k of keys) {
            if (k === "journal_ids") {
                const ja = [...(a.journal_ids || [])].sort();
                const jb = [...(b.journal_ids || [])].sort();
                if (ja.length !== jb.length || ja.some((v, i) => v !== jb[i])) {
                    return false;
                }
            } else if (a[k] !== b[k]) {
                return false;
            }
        }
        return true;
    }

    async reloadFilterOptions() {
        const opts = await this.orm.call(
            "banks.weekly.balance.dashboard",
            "get_filter_options",
            [],
            { company_id: this.state.draftFilters.company_id || false }
        );
        this.state.filterOptions = opts;
        if (opts.can_view_financial_health === false && this.state.activeMainTab === "health") {
            this.state.activeMainTab = "panel";
        }
        if (!this.state.draftFilters.company_id) {
            this.state.draftFilters.company_id = opts.company_id;
            this.state.appliedFilters.company_id = opts.company_id;
        }
        if (this._contextJournalIds?.length) {
            this.state.draftFilters.journal_ids = [...this._contextJournalIds];
            this.state.appliedFilters.journal_ids = [...this._contextJournalIds];
        } else if (!this.state.draftFilters.journal_ids.length && opts.journals?.length) {
            const ids = opts.journals.map((j) => j.id);
            this.state.draftFilters.journal_ids = ids;
            this.state.appliedFilters.journal_ids = [...ids];
        }
    }

    _healthCacheKeyFromFilters() {
        return JSON.stringify(this._exportFilters());
    }

    async loadFinancialHealth(force = false) {
        const cacheKey = this._healthCacheKeyFromFilters();
        if (!force && this._healthCacheKey === cacheKey && this.state.healthData?.has_data) {
            return;
        }
        const token = ++this._healthLoadToken;
        this.state.healthLoading = true;
        this.state.healthLoadError = null;
        try {
            const result = await this.orm.call(
                "banks.weekly.balance.dashboard",
                "get_bank_financial_health_data",
                [this._exportFilters()]
            );
            if (token !== this._healthLoadToken) {
                return;
            }
            this.state.healthData = result;
            this._healthCacheKey = cacheKey;
        } catch (e) {
            if (token !== this._healthLoadToken) {
                return;
            }
            console.error("Financial health dashboard error:", e);
            this.state.healthLoadError = e.message || _t("Error al cargar salud financiera.");
            this.state.healthData = {
                has_data: false,
                error_message: this.state.healthLoadError,
            };
        } finally {
            if (token === this._healthLoadToken) {
                this.state.healthLoading = false;
            }
        }
    }

    async loadData() {
        const token = ++this._dataLoadToken;
        this._healthLoadToken++;
        this.state.loading = true;
        this.state.loadError = null;
        this.weekSync.clear();
        this._healthCacheKey = null;
        const payload = { ...this.state.appliedFilters };
        if (!payload.use_custom_range) {
            payload.date_from = false;
            payload.date_to = false;
        }
        let result = null;
        let error = null;
        try {
            result = await this.orm.call(
                "banks.weekly.balance.dashboard",
                "get_bank_weekly_dashboard_data",
                [payload]
            );
        } catch (e) {
            error = e;
        }
        // Discard stale responses (newer loadData call already in flight).
        if (token !== this._dataLoadToken) {
            return;
        }
        if (error) {
            console.error("Weekly balance dashboard error:", error);
            this.state.loadError = error.message || _t("Error al cargar el informe.");
            this.state.data = {
                has_data: false,
                error_message: this.state.loadError,
                journal_columns: [],
                week_blocks: [],
                summary_lines: [],
                weeks: [],
                insights: [],
                kpis: {},
                charts: {},
            };
        } else {
            this.state.data = result;
            if (!this.state.data.has_data && this.state.data.error_message) {
                this.state.loadError = null;
            }
        }
        // Always release the loading flag before chaining the health refresh
        // so the panel renders even if the background request hangs.
        this.state.loading = false;
        if (!error && this.state.data.has_data && this.canViewFinancialHealth) {
            if (this.state.activeMainTab === "health") {
                await this.loadFinancialHealth(true);
            } else {
                void this.loadFinancialHealth();
            }
        }
    }

    onDraftFiltersChanged(partial) {
        Object.assign(this.state.draftFilters, partial);
        if (partial.journal_ids !== undefined) {
            this.state.draftFilters.journal_ids = [...partial.journal_ids];
        }
        this.state.filtersDirty = !this._filtersEqual(
            this.state.draftFilters,
            this.state.appliedFilters
        );
    }

    async onApplyFilters() {
        if (!this.state.draftFilters.journal_ids?.length) {
            this.notification.add(_t("Seleccione al menos un banco."), { type: "warning" });
            return;
        }
        if (this.state.draftFilters.company_id !== this.state.appliedFilters.company_id) {
            await this.reloadFilterOptions();
        }
        this.state.appliedFilters = this._cloneFilters(this.state.draftFilters);
        this.state.filtersDirty = false;
        await this.loadData();
    }

    async onClearFilters() {
        const now = DateTime.local();
        const cleared = defaultFilters(now);
        cleared.company_id = this.state.filterOptions.company_id;
        cleared.journal_ids = (this.state.filterOptions.journals || []).map((j) => j.id);
        this.state.draftFilters = { ...cleared };
        this.state.appliedFilters = this._cloneFilters(cleared);
        this.state.filtersDirty = false;
        await this.loadData();
    }

    async setMainTab(tab) {
        if (tab === "health" && !this.canViewFinancialHealth) {
            return;
        }
        this.state.activeMainTab = tab;
        if (tab === "health" && this.state.data.has_data && !this.state.healthLoading) {
            await this.loadFinancialHealth();
        }
    }

    toggleSidebar() {
        this.state.sidebarVisible = !this.state.sidebarVisible;
    }

    async onRefresh() {
        await this.loadData();
        if (this.state.activeMainTab === "health") {
            await this.loadFinancialHealth(true);
        }
        this.notification.add(_t("Informe actualizado."), { type: "success" });
    }

    async onRetryHealth() {
        await this.loadFinancialHealth(true);
    }

    toggleFullscreen() {
        const el = this.rootRef.el;
        if (!el) {
            return;
        }
        if (!document.fullscreenElement) {
            el.requestFullscreen?.();
            this.state.fullscreen = true;
        } else {
            document.exitFullscreen?.();
            this.state.fullscreen = false;
        }
    }

    async onShare() {
        const url = await this.orm.call("banks.weekly.balance.dashboard", "get_share_url", []);
        try {
            await navigator.clipboard.writeText(url);
            this.notification.add(_t("Enlace copiado al portapapeles."), { type: "info" });
        } catch {
            this.notification.add(url, { type: "info", sticky: true });
        }
    }

    onFavorite() {
        this.notification.add(
            _t("Use el menú de favoritos de Odoo (★) en la barra superior para guardar esta vista."),
            { type: "info" }
        );
    }

    _exportFilters() {
        const f = { ...this.state.appliedFilters };
        if (!f.use_custom_range) {
            f.date_from = false;
            f.date_to = false;
        }
        return f;
    }

    async onExportXlsx() {
        const action = await this.orm.call(
            "banks.weekly.balance.dashboard",
            "get_export_xlsx_action",
            [this._exportFilters()]
        );
        if (action?.type) {
            this.actionService.doAction(action);
        }
    }

    async onExportPdf() {
        const action = await this.orm.call(
            "banks.weekly.balance.dashboard",
            "get_export_pdf_action",
            [this._exportFilters()]
        );
        if (action?.type) {
            this.actionService.doAction(action);
        }
    }

    async _openDrilldownAction(ctx) {
        const action = await this.orm.call(
            "banks.weekly.balance.dashboard",
            "get_drilldown_action",
            [this._exportFilters(), ctx]
        );
        if (action?.type) {
            action.views = action.views || [[false, "list"], [false, "form"]];
            this.actionService.doAction(action);
        }
    }

    async onDrilldown(ctx) {
        try {
            const preview = await this.orm.call(
                "banks.weekly.balance.dashboard",
                "get_drilldown_preview",
                [this._exportFilters(), ctx, 50]
            );
            const metricLabels = {
                opening: _t("Saldo inicial"),
                closing: _t("Saldo final"),
                inflow: _t("Ingresos"),
                outflow: _t("Salidas"),
                net: _t("Flujo neto"),
            };
            const metric = ctx.metric || ctx.row_type || "inflow";
            this.dialog.add(MovementDrilldownModal, {
                title: metricLabels[metric] || _t("Detalle de movimientos"),
                lines: preview.lines || [],
                count: preview.count || 0,
                currencyId: this.currencyId,
                onOpenOdoo: () => this._openDrilldownAction(ctx),
            });
        } catch (e) {
            this.notification.add(e.message || _t("No se pudo abrir el detalle."), {
                type: "warning",
            });
        }
    }

    async onStatementDrilldown(ctx) {
        try {
            const action = await this.orm.call(
                "banks.weekly.balance.dashboard",
                "get_bank_statement_action",
                [this._exportFilters(), ctx]
            );
            if (action?.type) {
                this.actionService.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message || _t("Extracto no disponible."), {
                type: "warning",
            });
        }
    }
}

registry.category("actions").add(
    "gn_banks_balance_weekly_dashboard",
    BanksWeeklyBalanceDashboard
);
registry.category("actions").add(
    "gn_banks_weekly_balance_dashboard",
    BanksWeeklyBalanceDashboard
);
