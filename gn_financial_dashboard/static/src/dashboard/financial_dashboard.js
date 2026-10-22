/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { FinancialChart } from "./financial_chart";
import { KpiCard } from "./components/kpi_card";
import { RankingTable } from "./components/ranking_table";
import { AgingPanel } from "./components/aging_panel";
import { AnalysisPanel } from "./components/analysis_panel";
import { AccountDetailDialog } from "./components/account_detail_dialog";
import { HealthBreakdown } from "./components/health_breakdown";
import { CategoryScores } from "./components/category_scores";
import { RiskGauge } from "./components/risk_gauge";
import { RecommendationsPanel } from "./components/recommendations_panel";
import { DecisionCenter } from "./components/decision_center";
import { InfoTip } from "./components/info_tip";
import { VariancePanel } from "./components/variance_panel";
import { CustomKpiCard } from "./components/custom_kpi_card";
import { GoalsPanel } from "./components/goals_panel";
import { IntelligenceTable } from "./components/intelligence_table";
import { AlertList } from "./components/alert_list";
import { DecisionHub } from "./components/decision_hub";
import { ChatPanel } from "./components/chat_panel";
import { IndicatorGauge } from "./components/indicator_gauge";
import { PALETTE, formatMoney, compactNumber, formatNumber, formatDate, formatDateTime } from "./chart_helpers";

export class GnFinancialDashboard extends Component {
    static template = "gn_financial_dashboard.Dashboard";
    static components = {
        Layout, FinancialChart, KpiCard, RankingTable, AgingPanel, AnalysisPanel,
        HealthBreakdown, CategoryScores, RiskGauge, RecommendationsPanel, DecisionCenter,
        InfoTip, VariancePanel, CustomKpiCard, GoalsPanel, IntelligenceTable,
        AlertList, DecisionHub, ChatPanel, IndicatorGauge,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            loading: true,
            loadError: null,
            lastUpdate: false,
            activeTab: "overview",
            tabLoaded: { overview: false },
            tabLoading: false,
            filterOptions: {
                journals: [], companies: [], currency: {},
                branches: [], analytic_plans: [], projects: [],
                dimensions: { branch: false, analytic: false, project: false },
            },
            filters: {
                company_id: false,
                date_from: false,
                date_to: false,
                journal_ids: [],
                target_move: "posted",
                comparison: "previous_period",
                period_length: 30,
                // Dimensiones extra (multiseleccion).
                branch_ids: [],
                analytic_account_ids: [],
                project_ids: [],
            },
            data: { has_data: false, kpis: {}, health: {} },
            // Simulador what-if (% de cambio aplicados sobre la base anual).
            sim: { income: 0, cogs: 0, expenses: 0 },
            // V20 Fase 2: KPIs personalizados, objetivos y workspaces.
            customKpis: { items: [], can_configure: false, currency: {} },
            goals: { goals: [], summary: { total: 0, attained: 0, in_progress: 0, overdue: 0 } },
            workspaces: { list: [], active_id: false },
            workspaceEditor: { visible: false, name: "", shared: false, isDefault: false, id: false },
            // V20 Fase 3: Inteligencia de entidades (productos, clientes,
            // proveedores). Cada sub-pestaña carga su payload bajo demanda.
            intelSubtab: "products",
            intelLoaded: { products: false, customers: false, suppliers: false },
            intelLoading: false,
            intelProducts: null,
            intelCustomers: null,
            intelSuppliers: null,
            // V20 Fase 4: Dashboards por área (Comercial / Compras /
            // Inventario / paneles personalizados via hook).
            areaSubtab: "sales",
            areaLoaded: {},
            areaLoading: false,
            areaPayloads: {},
            // V20 Fase 5: Predicciones (forecast + score + escenarios +
            // benchmark sectorial).
            predictSubtab: "forecast",
            predictLoading: false,
            predictData: null,
            predictHorizon: 6,
            predictHistoryMonths: 24,
            predictBenchmarkSector: "hospital",
            scenarioInputs: {
                price_delta_pct: 0,
                volume_delta_pct: 0,
                cost_delta_pct: 0,
                opex_delta_pct: 0,
                dso_delta_days: 0,
                dpo_delta_days: 0,
                capex: 0,
            },
            scenarioResult: null,
            scenarioRunning: false,
            // V20 Fase 6: Decisiones e IA (alertas, centro, asistente).
            decisionsSubtab: "center",
            decisionsLoading: false,
            decisionsData: null,
            alertsData: null,
            chatHistory: [],
            chatLoading: false,
            askSuggestions: [
                _t("¿Cómo está la salud del negocio?"),
                _t("¿Cuánto tengo en caja?"),
                _t("Mostrar alertas urgentes"),
                _t("Pronóstico para los próximos meses"),
                _t("¿Qué clientes son los más rentables?"),
                _t("¿Qué debo hacer ahora?"),
            ],
            // Pestaña 'Indicadores': gauges semicirculares estilo
            // 'punto de referencia' (margenes, liquidez, DSO/DPO...).
            indicatorsData: null,
            agingSort: {
                receivable: { key: "pending", dir: "desc" },
                payable: { key: "pending", dir: "desc" },
            },
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await this.loadOverview();
            await this.loadWorkspaces();
        });
    }

    // ----------------------------------------------------------------
    // Pestañas (navegación por dominio con carga perezosa)
    // ----------------------------------------------------------------
    get _tabDefs() {
        return [
            { key: "overview", label: _t("Resumen"), icon: "fa-tachometer", sections: [] },
            { key: "executive", label: _t("Ejecutivo"), icon: "fa-briefcase", sections: [], always: true, fixedSeq: 0 },
            { key: "profitability", label: _t("Rentabilidad"), icon: "fa-line-chart", sections: ["profitability", "expense_ranking"] },
            { key: "liquidity", label: _t("Liquidez"), icon: "fa-tint", sections: ["liquidity"] },
            { key: "aging", label: _t("Cartera"), icon: "fa-clock-o", sections: ["aging", "partner_ranking"] },
            { key: "cashflow", label: _t("Flujo de caja"), icon: "fa-exchange", sections: ["cashflow"] },
            { key: "planning", label: _t("Planeación"), icon: "fa-bullseye", sections: [], always: true, fixedSeq: 65 },
            { key: "watch", label: _t("Vigilancia"), icon: "fa-binoculars", sections: [], always: true, fixedSeq: 66 },
            { key: "mykpis", label: _t("Mis KPIs"), icon: "fa-star-o", sections: [], always: true, fixedSeq: 67 },
            { key: "indicators", label: _t("Indicadores"), icon: "fa-tachometer", sections: [], always: true, fixedSeq: 64 },
            { key: "intelligence", label: _t("Inteligencia"), icon: "fa-users", sections: [], always: true, fixedSeq: 68 },
            { key: "areas", label: _t("Áreas"), icon: "fa-th-large", sections: [], always: true, fixedSeq: 69 },
            { key: "predictions", label: _t("Predicciones"), icon: "fa-line-chart", sections: [], always: true, fixedSeq: 67 },
            { key: "decisions", label: _t("Decisiones"), icon: "fa-bolt", sections: [], always: true, fixedSeq: 68 },
            { key: "diagnostics", label: _t("Diagnóstico"), icon: "fa-lightbulb-o", sections: ["analysis", "data_quality"] },
        ];
    }

    get _tabLoaders() {
        return {
            profitability: { method: "get_profitability_data", merge: (d, r) => Object.assign(d, r) },
            liquidity: {
                method: "get_liquidity_data",
                merge: (d, r) => {
                    if (!d.kpis) {
                        d.kpis = {};
                    }
                    Object.assign(d.kpis, r.kpis || {});
                    d.liquidity_compare = r.compare;
                },
                after: async (self) => {
                    if (!self.state.data.cashflow) {
                        const cf = await self.orm.call(
                            "gn.financial.dashboard",
                            "get_cashflow_data",
                            [self._filtersPayload()]
                        );
                        self.state.data.cashflow = cf;
                    }
                },
            },
            aging: { method: "get_aging_data", merge: (d, r) => Object.assign(d, r) },
            cashflow: { method: "get_cashflow_data", merge: (d, r) => { d.cashflow = r; } },
            executive: { method: "get_executive_data", merge: (d, r) => { d.executive = r; } },
            planning: { method: "get_planning_data", merge: (d, r) => { d.planning = r; } },
            watch: { method: "get_watch_data", merge: (d, r) => { d.watch = r; } },
            // "Mis KPIs" carga los KPIs personalizados + los objetivos
            // estratégicos en una sola pestaña (ambos dependen de los filtros).
            mykpis: {
                method: "get_custom_kpis",
                merge: (_d, r, self) => {
                    self.state.customKpis = r;
                },
                after: async (self) => { await self.loadGoals(); },
            },
            // Indicadores estilo "punto de referencia" (gauges).
            indicators: {
                method: "get_indicators_data",
                merge: (_d, r, self) => {
                    self.state.indicatorsData = r;
                },
            },
            // Inteligencia: carga la sub-pestaña activa por demanda.
            intelligence: {
                method: null,
                merge: () => {},
                after: async (self) => { await self.ensureIntelLoaded(self.state.intelSubtab); },
            },
            // Predicciones: forecast + score + escenarios + benchmark.
            predictions: {
                method: null,
                merge: () => {},
                after: async (self) => { await self.ensurePredictionsLoaded(); },
            },
            // Decisiones e IA: agrupa Centro / Alertas / Asistente.
            decisions: {
                method: null,
                merge: () => {},
                after: async (self) => { await self.ensureDecisionsLoaded(); },
            },
            // Áreas: misma estrategia con sub-tabs condicionales según
            // capacidades del backend (ventas, compras, inventario, custom).
            areas: {
                method: null,
                merge: () => {},
                after: async (self) => {
                    const first = self.availableAreaSubtabs[0]?.key;
                    if (first && !self.state.areaSubtab) {
                        self.state.areaSubtab = first;
                    }
                    if (self.state.areaSubtab) {
                        await self.ensureAreaLoaded(self.state.areaSubtab);
                    }
                },
            },
            diagnostics: { method: "get_diagnostics_data", merge: (d, r) => Object.assign(d, r) },
        };
    }

    get tabs() {
        const cfg = this.state.data.config?.sections || [];
        const visMap = {};
        const seqMap = {};
        for (const s of cfg) {
            visMap[s.key] = s.visible;
            seqMap[s.key] = s.sequence;
        }
        const result = [];
        for (const t of this._tabDefs) {
            if (t.key === "overview") {
                result.push({ ...t, seq: -1 });
                continue;
            }
            // Pestaña Áreas: solo se muestra si al menos una área (ventas,
            // compras, inventario o un panel personalizado) está disponible.
            if (t.key === "areas" && !this.hasAnyArea) {
                continue;
            }
            if (t.always) {
                // Pestaña independiente de secciones (p.ej. Planeación,
                // Vigilancia): se ubican antes de Diagnóstico (secciones 70/80).
                result.push({ ...t, seq: t.fixedSeq ?? 65 });
                continue;
            }
            const visible = t.sections.filter((k) => visMap[k] !== false);
            if (!visible.length) {
                continue;
            }
            const seq = Math.min(...t.sections.map((k) => seqMap[k] ?? 999));
            result.push({ ...t, seq });
        }
        result.sort((a, b) => a.seq - b.seq);
        return result;
    }

    isSectionVisible(key) {
        const cfg = this.state.data.config?.sections || [];
        const s = cfg.find((x) => x.key === key);
        return s ? s.visible : true;
    }

    async selectTab(key) {
        this.state.activeTab = key;
        await this.ensureTabLoaded(key);
    }

    // Construye el payload de filtros para los RPC: clona arrays mutables
    // (journal_ids y dimensiones) para evitar enviar referencias reactivas.
    _filtersPayload() {
        return {
            ...this.state.filters,
            journal_ids: [...this.state.filters.journal_ids],
            branch_ids: [...this.state.filters.branch_ids],
            analytic_account_ids: [...this.state.filters.analytic_account_ids],
            project_ids: [...this.state.filters.project_ids],
        };
    }

    async ensureTabLoaded(key) {
        const loader = this._tabLoaders[key];
        if (!loader || this.state.tabLoaded[key]) {
            return;
        }
        this.state.tabLoading = true;
        try {
            if (loader.method) {
                const result = await this.orm.call(
                    "gn.financial.dashboard",
                    loader.method,
                    [this._filtersPayload()]
                );
                loader.merge(this.state.data, result, this);
            }
            this.state.tabLoaded[key] = true;
            if (typeof loader.after === "function") {
                await loader.after(this);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        } finally {
            this.state.tabLoading = false;
        }
    }

    get display() {
        return { controlPanel: {} };
    }

    get title() {
        return _t("Tablero financiero");
    }

    get currencySymbol() {
        return this.state.data.currency?.symbol || this.state.filterOptions.currency?.symbol || "$";
    }

    fmt(value) {
        return formatMoney(value, this.currencySymbol);
    }

    // Helpers de formato unificado expuestos al template (QWeb).
    // - fmtNum: separador de miles "," y punto decimal (locale en-US).
    // - fmtDate: fecha en dd/mm/yyyy desde ISO o Date.
    // - fmtDateTime: fecha+hora en dd/mm/yyyy HH:mm desde ISO o Date.
    fmtNum(value, decimals = 2) {
        return formatNumber(value, decimals);
    }
    fmtDate(value) {
        return formatDate(value);
    }
    fmtDateTime(value) {
        return formatDateTime(value);
    }

    async loadFilterOptions() {
        const opts = await this.orm.call(
            "gn.financial.dashboard",
            "get_filter_options",
            [],
            { company_id: this.state.filters.company_id || false }
        );
        this.state.filterOptions = opts;
        if (!this.state.filters.company_id) {
            this.state.filters.company_id = opts.company_id;
        }
        if (!this.state.filters.date_from) {
            this.state.filters.date_from = opts.date_from;
            this.state.filters.date_to = opts.date_to;
        }
    }

    async loadOverview() {
        this.state.loading = true;
        this.state.loadError = null;
        try {
            this.state.data = await this.orm.call(
                "gn.financial.dashboard",
                "get_overview_data",
                [this._filtersPayload()]
            );
            this.state.lastUpdate = luxon.DateTime.now().toFormat("dd/MM/yyyy HH:mm");
            // Invalida el caché de pestañas (los filtros pudieron cambiar).
            this.state.tabLoaded = { overview: true };
        } catch (e) {
            this.state.loadError = e.message?.data?.message || e.message || _t("Error al cargar el tablero.");
            this.state.data = { has_data: false, kpis: {}, health: {} };
        } finally {
            this.state.loading = false;
        }
        // Recarga la pestaña activa (si no es el Resumen) con los nuevos filtros.
        if (!this.state.loadError && this.state.activeTab !== "overview") {
            await this.ensureTabLoaded(this.state.activeTab);
        }
    }

    async onApply() {
        await this.loadOverview();
        // Si "Mis KPIs" está activa, recargamos también goals (forman parte
        // del mismo bloque visual y dependen del rango aplicado).
        if (this.state.activeTab === "mykpis" && this.state.tabLoaded["mykpis"]) {
            await this.loadGoals();
        }
    }

    async onCompanyChange(ev) {
        this.state.filters.company_id = Number(ev.target.value) || false;
        this.state.filters.journal_ids = [];
        // Los catalogos de dimensiones dependen de la compañia: limpiamos
        // selecciones para evitar mostrar IDs de otra empresa.
        this.state.filters.branch_ids = [];
        this.state.filters.analytic_account_ids = [];
        this.state.filters.project_ids = [];
        await this.loadFilterOptions();
        await this.loadOverview();
    }

    onDateFromChange(ev) {
        this.state.filters.date_from = ev.target.value || false;
    }

    onDateToChange(ev) {
        this.state.filters.date_to = ev.target.value || false;
    }

    onTargetMoveChange(ev) {
        this.state.filters.target_move = ev.target.value;
    }

    onComparisonChange(ev) {
        this.state.filters.comparison = ev.target.value;
    }

    onPeriodLengthChange(ev) {
        this.state.filters.period_length = Number(ev.target.value) || 30;
    }

    onToggleJournal(journalId) {
        const ids = this.state.filters.journal_ids;
        const idx = ids.indexOf(journalId);
        if (idx >= 0) {
            ids.splice(idx, 1);
        } else {
            ids.push(journalId);
        }
    }

    isJournalSelected(journalId) {
        return this.state.filters.journal_ids.includes(journalId);
    }

    // ----------------------------------------------------------------
    // Dimensiones (sucursal, centro de costo/analitica, proyecto)
    // ----------------------------------------------------------------
    _toggleId(list, id) {
        const idx = list.indexOf(id);
        if (idx >= 0) {
            list.splice(idx, 1);
        } else {
            list.push(id);
        }
    }

    onToggleBranch(id) { this._toggleId(this.state.filters.branch_ids, id); }
    isBranchSelected(id) { return this.state.filters.branch_ids.includes(id); }

    onToggleAnalytic(id) { this._toggleId(this.state.filters.analytic_account_ids, id); }
    isAnalyticSelected(id) { return this.state.filters.analytic_account_ids.includes(id); }

    onToggleProject(id) { this._toggleId(this.state.filters.project_ids, id); }
    isProjectSelected(id) { return this.state.filters.project_ids.includes(id); }

    get hasBranchDim() {
        return this.state.filterOptions.dimensions?.branch && (this.state.filterOptions.branches?.length || 0) > 0;
    }
    get hasAnalyticDim() {
        return this.state.filterOptions.dimensions?.analytic && (this.state.filterOptions.analytic_plans?.length || 0) > 0;
    }
    get hasProjectDim() {
        return this.state.filterOptions.dimensions?.project && (this.state.filterOptions.projects?.length || 0) > 0;
    }
    get branchSummary() {
        const n = this.state.filters.branch_ids.length;
        return n ? `${n} seleccionado(s)` : _t("Todas");
    }
    get analyticSummary() {
        const n = this.state.filters.analytic_account_ids.length;
        return n ? `${n} seleccionado(s)` : _t("Todos");
    }
    get projectSummary() {
        const n = this.state.filters.project_ids.length;
        return n ? `${n} seleccionado(s)` : _t("Todos");
    }

    async onRefresh() {
        await this.loadOverview();
        this.notification.add(_t("Tablero actualizado."), { type: "success" });
    }

    async openBiReport(reportType) {
        if (!this.state.data.has_bi_reports) {
            this.notification.add(
                _t("El módulo de Reportes Financieros (BI) no está instalado."),
                { type: "warning" }
            );
            return;
        }
        try {
            const action = await this.orm.call(
                "gn.financial.dashboard",
                "open_bi_report",
                [reportType]
            );
            if (action?.type) {
                this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    // ----------------------------------------------------------------
    // KPI cards
    // ----------------------------------------------------------------
    _delta(key) {
        const cmp = this.state.data.compare;
        if (!cmp?.kpis) {
            return null;
        }
        const cur = this.state.data.kpis[key] ?? 0;
        const prev = cmp.kpis[key] ?? 0;
        const absVal = cur - prev;
        if (!prev) {
            // Sin base previa: aún reportamos la variación absoluta.
            return { pct: null, absVal, dir: absVal >= 0 ? "up" : "down" };
        }
        const pct = (absVal / Math.abs(prev)) * 100;
        return { pct, absVal, dir: absVal >= 0 ? "up" : "down" };
    }

    _card(key, label, icon, tone, { isPct = false, invertTrend = false } = {}) {
        const value = this.state.data.kpis[key] ?? 0;
        const delta = this._delta(key);
        // dir = dirección real del cambio (flecha); trend = juicio de valor
        // (verde favorable / rojo desfavorable). En gastos, por pagar y cartera
        // vencida una baja es favorable (invertTrend=true).
        let trend = "flat";
        let dir = "up";
        let deltaPct = "";
        let deltaAbs = "";
        if (delta) {
            dir = delta.dir;
            const increased = delta.absVal >= 0;
            trend = (increased !== invertTrend) ? "up" : "down";
            if (delta.pct !== null) {
                deltaPct = `${delta.pct >= 0 ? "+" : ""}${delta.pct.toFixed(1)}%`;
            }
            deltaAbs = isPct
                ? `${delta.absVal >= 0 ? "+" : ""}${delta.absVal.toFixed(1)} pp`
                : `${delta.absVal >= 0 ? "+" : ""}${this.fmt(delta.absVal)}`;
        }
        return {
            id: key,
            key,
            label,
            icon,
            tone,
            value: isPct ? `${Number(value).toFixed(1)}%` : this.fmt(value),
            delta: deltaPct,
            deltaAbs,
            dir,
            trend,
            meta: this.state.data.kpi_meta?.[key] || null,
            trendInfo: this.state.data.trends?.[key] || null,
        };
    }

    get overviewCards() {
        return [
            this._card("revenue", _t("Ingresos"), "fa-arrow-down", "success"),
            this._card("net_profit", _t("Utilidad neta"), "fa-line-chart", "balance"),
            this._card("net_margin", _t("Margen neto"), "fa-percent", "neutral", { isPct: true }),
            this._card("closing_bank", _t("Saldo bancario"), "fa-university", "balance"),
            this._card("receivables", _t("Por cobrar"), "fa-hand-holding-usd", "neutral"),
            this._card("payables", _t("Por pagar"), "fa-file-invoice", "danger", { invertTrend: true }),
        ];
    }

    get profitCards() {
        return [
            this._card("revenue", _t("Ingresos"), "fa-arrow-down", "success"),
            this._card("gross_profit", _t("Utilidad bruta"), "fa-cubes", "balance"),
            this._card("expenses", _t("Gastos"), "fa-arrow-up", "danger", { invertTrend: true }),
            this._card("net_profit", _t("Utilidad neta"), "fa-line-chart", "balance"),
            this._card("net_margin", _t("Margen neto"), "fa-percent", "neutral", { isPct: true }),
        ];
    }

    get liquidityCards() {
        return [
            this._card("cash_surplus", _t("Flujo de caja"), "fa-exchange", "success"),
            this._card("closing_bank", _t("Saldo bancario"), "fa-university", "balance"),
            this._card("receivables", _t("Por cobrar"), "fa-hand-holding-usd", "neutral"),
            this._card("payables", _t("Por pagar"), "fa-file-invoice", "danger", { invertTrend: true }),
            this._card("working_capital", _t("Capital de trabajo"), "fa-balance-scale", "balance"),
        ];
    }

    // ----------------------------------------------------------------
    // Chart configs
    // ----------------------------------------------------------------
    _moneyTooltip() {
        const symbol = this.currencySymbol;
        return {
            callbacks: {
                label: (ctx) => `${ctx.dataset.label || ""}: ${formatMoney(ctx.parsed.y ?? ctx.parsed, symbol)}`,
            },
        };
    }

    get monthlyConfig() {
        const s = this.state.data.monthly_series || { labels: [], income: [], expense: [], net: [] };
        return {
            type: "bar",
            data: {
                labels: s.labels,
                datasets: [
                    { label: _t("Ingresos"), data: s.income, backgroundColor: PALETTE.income, borderColor: PALETTE.incomeBorder, borderWidth: 1, order: 2 },
                    { label: _t("Gastos"), data: s.expense, backgroundColor: PALETTE.expense, borderColor: PALETTE.expenseBorder, borderWidth: 1, order: 3 },
                    { label: _t("Utilidad neta"), data: s.net, type: "line", borderColor: PALETTE.net, backgroundColor: "transparent", borderWidth: 3, tension: 0.25, pointRadius: 3, order: 1 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { position: "top" }, tooltip: this._moneyTooltip() },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }

    get monthlyFingerprint() {
        return JSON.stringify(this.state.data.monthly_series || {});
    }

    get waterfallConfig() {
        const steps = this.state.data.waterfall || [];
        const ranges = [];
        const colors = [];
        let running = 0;
        for (const step of steps) {
            if (step.type === "total" || step.type === "subtotal") {
                ranges.push([0, step.value]);
                running = step.value;
                colors.push(step.type === "total" ? PALETTE.total : PALETTE.subtotal);
            } else {
                ranges.push([running + step.value, running]);
                running = running + step.value;
                colors.push(PALETTE.down);
            }
        }
        return {
            type: "bar",
            data: {
                labels: steps.map((s) => s.label),
                datasets: [{
                    label: _t("Resultado"),
                    data: ranges,
                    backgroundColor: colors,
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const step = steps[ctx.dataIndex];
                                return `${step.label}: ${formatMoney(step.value, this.currencySymbol)}`;
                            },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }

    get waterfallFingerprint() {
        return JSON.stringify(this.state.data.waterfall || []);
    }

    get expenseConfig() {
        const b = this.state.data.expense_breakdown || { labels: [], values: [] };
        return {
            type: "doughnut",
            data: {
                labels: b.labels,
                datasets: [{ data: b.values, backgroundColor: PALETTE.donut, borderWidth: 1 }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${formatMoney(ctx.parsed, this.currencySymbol)}`,
                        },
                    },
                },
            },
        };
    }

    get expenseFingerprint() {
        return JSON.stringify(this.state.data.expense_breakdown || {});
    }

    get hasExpenseData() {
        return (this.state.data.expense_breakdown?.values || []).some((v) => Math.abs(v) > 0.009);
    }

    _agingConfig(side) {
        const a = this.state.data.aging?.[side];
        if (!a) {
            return null;
        }
        return {
            type: "bar",
            data: {
                labels: a.labels,
                datasets: [{
                    label: side === "receivable" ? _t("Por cobrar") : _t("Por pagar"),
                    data: a.values,
                    backgroundColor: a.colors || (side === "receivable" ? PALETTE.income : PALETTE.expense),
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: this._moneyTooltip() },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }

    get receivableAgingConfig() {
        return this._agingConfig("receivable");
    }

    get payableAgingConfig() {
        return this._agingConfig("payable");
    }

    get agingFingerprint() {
        return JSON.stringify(this.state.data.aging || {});
    }

    // ----------------------------------------------------------------
    // Rankings (gastos / clientes / proveedores)
    // ----------------------------------------------------------------
    _deltaCell(deltaPct) {
        if (deltaPct === null || deltaPct === undefined) {
            return { text: "—", cls: "text-end text-muted" };
        }
        const cls = deltaPct > 0 ? "text-danger" : "text-success";
        return { text: `${deltaPct > 0 ? "+" : ""}${deltaPct.toFixed(1)}%`, cls: `text-end ${cls}` };
    }

    get expenseRanking() {
        const r = this.state.data.expense_ranking || { items: [] };
        return {
            headers: [
                { label: _t("Cuenta") },
                { label: _t("Monto"), align: "end" },
                { label: _t("% del total"), align: "end" },
                { label: _t("Var. vs ant."), align: "end" },
            ],
            rows: r.items.map((it) => ({
                id: `exp_${it.account_id}`,
                account_id: it.account_id,
                drillType: "expense",
                cells: [
                    { text: it.name },
                    { text: this.fmt(it.amount), cls: "text-end fw-semibold" },
                    { text: `${it.pct.toFixed(1)}%`, cls: "text-end text-muted" },
                    this._deltaCell(it.delta_pct),
                ],
            })),
        };
    }

    _partnerRanking(side) {
        const r = this.state.data.partner_rankings?.[side] || { items: [] };
        const items = this._sortedPartnerItems(side, r.items);
        return {
            headers: [
                { label: side === "receivable" ? _t("Cliente") : _t("Proveedor"), sortKey: "name" },
                { label: _t("Pendiente"), align: "end", sortKey: "pending" },
                { label: _t("Vencido"), align: "end", sortKey: "overdue" },
                { label: _t("Días prom."), align: "end", sortKey: "avg_days" },
                { label: _t("% cartera"), align: "end", sortKey: "pct" },
            ],
            rows: items.map((it) => ({
                id: `${side}_${it.partner_id}`,
                partner_id: it.partner_id,
                drillType: side === "receivable" ? "receivable_partner" : "payable_partner",
                cells: [
                    { text: it.name },
                    { text: this.fmt(it.pending), cls: "text-end fw-semibold" },
                    { text: this.fmt(it.overdue), cls: "text-end text-danger" },
                    { text: `${it.avg_days.toFixed(0)}`, cls: "text-end" },
                    { text: `${it.pct.toFixed(1)}%`, cls: "text-end text-muted" },
                ],
            })),
            sortState: this.state.agingSort[side],
        };
    }

    _sortedPartnerItems(side, items) {
        const list = (items || []).slice();
        const cur = this.state.agingSort[side];
        const factor = cur.dir === "desc" ? -1 : 1;
        list.sort((a, b) => {
            if (cur.key === "name") {
                return factor * String(a.name).localeCompare(String(b.name));
            }
            return factor * ((Number(a[cur.key]) || 0) - (Number(b[cur.key]) || 0));
        });
        return list;
    }

    onAgingSort(side, key) {
        const cur = this.state.agingSort[side];
        if (cur.key === key) {
            cur.dir = cur.dir === "desc" ? "asc" : "desc";
        } else {
            this.state.agingSort[side] = { key, dir: "desc" };
        }
    }

    get receivableRanking() {
        return this._partnerRanking("receivable");
    }

    get payableRanking() {
        return this._partnerRanking("payable");
    }

    // ----------------------------------------------------------------
    // Indicadores de cobranza / pago
    // ----------------------------------------------------------------
    get collectionCards() {
        const c = this.state.data.collection || {};
        return [
            { id: "dso", label: _t("Días cartera (DSO)"), icon: "fa-calendar", tone: "neutral", value: `${(c.dso ?? 0).toFixed(0)} d` },
            { id: "overdue_pct", label: _t("% cartera vencida"), icon: "fa-exclamation-triangle", tone: "danger", value: `${(c.overdue_pct ?? 0).toFixed(1)}%` },
            { id: "over120_pct", label: _t("% +120 días"), icon: "fa-hourglass-end", tone: "danger", value: `${(c.over_120_pct ?? 0).toFixed(1)}%` },
            { id: "collected", label: _t("Recuperación"), icon: "fa-arrow-down", tone: "success", value: this.fmt(c.collected ?? 0) },
            { id: "invoiced", label: _t("Facturación"), icon: "fa-file-text-o", tone: "balance", value: this.fmt(c.invoiced ?? 0) },
            { id: "collection_ratio", label: _t("Cobros / facturación"), icon: "fa-percent", tone: "neutral", value: `${(c.collection_ratio ?? 0).toFixed(1)}%` },
        ];
    }

    get paymentCards() {
        const p = this.state.data.payment || {};
        return [
            { id: "dpo", label: _t("Días pago (DPO)"), icon: "fa-calendar", tone: "neutral", value: `${(p.dpo ?? 0).toFixed(0)} d` },
            { id: "pay_overdue_pct", label: _t("% por pagar vencido"), icon: "fa-exclamation-triangle", tone: "danger", value: `${(p.overdue_pct ?? 0).toFixed(1)}%` },
            { id: "paid", label: _t("Pagos realizados"), icon: "fa-arrow-up", tone: "danger", value: this.fmt(p.paid ?? 0) },
            { id: "purchased", label: _t("Compras/gastos"), icon: "fa-shopping-cart", tone: "balance", value: this.fmt(p.purchased ?? 0) },
            { id: "payment_ratio", label: _t("Pagos / obligaciones"), icon: "fa-percent", tone: "neutral", value: `${(p.payment_ratio ?? 0).toFixed(1)}%` },
        ];
    }

    // ----------------------------------------------------------------
    // Drill-down a apuntes contables (respeta filtros activos)
    // ----------------------------------------------------------------
    async openAccountMoveLines(row) {
        if (!this.state.data.capabilities?.can_view_detail) {
            this.notification.add(
                _t("Necesita permisos de gestor contable para ver el detalle."),
                { type: "warning" }
            );
            return;
        }
        try {
            const action = await this.orm.call(
                "gn.financial.dashboard",
                "open_move_lines",
                [{
                    ...this.state.filters,
                    journal_ids: [...this.state.filters.journal_ids],
                    drill_type: row.drillType,
                    account_id: row.account_id || false,
                    partner_id: row.partner_id || false,
                }]
            );
            if (action?.type) {
                this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    onRankingRowClick(row) {
        if (!row.drillType) {
            return;
        }
        this.openAccountMoveLines(row);
    }

    // ----------------------------------------------------------------
    // Variaciones (V20 Fase 1)
    // ----------------------------------------------------------------
    get varianceItems() {
        return this.state.data.variance || [];
    }

    async _openVarianceDrill(payload) {
        if (!this.state.data.capabilities?.can_view_detail) {
            this.notification.add(
                _t("Necesita permisos de gestor contable para ver el detalle."),
                { type: "warning" }
            );
            return;
        }
        try {
            const action = await this.orm.call(
                "gn.financial.dashboard",
                "open_move_lines",
                [{ ...this._filtersPayload(), ...payload }]
            );
            if (action?.type) {
                this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    onVarianceAccountClick(accountId, _kpi) {
        if (!accountId) {
            return;
        }
        this._openVarianceDrill({
            drill_type: "account",
            account_id: accountId,
        });
    }

    onVariancePartnerClick(partnerId, kpi) {
        if (!partnerId) {
            return;
        }
        // Para ingresos drilleamos por receivable; para gastos/costo, por payable.
        const drill_type = kpi === "revenue" ? "receivable_partner" : "payable_partner";
        this._openVarianceDrill({ drill_type, partner_id: partnerId });
    }

    // ----------------------------------------------------------------
    // Drill-down de detalle por cuenta (clic en KPI)
    // ----------------------------------------------------------------
    get _detailKeys() {
        return [
            "revenue", "cogs", "gross_profit", "expenses", "net_profit",
            "cash_surplus", "closing_bank", "receivables", "payables",
            "working_capital", "total_assets", "net_assets",
        ];
    }

    async openAccountDetail(card) {
        if (!card?.key || !this._detailKeys.includes(card.key)) {
            return;
        }
        try {
            const detail = await this.orm.call(
                "gn.financial.dashboard",
                "get_account_detail",
                [
                    { ...this.state.filters, journal_ids: [...this.state.filters.journal_ids] },
                    card.key,
                ]
            );
            this.dialog.add(AccountDetailDialog, {
                title: _t("Detalle: %s").replace("%s", card.label),
                detail,
                onOpenLines: (row) => this.openAccountMoveLines({
                    drillType: "account",
                    account_id: row.account_id,
                }),
            });
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    isCardDrillable(card) {
        return this._detailKeys.includes(card.key);
    }

    // ----------------------------------------------------------------
    // Exportaciones (solo gestor)
    // ----------------------------------------------------------------
    get canExport() {
        return !!this.state.data.capabilities?.can_export;
    }

    async _export(method) {
        try {
            const action = await this.orm.call(
                "gn.financial.dashboard",
                method,
                [{ ...this.state.filters, journal_ids: [...this.state.filters.journal_ids] }]
            );
            if (action) {
                this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    onExportPdf() {
        return this._export("action_export_pdf");
    }

    onExportExcel() {
        return this._export("action_export_excel");
    }

    // ----------------------------------------------------------------
    // Flujo de caja
    // ----------------------------------------------------------------
    get hasCashflow() {
        const c = this.state.data.cashflow;
        return !!(c && c.labels && c.labels.length);
    }

    get cashflowConfig() {
        const c = this.state.data.cashflow || { labels: [], inflow: [], outflow: [], cumulative: [] };
        return {
            type: "bar",
            data: {
                labels: c.labels,
                datasets: [
                    { label: _t("Entradas"), data: c.inflow, backgroundColor: PALETTE.income, order: 2 },
                    { label: _t("Salidas"), data: c.outflow, backgroundColor: PALETTE.expense, order: 3 },
                    { label: _t("Saldo acumulado"), data: c.cumulative, type: "line", borderColor: PALETTE.net, backgroundColor: "transparent", borderWidth: 3, tension: 0.25, pointRadius: 3, order: 1 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { position: "top" }, tooltip: this._moneyTooltip() },
                scales: {
                    y: { ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }

    get cashflowFingerprint() {
        return JSON.stringify(this.state.data.cashflow || {});
    }

    get cashflowCards() {
        const c = this.state.data.cashflow || {};
        return [
            { id: "cf_opening", label: _t("Saldo inicial"), icon: "fa-flag-o", tone: "neutral", value: this.fmt(c.opening ?? 0) },
            { id: "cf_operating", label: _t("Flujo operativo"), icon: "fa-cogs", tone: "balance", value: this.fmt(c.operating ?? 0) },
            { id: "cf_investing", label: _t("Flujo inversión"), icon: "fa-building-o", tone: "neutral", value: this.fmt(c.investing ?? 0) },
            { id: "cf_financing", label: _t("Flujo financiamiento"), icon: "fa-bank", tone: "neutral", value: this.fmt(c.financing ?? 0) },
            { id: "cf_closing", label: _t("Saldo final"), icon: "fa-flag-checkered", tone: "success", value: this.fmt(c.closing ?? 0) },
        ];
    }

    // ----------------------------------------------------------------
    // Calidad de datos y cierre contable
    // ----------------------------------------------------------------
    get analysisNotes() {
        return this.state.data.analysis || [];
    }

    get dataQualityChecks() {
        return this.state.data.data_quality?.checks || [];
    }

    get closingStatus() {
        return this.state.data.closing_status || {};
    }

    get closingSummary() {
        const c = this.closingStatus;
        const parts = [];
        if (c.posted !== undefined) {
            parts.push(_t("%s asientos publicados").replace("%s", c.posted));
        }
        if (c.draft) {
            parts.push(_t("%s en borrador").replace("%s", c.draft));
        }
        if (c.last_date) {
            parts.push(_t("último: %s").replace("%s", c.last_date));
        }
        return parts.join(" · ");
    }

    // ----------------------------------------------------------------
    // Score explicable: categorías, riesgo, radar y recomendaciones
    // ----------------------------------------------------------------
    get healthCategories() {
        return this.state.data.health?.categories || [];
    }

    get riskIndicator() {
        return this.state.data.health?.risk || null;
    }

    get radarConfig() {
        const r = this.state.data.health?.radar;
        if (!r || !r.labels || !r.labels.length) {
            return null;
        }
        return {
            type: "radar",
            data: {
                labels: r.labels,
                datasets: [{
                    label: _t("Puntaje"),
                    data: r.values,
                    backgroundColor: "rgba(91, 44, 111, 0.18)",
                    borderColor: PALETTE.total,
                    borderWidth: 2,
                    pointBackgroundColor: PALETTE.total,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    r: {
                        min: 0,
                        max: 100,
                        ticks: { stepSize: 20, display: false },
                        pointLabels: { font: { size: 11 } },
                        grid: { color: PALETTE.grid },
                        angleLines: { color: PALETTE.grid },
                    },
                },
            },
        };
    }

    get radarFingerprint() {
        return JSON.stringify(this.state.data.health?.radar || {});
    }

    get recommendations() {
        return this.state.data.recommendations || [];
    }

    get decisions() {
        return this.state.data.decisions || [];
    }

    fmtBound() {
        // Devuelve un fn que componentes hijos pueden usar para formatear
        // montos sin acoplar la lógica de moneda. ``bind`` mantiene ``this``.
        return (v) => this.fmt(v);
    }

    // ----------------------------------------------------------------
    // Drill-down de gráficos (clic en barras, dona, cascada, aging)
    // ----------------------------------------------------------------
    chartMeta(key) {
        return this.state.data.kpi_meta?.[key] || null;
    }

    /**
     * Mapeo mes índice → 'YYYY-MM' a partir de las etiquetas del eje X.
     * Las etiquetas tienen formato "Ene 2026", lo convertimos al formato
     * usado por el backend (``YYYY-MM``).
     */
    _labelToMonth(label) {
        if (!label) return null;
        const months = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
        const parts = String(label).split(" ");
        if (parts.length !== 2) return null;
        const m = months.indexOf(parts[0]) + 1;
        if (m <= 0) return null;
        return `${parts[1]}-${String(m).padStart(2, "0")}`;
    }

    /** Mapea el datasetIndex de la serie mensual a tipos de cuenta. */
    _monthlyDatasetTypes(datasetIndex) {
        // 0=Ingresos, 1=Gastos, 2=Utilidad neta (línea)
        if (datasetIndex === 0) return ["income", "income_other"];
        if (datasetIndex === 1) return ["expense_direct_cost", "expense", "expense_depreciation"];
        return ["income", "income_other", "expense_direct_cost", "expense", "expense_depreciation"];
    }

    onMonthlyClick({ datasetIndex, label }) {
        const month = this._labelToMonth(label);
        if (!month) return;
        this._drilldown({
            drill_type: "account_type_month",
            account_types: this._monthlyDatasetTypes(datasetIndex),
            month,
            label: `${label}`,
        });
    }

    onCashflowClick({ label }) {
        const month = this._labelToMonth(label);
        if (!month) return;
        this._drilldown({
            drill_type: "cash_month",
            month,
            label: `Flujo de caja · ${label}`,
        });
    }

    onWaterfallClick({ index }) {
        // 0=Ingresos, 1=COGS, 2=Utilidad bruta, 3=Gastos, 4=Utilidad neta
        const map = [
            ["income", "income_other"],
            ["expense_direct_cost"],
            null, // utilidad bruta es derivada, no se hace drill-down
            ["expense", "expense_depreciation"],
            null, // utilidad neta también derivada
        ];
        const types = map[index];
        if (!types) return;
        const labels = ["Ingresos", "Costo de ventas", "", "Gastos", ""];
        this._drilldown({
            drill_type: "account_type",
            account_types: types,
            label: labels[index],
        });
    }

    onExpenseDonutClick({ index }) {
        const breakdown = this.state.data.expense_breakdown || {};
        const accountId = (breakdown.account_ids || [])[index];
        if (!accountId) return;
        this._drilldown({
            drill_type: "account",
            account_id: accountId,
            label: (breakdown.labels || [])[index] || "Detalle de cuenta",
        });
    }

    onAgingBucketClick(side, { index, label }) {
        this._drilldown({
            drill_type: "aging_bucket",
            side,
            bucket: index,
            label: `${side === "receivable" ? "Por cobrar" : "Por pagar"} · ${label}`,
        });
    }

    onReceivableAgingClick(payload) {
        this.onAgingBucketClick("receivable", payload);
    }

    onPayableAgingClick(payload) {
        this.onAgingBucketClick("payable", payload);
    }

    // ----------------------------------------------------------------
    // Planeación: presupuesto vs real, pronóstico, simulador, timeline
    // ----------------------------------------------------------------
    get planning() {
        return this.state.data.planning || null;
    }

    get budgetCategories() {
        return this.planning?.budget?.categories || [];
    }

    get budgetNet() {
        return this.planning?.budget?.net || null;
    }

    get forecast() {
        return this.planning?.forecast || null;
    }

    get timeline() {
        return this.planning?.timeline || [];
    }

    /** Config del gráfico presupuesto vs real (utilidad neta acumulada). */
    get planningChartConfig() {
        const b = this.planning?.budget;
        if (!b) return { type: "bar", data: { labels: [], datasets: [] } };
        const labels = b.labels;
        // Acumulados de presupuesto y real para la utilidad neta.
        const cumBudget = [];
        const cumActual = [];
        let cb = 0;
        let ca = 0;
        for (let i = 0; i < 12; i++) {
            cb += b.net.budget[i] || 0;
            cumBudget.push(Math.round(cb));
            if (i < b.cutoff) {
                ca += b.net.actual[i] || 0;
                cumActual.push(Math.round(ca));
            } else {
                cumActual.push(null);
            }
        }
        return {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        type: "line",
                        label: _t("Meta acumulada"),
                        data: cumBudget,
                        borderColor: PALETTE.total,
                        backgroundColor: "transparent",
                        borderDash: [6, 4],
                        tension: 0.3,
                        pointRadius: 2,
                    },
                    {
                        type: "line",
                        label: _t("Real acumulado"),
                        data: cumActual,
                        borderColor: PALETTE.incomeBorder,
                        backgroundColor: "rgba(25,135,84,.12)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { ticks: { callback: (v) => compactNumber(v) } } },
            },
        };
    }

    get planningFingerprint() {
        return JSON.stringify(this.planning?.budget?.net || {});
    }

    // ---- Simulador ----
    get simBase() {
        return this.planning?.sim_base || { income: 0, cogs: 0, expenses: 0 };
    }

    get simResult() {
        const base = this.simBase;
        const f = (v) => 1 + (Number(v) || 0) / 100;
        const income = base.income * f(this.state.sim.income);
        const cogs = base.cogs * f(this.state.sim.cogs);
        const expenses = base.expenses * f(this.state.sim.expenses);
        const net = income - cogs - expenses;
        const baseNet = base.income - base.cogs - base.expenses;
        return {
            income,
            cogs,
            expenses,
            net,
            baseNet,
            delta: net - baseNet,
            margin: income ? (net / income) * 100 : 0,
        };
    }

    onSimInput(key, ev) {
        this.state.sim[key] = parseFloat(ev.target.value) || 0;
    }

    resetSim() {
        this.state.sim = { income: 0, cogs: 0, expenses: 0 };
    }

    timelineIconClass(ev) {
        const map = {
            closing: "fa-calendar-check-o",
            milestone: "fa-flag",
            goal: "fa-trophy",
        };
        return map[ev.type] || "fa-circle";
    }

    timelineStatusClass(ev) {
        return `gn-fd-tl__item--${ev.status}`;
    }

    openBudgetEditor() {
        const actionId = this.planning?.budget_action_id;
        if (actionId) {
            this.action.doAction(actionId);
        }
    }

    devCls(favorable) {
        return favorable ? "text-success" : "text-danger";
    }

    // ----------------------------------------------------------------
    // Vigilancia: multi-año, benchmark, calendario, alertas
    // ----------------------------------------------------------------
    get watch() {
        return this.state.data.watch || null;
    }

    get multiyear() {
        return this.watch?.multiyear || null;
    }

    get multiyearConfig() {
        const m = this.multiyear;
        if (!m) return { type: "bar", data: { labels: [], datasets: [] } };
        return {
            type: "bar",
            data: {
                labels: m.labels,
                datasets: [
                    { label: _t("Ingresos"), data: m.income, backgroundColor: PALETTE.income, borderColor: PALETTE.incomeBorder, borderWidth: 1 },
                    { label: _t("Gastos"), data: m.expense, backgroundColor: PALETTE.expense, borderColor: PALETTE.expenseBorder, borderWidth: 1 },
                    { type: "line", label: _t("Utilidad neta"), data: m.net, borderColor: PALETTE.net, backgroundColor: "transparent", tension: 0.3, pointRadius: 3 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } } },
            },
        };
    }

    get multiyearFingerprint() {
        return JSON.stringify(this.multiyear?.net || []);
    }

    get benchmark() {
        return this.watch?.benchmark || null;
    }

    get benchmarkRows() {
        return this.benchmark?.rows || [];
    }

    rankCls(rank) {
        if (rank === "best") return "gn-fd-bench__row--best";
        if (rank === "worst") return "gn-fd-bench__row--worst";
        return "";
    }

    get calendar() {
        return this.watch?.calendar || null;
    }

    get calendarEvents() {
        return this.calendar?.events || [];
    }

    get alertCenter() {
        return this.watch?.alerts || null;
    }

    get watchAlerts() {
        return this.alertCenter?.alerts || [];
    }

    severityCls(sev) {
        return `gn-fd-alert--${sev}`;
    }

    severityIcon(sev) {
        const map = {
            critical: "fa-exclamation-circle",
            warning: "fa-exclamation-triangle",
            info: "fa-info-circle",
        };
        return map[sev] || "fa-info-circle";
    }

    // ----------------------------------------------------------------
    // Vista ejecutiva (resumen de una ojeada + narrativa IA)
    // ----------------------------------------------------------------
    get executive() {
        return this.state.data.executive || null;
    }

    get execHealthCls() {
        const lvl = this.executive?.health?.level;
        return `gn-fd-exec-health--${lvl || "good"}`;
    }

    get execKpiCards() {
        const e = this.executive;
        if (!e) return [];
        const k = e.kpis || {};
        const cmp = e.compare?.kpis || {};
        const defs = [
            { key: "revenue", label: _t("Ingresos"), icon: "fa-arrow-up" },
            { key: "net_profit", label: _t("Utilidad neta"), icon: "fa-line-chart" },
            { key: "closing_bank", label: _t("Saldo bancario"), icon: "fa-university" },
            { key: "receivables", label: _t("Por cobrar"), icon: "fa-hand-holding-usd" },
        ];
        return defs.map((d) => {
            const cur = k[d.key] ?? 0;
            const prev = cmp[d.key];
            let deltaPct = null;
            if (prev !== undefined && prev !== 0) {
                deltaPct = ((cur - prev) / Math.abs(prev)) * 100;
            }
            return {
                ...d,
                value: this.fmt(cur),
                deltaPct: deltaPct === null ? null : deltaPct.toFixed(1),
                deltaUp: deltaPct !== null && deltaPct >= 0,
            };
        });
    }

    get execNarrative() {
        return this.executive?.narrative || null;
    }

    get execAlerts() {
        return this.executive?.alerts?.top || [];
    }

    get execMultiyearConfig() {
        const m = this.executive?.multiyear;
        if (!m) return { type: "bar", data: { labels: [], datasets: [] } };
        return {
            type: "bar",
            data: {
                labels: m.labels,
                datasets: [
                    { label: _t("Utilidad neta"), data: m.net, backgroundColor: PALETTE.total },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } } },
            },
        };
    }

    get execMultiyearFingerprint() {
        return JSON.stringify(this.executive?.multiyear?.net || []);
    }

    async _drilldown(extra) {
        if (!this.state.data.capabilities?.can_view_detail) {
            this.notification.add(
                _t("Necesita permisos de gestor contable para ver el detalle."),
                { type: "warning" }
            );
            return;
        }
        try {
            const action = await this.orm.call(
                "gn.financial.dashboard",
                "open_move_lines",
                [{
                    ...this.state.filters,
                    journal_ids: [...this.state.filters.journal_ids],
                    ...extra,
                }]
            );
            if (action?.type) {
                this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    // ----------------------------------------------------------------
    // V20 Fase 2: KPIs personalizados (#1)
    // ----------------------------------------------------------------
    get uid() {
        // ID del usuario actual (para distinguir workspaces propios vs.
        // compartidos en la UI).
        return this.env.services.user?.userId || (typeof odoo !== "undefined" && odoo.session_info?.uid) || 0;
    }

    get customKpiItems() {
        return (this.state.customKpis?.items || []).filter((k) => k.show_in_my_kpis);
    }

    get featuredCustomKpis() {
        // Los KPIs marcados como "show_in_overview" se muestran como tarjetas
        // adicionales en la pestaña Resumen.
        return (this.state.customKpis?.items || []).filter((k) => k.show_in_overview);
    }

    async onCustomKpiClick(kpi) {
        if (!kpi || kpi.error || !kpi.account_ids?.length) {
            return;
        }
        await this._drilldown({
            drill_type: 'custom_kpi',
            account_ids: kpi.account_ids,
            from_beginning: kpi.period_mode === 'asof',
            label: kpi.name,
        });
    }

    onOpenKpiBuilder() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "gn.financial.dashboard.kpi",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            name: _t("KPIs personalizados"),
        });
    }

    onOpenGoalsConfig() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "gn.financial.dashboard.goal",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            name: _t("Objetivos estratégicos"),
        });
    }

    // ----------------------------------------------------------------
    // V20 Fase 2: Objetivos estratégicos (#19)
    // ----------------------------------------------------------------
    async loadGoals() {
        try {
            this.state.goals = await this.orm.call(
                "gn.financial.dashboard",
                "get_goals_progress",
                [this._filtersPayload()]
            );
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message, { type: "warning" });
        }
    }

    async onGoalClick(goal) {
        if (!goal) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "gn.financial.dashboard.goal",
            res_id: goal.id,
            views: [[false, "form"]],
            target: "current",
            name: goal.name,
        });
    }

    // ----------------------------------------------------------------
    // V20 Fase 2: Espacios de trabajo (#2 + #20)
    // ----------------------------------------------------------------
    async loadWorkspaces() {
        try {
            const res = await this.orm.call(
                "gn.financial.dashboard",
                "get_workspaces",
                [],
                { company_id: this.state.filters.company_id || false }
            );
            this.state.workspaces = { list: res.workspaces || [], active_id: res.active_id || false };
            this._applyWorkspaceLayout();
        } catch (e) {
            // Silencioso: si los modelos no se han instalado aún, no rompe.
            this.state.workspaces = { list: [], active_id: false };
        }
    }

    get activeWorkspace() {
        const id = this.state.workspaces.active_id;
        return (this.state.workspaces.list || []).find((w) => w.id === id) || null;
    }

    _applyWorkspaceLayout() {
        // Por ahora aplicamos solo el orden de pestañas y la visibilidad de
        // secciones (los handlers de tabs/sections ya hacen merge con
        // state.data.config). Las extensiones avanzadas vendrán en una iteración
        // futura sin tocar este punto.
        const ws = this.activeWorkspace;
        if (!ws || !ws.layout) return;
        if (ws.layout.tabs_order?.length) {
            this._tabOrderOverride = ws.layout.tabs_order;
        } else {
            this._tabOrderOverride = null;
        }
    }

    onSelectWorkspace(ev) {
        const id = Number(ev.target.value) || false;
        this.state.workspaces.active_id = id;
        this._applyWorkspaceLayout();
    }

    onOpenWorkspaceEditor() {
        const ws = this.activeWorkspace;
        this.state.workspaceEditor = {
            visible: true,
            id: ws?.id || false,
            name: ws?.name || _t("Mi tablero"),
            shared: !!ws?.shared,
            isDefault: !!ws?.is_default,
        };
    }

    onCloseWorkspaceEditor() {
        this.state.workspaceEditor.visible = false;
    }

    async onSaveWorkspace() {
        const ed = this.state.workspaceEditor;
        if (!ed.name?.trim()) {
            this.notification.add(_t("El nombre del espacio es obligatorio."),
                                  { type: "warning" });
            return;
        }
        // Layout actual: usamos la config visible de secciones y el orden
        // implícito de pestañas (basado en _tabDefs). El frontend lo guarda
        // como base; futuras versiones permitirán arrastrar y soltar.
        const layout = {
            tabs_order: this.tabs.map((t) => t.key),
            sections: (this.state.data.config?.sections || []).map((s) => ({
                key: s.key, visible: s.visible, sequence: s.sequence,
            })),
        };
        try {
            const payload = await this.orm.call(
                "gn.financial.dashboard",
                "save_workspace",
                [{
                    id: ed.id || false,
                    name: ed.name.trim(),
                    shared: !!ed.shared,
                    is_default: !!ed.isDefault,
                    company_id: this.state.filters.company_id || false,
                    layout,
                }]
            );
            this.notification.add(_t("Espacio de trabajo guardado."),
                                  { type: "success" });
            this.state.workspaceEditor.visible = false;
            await this.loadWorkspaces();
            this.state.workspaces.active_id = payload.id;
            this._applyWorkspaceLayout();
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        }
    }

    async onDuplicateWorkspace() {
        const ws = this.activeWorkspace;
        if (!ws) return;
        try {
            const payload = await this.orm.call(
                "gn.financial.dashboard",
                "duplicate_workspace",
                [ws.id]
            );
            this.notification.add(_t("Workspace duplicado."), { type: "success" });
            await this.loadWorkspaces();
            this.state.workspaces.active_id = payload.id;
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        }
    }

    async onDeleteWorkspace() {
        const ws = this.activeWorkspace;
        if (!ws) return;
        if (!window.confirm(_t("¿Eliminar este espacio de trabajo?"))) {
            return;
        }
        try {
            await this.orm.call(
                "gn.financial.dashboard",
                "delete_workspace",
                [ws.id]
            );
            this.notification.add(_t("Workspace eliminado."), { type: "success" });
            await this.loadWorkspaces();
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        }
    }

    // ----------------------------------------------------------------
    // V20 Fase 3 — Inteligencia de entidades (productos/clientes/proveedores)
    // ----------------------------------------------------------------
    async onSelectIntelTab(sub) {
        this.state.intelSubtab = sub;
        await this.ensureIntelLoaded(sub);
    }

    async ensureIntelLoaded(sub) {
        if (this.state.intelLoaded[sub]) return;
        const map = {
            products: { rpc: "get_product_intelligence", key: "intelProducts" },
            customers: { rpc: "get_customer_intelligence", key: "intelCustomers" },
            suppliers: { rpc: "get_supplier_intelligence", key: "intelSuppliers" },
        };
        const cfg = map[sub];
        if (!cfg) return;
        this.state.intelLoading = true;
        try {
            const result = await this.orm.call(
                "gn.financial.dashboard",
                cfg.rpc,
                [this._filtersPayload()]
            );
            this.state[cfg.key] = result;
            this.state.intelLoaded[sub] = true;
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        } finally {
            this.state.intelLoading = false;
        }
    }

    // Esquema de columnas reutilizable por sub-tab.
    get productColumns() {
        return [
            { key: "name", label: _t("Producto"), align: "left" },
            { key: "revenue", label: _t("Ingresos"), align: "right", format: "money", width: "12%" },
            { key: "cost", label: _t("Costo"), align: "right", format: "money", width: "11%" },
            { key: "margin", label: _t("Margen"), align: "right", format: "money", width: "11%" },
            { key: "margin_pct", label: _t("Margen %"), align: "right", format: "percent", width: "8%" },
            { key: "qty", label: _t("Cantidad"), align: "right", format: "qty", width: "9%" },
            { key: "pct", label: _t("% Total"), align: "right", format: "percent", width: "7%" },
            { key: "frequency", label: _t("Facturas"), align: "right", format: "int", width: "7%" },
        ];
    }
    get customerColumns() {
        return [
            { key: "name", label: _t("Cliente"), align: "left" },
            { key: "score", label: _t("Score"), align: "center", format: "score", width: "8%" },
            { key: "revenue", label: _t("Ingresos"), align: "right", format: "money", width: "13%" },
            { key: "pending", label: _t("Pendiente"), align: "right", format: "money", width: "11%" },
            { key: "overdue", label: _t("Vencido"), align: "right", format: "money", width: "11%" },
            { key: "overdue_pct", label: _t("Mora %"), align: "right", format: "percent", width: "7%" },
            { key: "dso_days", label: _t("DSO"), align: "right", format: "days", width: "7%" },
            { key: "frequency", label: _t("Facturas"), align: "right", format: "int", width: "7%" },
        ];
    }
    get supplierColumns() {
        return [
            { key: "name", label: _t("Proveedor"), align: "left" },
            { key: "score", label: _t("Score"), align: "center", format: "score", width: "8%" },
            { key: "purchases", label: _t("Compras"), align: "right", format: "money", width: "13%" },
            { key: "concentration_pct", label: _t("Dependencia"), align: "right", format: "percent", width: "10%" },
            { key: "pending", label: _t("Por pagar"), align: "right", format: "money", width: "11%" },
            { key: "dpo_days", label: _t("DPO"), align: "right", format: "days", width: "7%" },
            { key: "frequency", label: _t("Facturas"), align: "right", format: "int", width: "7%" },
        ];
    }

    // Currency helper para los 3 sub-tabs.
    get intelCurrencySymbol() {
        const sub = this.state.intelSubtab;
        const payload = sub === "products" ? this.state.intelProducts
                      : sub === "customers" ? this.state.intelCustomers
                      : this.state.intelSuppliers;
        return payload?.currency?.symbol || this.currencySymbol;
    }

    async onProductClick(item) {
        if (!item?.product_id) return;
        await this._drilldown({
            drill_type: "product",
            product_id: item.product_id,
            side: "revenue",
            label: item.name || _t("Producto"),
        });
    }

    async onCustomerClick(item) {
        if (!item?.partner_id) return;
        await this._drilldown({
            drill_type: "partner_revenue",
            partner_id: item.partner_id,
            label: item.name || _t("Cliente"),
        });
    }

    async onSupplierClick(item) {
        if (!item?.partner_id) return;
        await this._drilldown({
            drill_type: "partner_purchases",
            partner_id: item.partner_id,
            label: item.name || _t("Proveedor"),
        });
    }

    async onPartnerOpenForm(item) {
        if (!item?.partner_id) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: item.partner_id,
            views: [[false, "form"]],
            target: "current",
            name: item.name,
        });
    }

    // ----------------------------------------------------------------
    // V20 Fase 4 — Dashboards por área (Comercial / Compras / Inventario / hooks)
    // ----------------------------------------------------------------
    get areaCaps() {
        return this.state.filterOptions?.areas || {};
    }

    get hasAnyArea() {
        const c = this.areaCaps;
        return !!(c.sales || c.purchase || c.inventory || (c.customs || []).length);
    }

    // Tabs disponibles (en orden) considerando capacidades del backend.
    get availableAreaSubtabs() {
        const caps = this.areaCaps;
        const tabs = [];
        if (caps.sales) tabs.push({ key: "sales", label: _t("Comercial"), icon: "fa-shopping-cart", rpc: "get_sales_data" });
        if (caps.purchase) tabs.push({ key: "purchase", label: _t("Compras"), icon: "fa-truck", rpc: "get_purchase_data" });
        if (caps.inventory) tabs.push({ key: "inventory", label: _t("Inventario"), icon: "fa-cubes", rpc: "get_inventory_data" });
        for (const c of (caps.customs || [])) {
            tabs.push({ key: c.key, label: c.label, icon: c.icon || "fa-puzzle-piece", rpc: c.rpc });
        }
        return tabs;
    }

    async onSelectAreaTab(key) {
        this.state.areaSubtab = key;
        await this.ensureAreaLoaded(key);
    }

    async ensureAreaLoaded(key) {
        if (this.state.areaLoaded[key]) return;
        const def = this.availableAreaSubtabs.find((t) => t.key === key);
        if (!def) return;
        this.state.areaLoading = true;
        try {
            const result = await this.orm.call(
                "gn.financial.dashboard",
                def.rpc,
                [this._filtersPayload()]
            );
            this.state.areaPayloads[key] = result;
            this.state.areaLoaded[key] = true;
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        } finally {
            this.state.areaLoading = false;
        }
    }

    // Acceso reactivo al payload activo (atajos para el template).
    get salesData() { return this.state.areaPayloads.sales; }
    get purchaseData() { return this.state.areaPayloads.purchase; }
    get inventoryData() { return this.state.areaPayloads.inventory; }
    get activeAreaPayload() { return this.state.areaPayloads[this.state.areaSubtab]; }
    get activeAreaCurrencySymbol() {
        return this.activeAreaPayload?.currency?.symbol || this.currencySymbol;
    }

    // --- Columnas de tablas para reutilizar IntelligenceTable ---
    get salesSellerColumns() {
        return [
            { key: "name", label: _t("Vendedor"), align: "left" },
            { key: "amount", label: _t("Monto"), align: "right", format: "money", width: "20%" },
            { key: "orders", label: _t("Órdenes"), align: "right", format: "int", width: "12%" },
        ];
    }
    get salesTeamColumns() {
        return [
            { key: "name", label: _t("Equipo"), align: "left" },
            { key: "amount", label: _t("Monto"), align: "right", format: "money", width: "20%" },
            { key: "orders", label: _t("Órdenes"), align: "right", format: "int", width: "12%" },
        ];
    }
    get salesCustomerColumns() {
        return [
            { key: "name", label: _t("Cliente"), align: "left" },
            { key: "amount", label: _t("Monto"), align: "right", format: "money", width: "20%" },
            { key: "orders", label: _t("Órdenes"), align: "right", format: "int", width: "12%" },
        ];
    }
    get salesProductColumns() {
        return [
            { key: "name", label: _t("Producto"), align: "left" },
            { key: "amount", label: _t("Monto"), align: "right", format: "money", width: "20%" },
            { key: "qty", label: _t("Cantidad"), align: "right", format: "qty", width: "12%" },
        ];
    }
    get purchaseSupplierColumns() {
        return [
            { key: "name", label: _t("Proveedor"), align: "left" },
            { key: "amount", label: _t("Monto"), align: "right", format: "money", width: "20%" },
            { key: "orders", label: _t("Órdenes"), align: "right", format: "int", width: "12%" },
        ];
    }
    get purchaseBuyerColumns() { return this.salesSellerColumns; }
    get purchaseProductColumns() { return this.salesProductColumns; }
    get inventoryProductColumns() {
        return [
            { key: "name", label: _t("Producto"), align: "left" },
            { key: "qty", label: _t("Cantidad"), align: "right", format: "qty", width: "15%" },
            { key: "value", label: _t("Valor"), align: "right", format: "money", width: "18%" },
        ];
    }

    // --- Charts mensuales reutilizando el componente FinancialChart ---
    _areaMonthlyConfig(monthly, label, color) {
        const m = monthly || { labels: [], amounts: [], counts: [] };
        return {
            type: "bar",
            data: {
                labels: m.labels,
                datasets: [
                    { label: label, data: m.amounts, backgroundColor: color, borderColor: color, borderWidth: 1 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: this._moneyTooltip() },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }
    get salesMonthlyConfig() {
        return this._areaMonthlyConfig(this.salesData?.monthly, _t("Ventas confirmadas"), PALETTE.income);
    }
    get salesMonthlyFingerprint() {
        return JSON.stringify(this.salesData?.monthly || {});
    }
    get purchaseMonthlyConfig() {
        return this._areaMonthlyConfig(this.purchaseData?.monthly, _t("Compras confirmadas"), PALETTE.expense);
    }
    get purchaseMonthlyFingerprint() {
        return JSON.stringify(this.purchaseData?.monthly || {});
    }

    // --- Drill-down handlers ---
    async onAreaSalesOrderList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            name: _t("Órdenes de venta"),
            domain: [
                ["company_id", "=", this.state.filters.company_id],
                ["date_order", ">=", this.state.filters.date_from],
                ["date_order", "<=", this.state.filters.date_to],
                ["state", "in", ["sale"]],
            ],
        });
    }
    async onAreaPurchaseOrderList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.order",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            name: _t("Órdenes de compra"),
            domain: [
                ["company_id", "=", this.state.filters.company_id],
                ["date_order", ">=", this.state.filters.date_from],
                ["date_order", "<=", this.state.filters.date_to],
                ["state", "in", ["purchase"]],
            ],
        });
    }
    async onAreaInventoryProductClick(item) {
        if (!item?.product_id) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: item.product_id,
            views: [[false, "form"]],
            target: "current",
            name: item.name,
        });
    }

    // ----------------------------------------------------------------
    // V20 Fase 5 — Predicciones (forecast + score + escenarios + benchmark)
    // ----------------------------------------------------------------
    async ensurePredictionsLoaded() {
        if (this.state.predictData) return;
        await this.loadPredictions();
    }

    async loadPredictions() {
        this.state.predictLoading = true;
        try {
            const payload = this._filtersPayload();
            payload.forecast_horizon = this.state.predictHorizon;
            payload.history_months = this.state.predictHistoryMonths;
            payload.benchmark_sector = this.state.predictBenchmarkSector;
            this.state.predictData = await this.orm.call(
                "gn.financial.dashboard",
                "get_predictions_data",
                [payload],
            );
            // Sincroniza sector activo desde la respuesta (por si no existía).
            if (this.state.predictData?.benchmark?.sector) {
                this.state.predictBenchmarkSector = this.state.predictData.benchmark.sector;
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        } finally {
            this.state.predictLoading = false;
        }
    }

    async onSelectPredictTab(key) {
        this.state.predictSubtab = key;
    }

    async onChangeForecastHorizon(ev) {
        const v = parseInt(ev.target.value, 10);
        if (!Number.isNaN(v) && v >= 1 && v <= 12) {
            this.state.predictHorizon = v;
            this.state.predictData = null;
            await this.loadPredictions();
        }
    }
    async onChangeHistoryMonths(ev) {
        const v = parseInt(ev.target.value, 10);
        if (!Number.isNaN(v) && v >= 6 && v <= 36) {
            this.state.predictHistoryMonths = v;
            this.state.predictData = null;
            await this.loadPredictions();
        }
    }
    async onChangeBenchmarkSector(ev) {
        this.state.predictBenchmarkSector = ev.target.value;
        this.state.predictData = null;
        await this.loadPredictions();
    }

    // Configuración de chart para un KPI con histórico + forecast.
    _forecastChartConfig(code) {
        const fc = this.state.predictData?.forecast?.[code];
        if (!fc) return null;
        const labels = [...fc.history_labels, ...fc.forecast_labels];
        const historyOnly = [...fc.history, ...Array(fc.forecast.length).fill(null)];
        const forecastOnly = [...Array(fc.history.length).fill(null), ...fc.forecast];
        const upper = [...Array(fc.history.length).fill(null), ...fc.upper];
        const lower = [...Array(fc.history.length).fill(null), ...fc.lower];
        return {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    { label: _t("Histórico"), data: historyOnly, borderColor: PALETTE.net,
                      backgroundColor: "transparent", borderWidth: 2, tension: 0.2, pointRadius: 2, order: 2 },
                    { label: _t("Pronóstico"), data: forecastOnly, borderColor: PALETTE.subtotal,
                      borderDash: [6, 4], backgroundColor: "transparent", borderWidth: 2, tension: 0.2,
                      pointRadius: 3, order: 1 },
                    { label: _t("Banda superior"), data: upper, borderColor: "rgba(180,180,180,0.4)",
                      backgroundColor: "rgba(13,110,253,0.06)", borderWidth: 1, fill: "+1",
                      pointRadius: 0, order: 3 },
                    { label: _t("Banda inferior"), data: lower, borderColor: "rgba(180,180,180,0.4)",
                      backgroundColor: "transparent", borderWidth: 1, pointRadius: 0, order: 4 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" },
                    tooltip: this._moneyTooltip(),
                },
                scales: {
                    y: { ticks: { callback: (v) => compactNumber(v) }, grid: { color: PALETTE.grid } },
                    x: { grid: { display: false } },
                },
            },
        };
    }
    _forecastFingerprint(code) {
        const fc = this.state.predictData?.forecast?.[code];
        if (!fc) return code;
        return code + ":" + fc.history.length + ":" + fc.forecast.length
                    + ":" + (fc.forecast[0] || 0).toFixed(2);
    }

    get revenueForecastConfig() { return this._forecastChartConfig("revenue"); }
    get revenueForecastFingerprint() { return this._forecastFingerprint("revenue"); }
    get netProfitForecastConfig() { return this._forecastChartConfig("net_profit"); }
    get netProfitForecastFingerprint() { return this._forecastFingerprint("net_profit"); }
    get cashFlowForecastConfig() { return this._forecastChartConfig("cash_flow"); }
    get cashFlowForecastFingerprint() { return this._forecastFingerprint("cash_flow"); }
    get expensesForecastConfig() { return this._forecastChartConfig("expenses"); }
    get expensesForecastFingerprint() { return this._forecastFingerprint("expenses"); }
    get grossProfitForecastConfig() { return this._forecastChartConfig("gross_profit"); }
    get grossProfitForecastFingerprint() { return this._forecastFingerprint("gross_profit"); }

    get predictCurrency() {
        return this.state.predictData?.currency?.symbol || this.currencySymbol;
    }

    // --- Escenarios ---
    onScenarioInput(key, ev) {
        const raw = ev?.target?.value ?? 0;
        const v = parseFloat(raw);
        this.state.scenarioInputs = {
            ...this.state.scenarioInputs,
            [key]: Number.isNaN(v) ? 0 : v,
        };
    }
    async onRunScenario() {
        this.state.scenarioRunning = true;
        try {
            this.state.scenarioResult = await this.orm.call(
                "gn.financial.dashboard", "simulate_scenario",
                [this._filtersPayload(), this.state.scenarioInputs],
            );
        } catch (e) {
            this.notification.add(e.message?.data?.message || e.message,
                                  { type: "warning" });
        } finally {
            this.state.scenarioRunning = false;
        }
    }
    onScenarioReset() {
        this.state.scenarioInputs = {
            price_delta_pct: 0, volume_delta_pct: 0, cost_delta_pct: 0,
            opex_delta_pct: 0, dso_delta_days: 0, dpo_delta_days: 0, capex: 0,
        };
        this.state.scenarioResult = null;
    }

    // --- Helpers de formato para vistas ---
    formatScoreComponent(c) {
        if (!c) return "";
        const v = c.value;
        if (c.fmt === "percent") {
            return (typeof v === "number" ? v.toFixed(1) : v) + "%";
        }
        if (c.fmt === "money") {
            return this.predictCurrency + (typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v);
        }
        if (c.fmt === "days") {
            return (typeof v === "number" ? v.toFixed(0) : v) + " d";
        }
        return typeof v === "number" ? v.toFixed(2) : v;
    }
    benchmarkValueDisplay(c) {
        // Detecta KPI por sufijo: % o ratio.
        const code = c.kpi_code || "";
        if (code.endsWith("_pct") || code.endsWith("_pct")) {
            return c.current.toFixed(1) + "%";
        }
        if (code.endsWith("_days")) {
            return c.current.toFixed(0) + " d";
        }
        return c.current.toFixed(2);
    }
    benchmarkTargetDisplay(c) {
        const code = c.kpi_code || "";
        if (code.endsWith("_pct")) return c.target.toFixed(1) + "%";
        if (code.endsWith("_days")) return c.target.toFixed(0) + " d";
        return c.target.toFixed(2);
    }

    // =============================================================
    // V20 Fase 6: Decisiones e IA (#21, #22, #23)
    // =============================================================
    onSelectDecisionsTab(key) {
        this.state.decisionsSubtab = key;
    }

    async ensureDecisionsLoaded() {
        if (this.state.decisionsData && this.state.alertsData) {
            return;
        }
        this.state.decisionsLoading = true;
        try {
            const filters = this._filtersPayload();
            const [decisions, alerts] = await Promise.all([
                this.orm.call("gn.financial.dashboard", "get_decisions_data", [filters]),
                this.orm.call("gn.financial.dashboard", "get_alerts_data", [filters]),
            ]);
            this.state.decisionsData = decisions;
            this.state.alertsData = alerts;
        } catch (e) {
            this.notification.add(
                _t("Error al cargar Decisiones: ") + (e?.data?.message || e.message || e),
                { type: "danger" }
            );
        } finally {
            this.state.decisionsLoading = false;
        }
    }

    async reloadDecisions() {
        this.state.decisionsData = null;
        this.state.alertsData = null;
        await this.ensureDecisionsLoaded();
    }

    async onAcknowledgeAlert(eventId) {
        try {
            await this.orm.call("gn.financial.dashboard", "acknowledge_alert_event", [eventId, ""]);
            this.notification.add(_t("Alerta reconocida."), { type: "success" });
            await this.reloadDecisions();
        } catch (e) {
            this.notification.add(_t("No se pudo reconocer."), { type: "danger" });
        }
    }

    async onResolveAlert(eventId) {
        try {
            await this.orm.call("gn.financial.dashboard", "resolve_alert_event", [eventId, ""]);
            this.notification.add(_t("Alerta resuelta."), { type: "success" });
            await this.reloadDecisions();
        } catch (e) {
            this.notification.add(_t("No se pudo resolver."), { type: "danger" });
        }
    }

    async onSnoozeAlert(eventId, hours) {
        try {
            await this.orm.call(
                "gn.financial.dashboard", "snooze_alert_event", [eventId, hours]
            );
            this.notification.add(_t("Alerta pospuesta."), { type: "success" });
            await this.reloadDecisions();
        } catch (e) {
            this.notification.add(_t("No se pudo posponer."), { type: "danger" });
        }
    }

    async onSyncAlerts() {
        try {
            const r = await this.orm.call(
                "gn.financial.dashboard", "sync_alert_events", [this._filtersPayload()]
            );
            this.notification.add(
                _t("Sincronizadas: %s creadas, %s resueltas auto.").replace(
                    "%s", r.created).replace("%s", r.resolved_auto),
                { type: "success" }
            );
            await this.reloadDecisions();
        } catch (e) {
            this.notification.add(_t("No se pudo sincronizar."), { type: "danger" });
        }
    }

    onDecisionDrill(decision) {
        const dd = decision.drilldown || {};
        if (dd.partner_id) {
            // Reutiliza el drill de cartera/CxC ya existente.
            return this.openPartnerLedger(dd.partner_id);
        }
        if (dd.product_id) {
            return this.openProductForm(dd.product_id);
        }
        if (dd.goal_id) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "gn.financial.dashboard.goal",
                res_id: dd.goal_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
        if (decision.kind === "alert" && decision.source_code) {
            return this.onSelectDecisionsTab("alerts");
        }
    }

    onAlertDrill(alert) {
        const dd = alert.payload || {};
        if (dd.partner_id) {
            return this.openPartnerLedger(dd.partner_id);
        }
        if (dd.product_id) {
            return this.openProductForm(dd.product_id);
        }
        if (dd.goal_id) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "gn.financial.dashboard.goal",
                res_id: dd.goal_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }

    openPartnerLedger(partnerId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Movimientos del partner"),
            res_model: "account.move.line",
            views: [[false, "list"]],
            domain: [["partner_id", "=", partnerId], ["parent_state", "=", "posted"]],
            target: "current",
            context: { search_default_unreconciled: 1 },
        });
    }

    openProductForm(productId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Asistente IA
    async onAskAI(question) {
        if (!question) return;
        this.state.chatHistory.push({ role: "user", text: question });
        this.state.chatLoading = true;
        try {
            const r = await this.orm.call(
                "gn.financial.dashboard", "ask_ai",
                [question, this._filtersPayload()]
            );
            this.state.chatHistory.push({
                role: "assistant",
                text: r.answer,
                intent: r.intent,
                data: r.data,
            });
        } catch (e) {
            this.state.chatHistory.push({
                role: "assistant",
                text: _t("No pude procesar esa pregunta. Intenta reformularla."),
                intent: "error",
            });
        } finally {
            this.state.chatLoading = false;
        }
    }

    onClearChat() {
        this.state.chatHistory = [];
    }
}

registry.category("actions").add("gn_financial_dashboard", GnFinancialDashboard);
