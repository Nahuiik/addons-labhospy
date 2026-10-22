/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import {
    Component,
    useState,
    useEffect,
    onWillStart,
    onMounted,
    onWillUnmount,
    useRef,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatDate, parseDate } from "@web/core/l10n/dates";
import { formatMonetary } from "@web/views/fields/formatters";
import {
    loadChartJs,
    destroyChart,
    baseChartOptions,
    CHART_COLORS,
    paletteColors,
    attachChartDrilldown,
} from "./chart_utils";
import { debounce } from "@web/core/utils/timing";
import { GnBanksDashboardFilterBar } from "./filter_bar";
import { TreasuryIndicatorGaugesPanel } from "./indicator_gauges";
import { GnEmptyState, GnLoadingSkeleton, GnChartEmpty } from "./empty_state";
import { KpiSparkline } from "./kpi_sparkline";
import {
    loadStoredFilters,
    saveStoredFilters,
    clearStoredFilters,
} from "./filter_storage";
import {
    dashboardLabels,
    chartDatasetLabels,
    summaryTableTitles,
    PRIMARY_KPI_KEYS,
} from "./dashboard_labels";

const { DateTime } = luxon;
const MODEL = "gn.banks.dashboard.service";
const SUMMARY_ROW_LIMIT = 8;

const CHART_TABS = [
    { id: "operation_type", metric: "period_inflow", chartKey: "by_operation_type", labelKey: "chartByOperationType" },
    { id: "bank", metric: "period_inflow", chartKey: "by_bank", labelKey: "chartByBank" },
    { id: "branch", metric: "period_inflow", chartKey: "by_branch", labelKey: "chartByBranch" },
    { id: "checks", metric: "checks_issued", chartKey: "checks_by_state", type: "doughnut", labelKey: "chartChecksByState" },
    { id: "pos", metric: "pos_liquidations", chartKey: "pos_by_bank", labelKey: "chartPosByBank" },
    { id: "partners", metric: "period_inflow", chartKey: "top_partners", labelKey: "chartTopPartners", hasIds: true },
];

function defaultFilters(now) {
    const start = now.startOf("month");
    return {
        company_id: false,
        date_from: start.toISODate(),
        date_to: now.endOf("month").toISODate(),
        journal_ids: [],
        branch_ids: [],
        currency_id: false,
        move_types: [],
        states: [],
        partner_id: false,
        user_id: false,
        account_id: false,
        analytic_account_id: false,
        flow_source: "treasury",
    };
}

function formatIsoDate(iso) {
    if (!iso) {
        return "";
    }
    return formatDate(parseDate(iso));
}

export class GnBanksTreasuryDashboard extends Component {
    static template = "gn_banks_dashboard.GnBanksTreasuryDashboard";
    static components = {
        Layout,
        GnBanksDashboardFilterBar,
        TreasuryIndicatorGaugesPanel,
        GnEmptyState,
        GnLoadingSkeleton,
        GnChartEmpty,
        KpiSparkline,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.cashflowRef = useRef("cashflow");
        this.analysisChartRef = useRef("analysisChart");
        this.charts = {};
        this._initialLoadDone = false;
        this._analysisChartTabId = null;
        this._scheduleChartRender = debounce(() => {
            requestAnimationFrame(() => this.renderAllCharts());
        }, 16);
        this._scheduleAnalysisChartRender = debounce(async () => {
            await this.renderAnalysisChart();
        }, 16);
        this._debouncedApply = debounce(() => this.applyFilters(), 600);

        const now = DateTime.local();
        const initial = { ...defaultFilters(now), ...loadStoredFilters() };
        this.state = useState({
            loading: true,
            loadError: null,
            showAllKpis: false,
            activeChartTab: "bank",
            activeSummaryTab: "bank",
            filterOptions: {},
            draftFilters: { ...initial },
            appliedFilters: { ...initial },
            data: {
                kpis: [],
                cashflow: { labels: [], inflows: [], outflows: [], cumulative: [] },
                charts: {},
                alerts: [],
                summary_tables: {},
                insights: [],
                risk: [],
                indicator_gauges: { groups: [], gauges: [] },
            },
        });

        onWillStart(async () => {
            await this.reloadFilterOptions();
        });

        onMounted(async () => {
            await this.applyFilters();
            this._initialLoadDone = true;
        });

        // Cashflow chart re-render: triggered after the data layer settles or
        // its payload changes. Using ``useEffect`` (instead of relying solely
        // on ``_scheduleChartRender`` from ``loadData``) guarantees we run
        // *after* OWL has flushed the DOM, so the ``<canvas>`` ref is ready
        // even when the panel was previously hidden by ``state.loading``.
        useEffect(
            () => {
                if (!this.state.loading) {
                    this._scheduleChartRender();
                }
            },
            () => [
                this.state.loading,
                this._cashflowFingerprint(),
            ]
        );

        useEffect(
            () => {
                if (!this.state.loading) {
                    this._scheduleAnalysisChartRender();
                }
            },
            () => [
                this.state.loading,
                this.state.activeChartTab,
                this._analysisChartFingerprint(),
            ]
        );

        onWillUnmount(() => {
            Object.values(this.charts).forEach((c) => destroyChart(c));
        });
    }

    get labels() {
        return dashboardLabels();
    }

    get chartLabels() {
        return chartDatasetLabels();
    }

    get periodLabel() {
        const f = this.state.appliedFilters;
        if (f.date_from && f.date_to) {
            return `${formatIsoDate(f.date_from)} → ${formatIsoDate(f.date_to)}`;
        }
        return "";
    }

    get flowSourceLabel() {
        const src = this.state.appliedFilters.flow_source || "treasury";
        return src === "ledger"
            ? _t("Source: accounting ledger (bank/cash accounts)")
            : _t("Source: Treasury documents (gn_banks)");
    }

    get heroKpis() {
        const primary = new Set(PRIMARY_KPI_KEYS);
        return (this.state.data.kpis || []).filter((k) => primary.has(k.key));
    }

    get secondaryKpis() {
        const primary = new Set(PRIMARY_KPI_KEYS);
        return (this.state.data.kpis || []).filter((k) => !primary.has(k.key));
    }

    get sortedAlerts() {
        const order = { danger: 0, warning: 1, info: 2 };
        return [...(this.state.data.alerts || [])].sort(
            (a, b) => (order[a.level] ?? 9) - (order[b.level] ?? 9)
        );
    }

    get cashflowSummary() {
        const cf = this.state.data.cashflow;
        if (!cf?.labels?.length) {
            return "";
        }
        const inTotal = (cf.inflows || []).reduce((a, v) => a + (v || 0), 0);
        const outTotal = (cf.outflows || []).reduce((a, v) => a + (v || 0), 0);
        const net = inTotal - outTotal;
        return _t(
            "Inflows: %s · Outflows: %s · Net: %s",
            this.formatMoney(inTotal),
            this.formatMoney(outTotal),
            this.formatMoney(net)
        );
    }

    _cashflowTrendSeries(inflows, outflows, windowSize = 7) {
        const net = (inflows || []).map((v, i) => (v || 0) - ((outflows || [])[i] || 0));
        if (net.length < windowSize) {
            return net;
        }
        return net.map((_, i) => {
            const start = Math.max(0, i - windowSize + 1);
            const slice = net.slice(start, i + 1);
            return slice.reduce((a, v) => a + v, 0) / slice.length;
        });
    }

    kpiSparkline(kpi) {
        const cf = this.state.data.cashflow;
        if (!cf?.labels?.length) {
            return [];
        }
        const map = {
            available_balance: cf.cumulative,
            period_inflow: cf.inflows,
            period_outflow: cf.outflows,
            net_flow: (cf.inflows || []).map((v, i) => v - (cf.outflows || [])[i] || 0),
            reconciled_amount: null,
            unreconciled_amount: null,
        };
        const series = map[kpi.key];
        if (!series || !series.length) {
            return [];
        }
        return series.slice(-30);
    }

    kpiSparkColor(kpi) {
        const tone = (kpi.tone || "neutral").toLowerCase();
        const map = {
            success: "#10b981",
            danger: "#ef4444",
            warning: "#f59e0b",
            info: "#0ea5e9",
            primary: "#6366f1",
            neutral: "#64748b",
        };
        return map[tone] || map.neutral;
    }

    get hasCashflowData() {
        const cf = this.state.data.cashflow;
        const has = !!cf?.labels?.length;
        if (!has) {
            return false;
        }
        const hasFlow = (cf.inflows || []).some((v) => v) || (cf.outflows || []).some((v) => v);
        return hasFlow;
    }

    get hasAnyData() {
        return (
            (this.state.data.kpis || []).some((k) => k.amount || k.count) ||
            this.hasCashflowData
        );
    }

    get cashflowEmptyTitle() {
        return _t("Sin movimientos en el período");
    }

    get cashflowEmptyDescription() {
        return _t(
            "No hay entradas ni salidas registradas en el rango seleccionado. " +
            "Ajusta los filtros o registra nuevas operaciones."
        );
    }

    get filterValidationError() {
        const f = this.state.appliedFilters;
        if (!f.date_from || !f.date_to) {
            return _t("Selecciona un rango de fechas válido para visualizar el dashboard.");
        }
        if (f.date_from > f.date_to) {
            return _t("La fecha inicial no puede ser posterior a la fecha final.");
        }
        return null;
    }

    get chartTabs() {
        const lbl = this.labels;
        return CHART_TABS.map((t) => ({
            ...t,
            label: lbl[t.labelKey] || t.id,
        }));
    }

    get activeChartTabDef() {
        return CHART_TABS.find((t) => t.id === this.state.activeChartTab) || CHART_TABS[1];
    }

    get activeChartData() {
        const key = this.activeChartTabDef.chartKey;
        return this.state.data.charts?.[key];
    }

    get hasActiveChartData() {
        const d = this.activeChartData;
        return Boolean(d?.labels?.length && d.amounts?.some((v) => Math.abs(v) > 0.009));
    }

    get summaryTabs() {
        const tables = this.state.data.summary_tables || {};
        const titles = summaryTableTitles();
        return Object.keys(titles)
            .filter((k) => tables[k]?.rows?.length)
            .map((k) => ({ id: k, title: titles[k] }));
    }

    get activeSummaryRows() {
        const tables = this.state.data.summary_tables || {};
        const rows = tables[this.state.activeSummaryTab]?.rows || [];
        return rows.slice(0, SUMMARY_ROW_LIMIT);
    }

    get maxSummaryNet() {
        return Math.max(
            ...this.activeSummaryRows.map((r) => Math.abs(r.net)),
            1
        );
    }

    formatVariationPct(pct) {
        return _t("%s%% vs previous period", pct);
    }

    formatMoney(value) {
        const cid = this.state.filterOptions.currency_id;
        if (cid) {
            return formatMonetary(value, { currencyId: cid });
        }
        return `${this.state.filterOptions.currency_symbol || "$"}${Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    async reloadFilterOptions() {
        try {
            const opts = await this.orm.call(MODEL, "get_filter_options", [], {
                company_id: this.state.draftFilters.company_id || undefined,
            });
            this.state.filterOptions = opts;
            if (!this.state.draftFilters.company_id) {
                this.state.draftFilters.company_id = opts.company_id;
                this.state.appliedFilters.company_id = opts.company_id;
            }
            this._sanitizeJournalIds(opts);
        } catch (e) {
            this.state.loadError = e.message || _t("Could not load filters.");
        }
    }

    _sanitizeJournalIds(filterOptions) {
        const valid = new Set((filterOptions.journals || []).map((j) => j.id));
        const sanitize = (ids) => (ids || []).filter((id) => valid.has(id));
        this.state.draftFilters.journal_ids = sanitize(this.state.draftFilters.journal_ids);
        this.state.appliedFilters.journal_ids = sanitize(this.state.appliedFilters.journal_ids);
    }

    async loadData() {
        this.state.loading = true;
        this.state.loadError = null;
        this.charts.cashflow = destroyChart(this.charts.cashflow);
        this.charts.analysis = destroyChart(this.charts.analysis);
        this._analysisChartTabId = null;
        try {
            const payload = await this.orm.call(
                MODEL,
                "get_dashboard_data",
                [this.state.appliedFilters]
            );
            this.state.data = {
                kpis: payload.kpis || [],
                cashflow: payload.cashflow || {},
                charts: payload.charts || {},
                alerts: payload.alerts || [],
                summary_tables: payload.summary_tables || {},
                insights: payload.insights || [],
                risk: payload.risk || [],
                indicator_gauges: payload.indicator_gauges || { groups: [], gauges: [] },
            };
            const tabs = this.summaryTabs;
            if (tabs.length && !tabs.find((t) => t.id === this.state.activeSummaryTab)) {
                this.state.activeSummaryTab = tabs[0].id;
            }
            this.state.loading = false;
            this._scheduleChartRender();
        } catch (e) {
            this.state.loading = false;
            this.state.loadError = e.message || _t("Error loading dashboard.");
            this.notification.add(this.state.loadError, { type: "danger" });
        }
    }

    async onDraftFiltersChanged(patch) {
        Object.assign(this.state.draftFilters, patch);
        if (patch.company_id !== undefined) {
            await this.reloadFilterOptions();
        }
        if (this._initialLoadDone) {
            this._debouncedApply();
        }
    }

    async applyFilters() {
        this._debouncedApply.cancel();
        this.state.appliedFilters = { ...this.state.draftFilters };
        saveStoredFilters(this.state.appliedFilters);
        await this.loadData();
    }

    async resetFilters() {
        const now = DateTime.local();
        this.state.draftFilters = defaultFilters(now);
        this.state.draftFilters.company_id = this.state.filterOptions.company_id;
        clearStoredFilters();
        await this.applyFilters();
    }

    toggleAllKpis() {
        this.state.showAllKpis = !this.state.showAllKpis;
    }

    _analysisChartFingerprint() {
        const key = this.activeChartTabDef.chartKey;
        const d = this.state.data.charts?.[key];
        if (!d?.labels?.length) {
            return `${key}:empty`;
        }
        return `${key}:${d.labels.join("|")}:${d.amounts.join(",")}`;
    }

    _cashflowFingerprint() {
        const cf = this.state.data.cashflow;
        if (!cf?.labels?.length) {
            return "cashflow:empty";
        }
        return `cashflow:${cf.labels.length}:${cf.labels[0]}:${cf.labels[cf.labels.length - 1]}`;
    }

    setChartTab(tabId) {
        this.state.activeChartTab = tabId;
        this._analysisChartTabId = null;
    }

    setSummaryTab(tabId) {
        this.state.activeSummaryTab = tabId;
    }

    kpiDisplay(kpi) {
        if (kpi.format === "count") {
            return String(kpi.count || 0);
        }
        if (kpi.format === "both") {
            return `${this.formatMoney(kpi.amount)} · ${kpi.count || 0}`;
        }
        return this.formatMoney(kpi.amount);
    }

    async onDrilldown(metric, extraDomain = []) {
        try {
            const action = await this.orm.call(
                MODEL,
                "get_drilldown_action",
                [metric, this.state.appliedFilters, extraDomain]
            );
            if (action?.type) {
                this.actionService.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.message || _t("Action not available."), { type: "warning" });
        }
    }

    onKpiClick(kpi) {
        this.onDrilldown(kpi.metric);
    }

    onAlertClick(alert) {
        this.onDrilldown(alert.metric);
    }

    onRiskClick(risk) {
        const extra = risk.extra?.user_id
            ? [["create_uid", "=", risk.extra.user_id]]
            : [];
        this.onDrilldown(risk.metric, extra);
    }

    onChartSegmentClick(index) {
        const tab = this.activeChartTabDef;
        const data = this.activeChartData;
        const extra = [];
        if (tab.hasIds && data?.ids?.[index]) {
            extra.push(["partner_id", "=", data.ids[index]]);
        } else if (tab.id === "bank") {
            const journal = (this.state.filterOptions.journals || []).find(
                (j) => j.name === data?.labels?.[index]
            );
            if (journal) {
                extra.push(["journal_id", "=", journal.id]);
            }
        } else if (tab.id === "branch" && data?.labels?.[index]) {
            const branch = (this.state.filterOptions.branches || []).find(
                (b) => b.name === data.labels[index]
            );
            if (branch) {
                extra.push(["branch_id", "=", branch.id]);
            }
        } else if (tab.id === "operation_type" && data?.labels?.[index]) {
            const mt = this._resolveMoveType(data.labels[index]);
            if (mt) {
                extra.push(["move_type", "=", mt]);
            }
        }
        this.onDrilldown(tab.metric, extra);
    }

    _resolveMoveType(label) {
        const map = {
            debit: "debit",
            credit: "credit",
            deposit: "deposit",
            "credit card": "credit_card",
            "pos liquidation": "credit_card",
        };
        const key = (label || "").toLowerCase();
        for (const [k, v] of Object.entries(map)) {
            if (key.includes(k)) {
                return v;
            }
        }
        return false;
    }

    onSummaryRowClick(row) {
        const extra = [];
        const dim = this.state.activeSummaryTab;
        if (dim === "bank" && row.id) {
            extra.push(["journal_id", "=", row.id]);
        } else if (dim === "branch" && row.id) {
            extra.push(["branch_id", "=", row.id]);
        } else if (dim === "operation_type" && row.id) {
            extra.push(["move_type", "=", row.id]);
        } else if (dim === "state" && row.id) {
            extra.push(["state", "=", row.id]);
        } else if (dim === "partner" && row.id) {
            extra.push(["partner_id", "=", row.id]);
        }
        this.onDrilldown("period_inflow", extra);
    }

    summaryBarPct(row) {
        return Math.min(100, (Math.abs(row.net) / this.maxSummaryNet) * 100);
    }

    async renderAllCharts() {
        if (this.state.loading) {
            return;
        }
        await loadChartJs();
        await this.renderCashflowChart();
        await this.renderAnalysisChart();
    }

    async renderCashflowChart() {
        if (this.state.loading) {
            return;
        }
        await loadChartJs();
        if (typeof Chart === "undefined") {
            return;
        }
        const canvas = this.cashflowRef.el;
        const cf = this.state.data.cashflow;
        if (!canvas || !cf?.labels?.length) {
            this.charts.cashflow = destroyChart(this.charts.cashflow);
            return;
        }
        const labels = cf.labels.map((iso) => formatIsoDate(iso));
        const trend = this._cashflowTrendSeries(cf.inflows, cf.outflows);
        if (this.charts.cashflow) {
            const chart = this.charts.cashflow;
            chart.data.labels = labels;
            chart.data.datasets[0].data = cf.inflows;
            chart.data.datasets[1].data = cf.outflows;
            chart.data.datasets[2].data = cf.cumulative;
            chart.data.datasets[3].data = trend;
            chart.update("none");
            return;
        }
        const ctx = canvas.getContext("2d");
        this.charts.cashflow = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: this.chartLabels.inflows,
                        data: cf.inflows,
                        backgroundColor: CHART_COLORS.inflow,
                        borderColor: "transparent",
                        borderRadius: 4,
                        borderSkipped: false,
                        order: 2,
                    },
                    {
                        label: this.chartLabels.outflows,
                        data: cf.outflows,
                        backgroundColor: CHART_COLORS.outflow,
                        borderColor: "transparent",
                        borderRadius: 4,
                        borderSkipped: false,
                        order: 2,
                    },
                    {
                        label: this.chartLabels.cumulative,
                        data: cf.cumulative,
                        type: "line",
                        borderColor: CHART_COLORS.cumulative,
                        backgroundColor: CHART_COLORS.cumulativeFill,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 2,
                        yAxisID: "y1",
                        order: 1,
                    },
                    {
                        label: this.chartLabels.trend,
                        data: trend,
                        type: "line",
                        borderColor: CHART_COLORS.trend,
                        borderDash: [4, 3],
                        backgroundColor: "transparent",
                        fill: false,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        borderWidth: 1.5,
                        yAxisID: "y",
                        order: 0,
                    },
                ],
            },
            options: baseChartOptions({
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "top",
                        align: "start",
                        labels: { boxWidth: 10, boxHeight: 10, padding: 14 },
                    },
                    tooltip: { mode: "index", intersect: false },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 },
                    },
                    y: { beginAtZero: true, stacked: false },
                    y1: {
                        position: "right",
                        grid: { drawOnChartArea: false },
                        ticks: { color: CHART_COLORS.tick },
                    },
                },
            }),
        });
    }

    async renderAnalysisChart() {
        if (this.state.loading) {
            return;
        }
        await loadChartJs();
        if (typeof Chart === "undefined") {
            return;
        }
        const canvas = this.analysisChartRef.el;
        const tab = this.activeChartTabDef;
        const chartData = this.activeChartData;
        if (!canvas) {
            return;
        }
        if (!this.hasActiveChartData) {
            this.charts.analysis = destroyChart(this.charts.analysis);
            this._analysisChartTabId = null;
            return;
        }
        const chartType = tab.type === "doughnut" ? "doughnut" : "bar";
        const horizontal = chartData.labels.length > 5;
        const canUpdateInPlace =
            this.charts.analysis &&
            this._analysisChartTabId === tab.id &&
            this.charts.analysis.config.type === chartType &&
            (chartType === "doughnut" ||
                this.charts.analysis.options.indexAxis === (horizontal ? "y" : "x"));

        if (canUpdateInPlace) {
            const chart = this.charts.analysis;
            chart.data.labels = chartData.labels;
            chart.data.datasets[0].data = chartData.amounts;
            if (chartType === "bar") {
                chart.data.datasets[0].backgroundColor = paletteColors(chartData.labels.length);
            }
            chart.update("none");
            return;
        }

        this.charts.analysis = destroyChart(this.charts.analysis);
        this._analysisChartTabId = tab.id;
        const tabMeta = this.chartTabs.find((t) => t.id === tab.id);
        const title = tabMeta?.label || tab.id;
        const onSelect = (idx) => this.onChartSegmentClick(idx);

        if (tab.type === "doughnut") {
            this.charts.analysis = new Chart(canvas.getContext("2d"), {
                type: "doughnut",
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        data: chartData.amounts,
                        backgroundColor: paletteColors(chartData.labels.length),
                        borderWidth: 0,
                        hoverOffset: 6,
                    }],
                },
                options: baseChartOptions({
                    cutout: "62%",
                    plugins: { legend: { position: "right", align: "center" } },
                }),
            });
        } else {
            this.charts.analysis = new Chart(canvas.getContext("2d"), {
                type: "bar",
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: title || tab.label,
                        data: chartData.amounts,
                        backgroundColor: paletteColors(chartData.labels.length),
                        borderRadius: 6,
                        borderSkipped: false,
                    }],
                },
                options: baseChartOptions({
                    indexAxis: horizontal ? "y" : "x",
                    plugins: { legend: { display: false } },
                }),
            });
        }
        attachChartDrilldown(this.charts.analysis, onSelect);
    }
}

registry.category("actions").add("gn_banks_dashboard", GnBanksTreasuryDashboard);
