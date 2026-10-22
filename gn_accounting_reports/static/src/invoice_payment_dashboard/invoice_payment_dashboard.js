/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";
import { InvPayFilterPanel } from "./filter_panel";
import { InvPayKpiCard } from "./kpi_card";
import { InvPayDataTable } from "./data_table";
import { InvPayChartPanel } from "./chart_panel";
import { InvPayAnalysisChartCard } from "./analysis_chart_card";
import { InvPayInsightsPanel, InvPayDetailPanel } from "./panels";
import { user } from "@web/core/user";
import { DEFAULT_COLUMNS, TABS, defaultFilters, formatDateTime, formatMoney, formatPeriodChip, formatPct, PRIMARY_KPI_KEYS, SECONDARY_KPI_KEYS } from "./format_utils";

const SERVICE = "gn.accounting.invoice.payment.service";
const EXPORT_MODEL = "gn.accounting.invoice.payment.export";

const CHART_KEY_MAP = {
    timeline: "timeline",
    advisor: "advisor_ranking",
    clients: "client_ranking",
    bank: "bank_distribution",
    categ: "category_distribution",
    status: "status_distribution",
};

export class InvoicePaymentDashboard extends Component {
    static template = "gn_accounting_reports.InvoicePaymentDashboard";
    static props = { ...standardActionServiceProps };
    static components = {
        InvPayFilterPanel,
        InvPayKpiCard,
        InvPayDataTable,
        InvPayChartPanel,
        InvPayAnalysisChartCard,
        InvPayInsightsPanel,
        InvPayDetailPanel,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.menuService = useService("menu");
        this.notification = useService("notification");
        this._loadSeq = 0;
        this._searchTimeout = null;
        this.tabs = TABS;
        this.state = useState({
            loading: true,
            refreshing: false,
            loadError: null,
            filtersExpanded: false,
            filtersCollapsed: false,
            headerCompact: false,
            timelineBase: "payment",
            timelineScope: "period",
            activeTab: "summary",
            filterOptions: {},
            draftFilters: defaultFilters(),
            appliedFilters: defaultFilters(),
            header: {},
            kpis: { cards: [] },
            charts: {},
            insights: [],
            aging: { buckets: {} },
            table: { rows: [], totals: {}, page: 1, total_pages: 1, page_size: 50, meta: {} },
            overdueTable: { rows: [], totals: {}, page: 1, total_pages: 1, page_size: 50 },
            overdueFilterMode: "all_balance",
            upcomingDays: 7,
            expandedRows: {},
            expandedGroups: {},
            currency: {},
            thresholds: {},
            columns: [...DEFAULT_COLUMNS],
            density: "comfortable",
            tableSearch: "",
            groupBy: "",
            detail: null,
            detailOpen: false,
            exporting: false,
            showSaveView: false,
            saveViewName: "",
        });
        onWillStart(() => this._init());
        this._onScroll = () => {
            const el = this._scrollEl;
            this.state.headerCompact = el ? el.scrollTop > 48 : false;
        };
        onMounted(() => {
            this._scrollEl = document.querySelector(".o_inv_pay_dashboard");
            this._scrollEl?.addEventListener("scroll", this._onScroll, { passive: true });
        });
        onWillUnmount(() => {
            this._scrollEl?.removeEventListener("scroll", this._onScroll);
        });
    }

    get headerClass() {
        return this.state.headerCompact ? "o_inv_pay_header--compact" : "";
    }

    get primaryKpiCards() {
        const byKey = Object.fromEntries((this.state.kpis.cards || []).map((c) => [c.key, c]));
        return PRIMARY_KPI_KEYS.map((k) => byKey[k]).filter(Boolean);
    }

    get secondaryKpiCards() {
        const byKey = Object.fromEntries((this.state.kpis.cards || []).map((c) => [c.key, c]));
        return SECONDARY_KPI_KEYS.map((k) => byKey[k]).filter(Boolean);
    }

    get recoveryCard() {
        return (this.state.kpis.cards || []).find((c) => c.key === "recovery_pct") || null;
    }

    get punctualityCard() {
        return (this.state.kpis.cards || []).find((c) => c.key === "punctuality_pct") || null;
    }

    get paidCard() {
        return (this.state.kpis.cards || []).find((c) => c.key === "total_paid") || null;
    }

    get pendingCard() {
        return (this.state.kpis.cards || []).find((c) => c.key === "total_pending") || null;
    }

    get timelineChartConfig() {
        const charts = this.state.charts || {};
        if (this.state.timelineScope === "historical") {
            return charts.timeline_historical || charts.timeline || {};
        }
        const base = this.state.timelineBase;
        if (base === "invoice") return charts.timeline_invoice || charts.timeline || {};
        if (base === "accounting") return charts.timeline_accounting || charts.timeline || {};
        return charts.timeline || {};
    }

    get timelineScopeHint() {
        if (this.state.timelineScope === "historical") {
            return _t("Tendencia histórica: pagos registrados en fechas anteriores al período.");
        }
        const hints = {
            payment: _t("Base de pago: cobros y facturas asociadas a pagos del período seleccionado."),
            invoice: _t("Base de factura: montos agrupados por fecha de emisión de la factura."),
            accounting: _t("Comparativo contable: facturación y pagos dentro del rango de fechas de factura."),
        };
        return hints[this.state.timelineBase] || "";
    }

    get filterChips() {
        const f = this.state.appliedFilters;
        const chips = [];
        chips.push(formatPeriodChip(f.date_from, f.date_to) || _t("Período"));
        const co = (this.state.filterOptions.companies || []).find((c) => c.id === f.company_id);
        if (co) chips.push(co.name);
        if (f.branch_ids?.length) {
            chips.push(f.branch_ids.length === 1 ? _t("1 sucursal") : _t("%s sucursales", f.branch_ids.length));
        } else {
            chips.push(_t("Todas las sucursales"));
        }
        if (f.user_ids?.length) {
            chips.push(f.user_ids.length === 1 ? _t("1 asesor") : _t("%s asesores", f.user_ids.length));
        } else {
            chips.push(_t("Todos los asesores"));
        }
        const stateLabels = { all: _t("Todos los estados"), paid: _t("Pagadas"), partial: _t("Parciales"), not_paid: _t("Pendientes") };
        chips.push(stateLabels[f.payment_state] || f.payment_state);
        if (f.show_pending_invoices) chips.push(_t("Incluir pendientes"));
        if (f.overdue_only) chips.push(_t("Solo vencidas"));
        return chips;
    }

    get hasModifiedFilters() {
        const d = JSON.stringify(this.state.draftFilters);
        const a = JSON.stringify(this.state.appliedFilters);
        return d !== a || this.state.header?.has_filters;
    }

    setTimelineBase(base) {
        this.state.timelineBase = base;
    }

    setTimelineScope(scope) {
        this.state.timelineScope = scope;
    }

    expandFilters() {
        this.state.filtersCollapsed = false;
    }

    get formatDateTime() {
        return formatDateTime;
    }

    get recoveryDeltaLabel() {
        const d = this.recoveryCard?.delta;
        if (!d || d.pp === undefined || d.pp === null) return "—";
        const arrow = d.pp >= 0 ? "▲ +" : "▼ ";
        return `${arrow}${Math.abs(d.pp).toFixed(1)} pp`;
    }

    get formatMoneyBound() {
        return (v) => formatMoney(v, this.state.currency.id);
    }

    get formatPct() {
        return formatPct;
    }

    get recoveryGaugeConfig() {
        return { value: this.state.kpis.recovery_index || 0 };
    }

    get overdueTableTitle() {
        if (this.state.overdueFilterMode === "overdue_only") {
            return _t("Facturas vencidas");
        }
        if (this.state.overdueFilterMode === "upcoming_due") {
            return _t("Próximas a vencer (%s días)", this.state.upcomingDays);
        }
        return _t("Cartera con saldo");
    }

    get overdueColumns() {
        return [
            "collection_priority", "customer", "invoice_number", "invoice_date", "due_date",
            "days_overdue", "amount_total", "balance_pending", "advisor", "branch",
        ];
    }

    get detailViewMode() {
        return this.state.appliedFilters.view_mode || "by_payment";
    }

    get agingTotalPending() {
        return this.state.aging.total_pending || 0;
    }

    agingBucketPct(bk) {
        const total = this.agingTotalPending || 1;
        const amount = this.state.aging.buckets?.[bk]?.amount || 0;
        return `${((amount / total) * 100).toFixed(1)}%`;
    }

    agingBucketBarPct(bk) {
        const total = this.agingTotalPending || 1;
        const amount = this.state.aging.buckets?.[bk]?.amount || 0;
        return Math.min(100, (amount / total) * 100);
    }

    _columnsStorageKey() {
        return `inv_pay_columns_${user.userId}`;
    }

    _loadColumnPrefs() {
        try {
            const raw = localStorage.getItem(this._columnsStorageKey());
            if (raw) {
                const cols = JSON.parse(raw);
                if (Array.isArray(cols) && cols.length >= 3) {
                    this.state.columns = cols;
                }
            }
        } catch { /* ignore */ }
    }

    _saveColumnPrefs(cols) {
        try {
            localStorage.setItem(this._columnsStorageKey(), JSON.stringify(cols));
        } catch { /* ignore */ }
    }

    async _reloadTable(page = 1) {
        const t = this.state.table;
        const result = await this.orm.call(SERVICE, "get_table_page", [
            this.state.appliedFilters, page, t.page_size || 50,
            t.sort_by || "payment_date_raw", t.sort_dir || "desc",
            this.state.tableSearch, this.state.groupBy || null,
        ]);
        this.state.table = result;
    }

    async _reloadOverdue(page = 1) {
        const filters = {
            ...this.state.appliedFilters,
            overdue_filter_mode: this.state.overdueFilterMode,
            upcoming_days: this.state.upcomingDays,
        };
        const result = await this.orm.call(SERVICE, "get_overdue_page", [
            filters, page, this.state.overdueTable.page_size || 50,
            "collection_priority_score", "desc",
        ]);
        this.state.overdueTable = result;
        if (result.aging) {
            this.state.aging = result.aging;
        }
    }

    async onViewModeChange(mode) {
        this.state.draftFilters.view_mode = mode;
        this.state.appliedFilters = { ...this.state.draftFilters, view_mode: mode };
        this.state.expandedRows = {};
        await this._reloadTable(1);
    }

    async onOverdueFilterChange(mode) {
        this.state.overdueFilterMode = mode;
        await this._reloadOverdue(1);
    }

    async onUpcomingDaysChange(days) {
        this.state.upcomingDays = days;
        if (this.state.overdueFilterMode === "upcoming_due") {
            await this._reloadOverdue(1);
        }
    }

    async onPageSizeChange(size) {
        this.state.table = { ...this.state.table, page_size: size };
        await this._reloadTable(1);
    }

    async onOverduePageSizeChange(size) {
        this.state.overdueTable = { ...this.state.overdueTable, page_size: size };
        await this._reloadOverdue(1);
    }

    async onGoToPage(page) {
        await this._reloadTable(page);
    }

    async onOverduePageChange(page) {
        await this._reloadOverdue(page);
    }

    resetTableToolbar() {
        this.state.tableSearch = "";
        this.state.groupBy = "";
        this.state.density = "comfortable";
        this.state.columns = [...DEFAULT_COLUMNS];
        this._saveColumnPrefs(this.state.columns);
        this._reloadTable(1);
    }

    onToggleGroup(name) {
        const cur = this.state.expandedGroups[name];
        this.state.expandedGroups[name] = cur === false ? true : false;
    }

    onExpandRow(invoiceId) {
        this.state.expandedRows[invoiceId] = !this.state.expandedRows[invoiceId];
    }

    onChartApplyFilter(drill) {
        if (drill?.tab) this.setTab(drill.tab);
        if (drill?.filter && Object.keys(drill.filter).length) {
            Object.assign(this.state.draftFilters, drill.filter);
            this.applyFilters();
        }
    }

    onChartViewDetail(chartKey) {
        this.setTab("detail");
        this.notification.add(_t("Vista de detalle abierta"), { type: "info" });
    }

    onChartExportData(chartKey, chartData) {
        const rows = (chartData.labels || []).map((label, i) => ({
            nombre: chartData.fullLabels?.[i] || label,
            valor: chartData.data?.[i] ?? 0,
        }));
        const csv = ["nombre,valor", ...rows.map((r) => `"${r.nombre}",${r.valor}`)].join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `${chartKey}.csv`;
        link.click();
    }

    setTab(tabId) {
        this.state.activeTab = tabId;
        if (tabId === "overdue") {
            this._reloadOverdue(1);
        }
    }

    get tableMode() {
        return this.detailViewMode === "consolidated" ? "consolidated" : "flat";
    }

    get bucketKeys() {
        return ["current", "1_30", "31_60", "61_90", "90_plus"];
    }

    get showPeriodHint() {
        return Boolean(this.state.header?.filters_by_payment_date);
    }

    async goBack() {
        try {
            await this.action.restore();
        } catch {
            const app = this.menuService.getCurrentApp();
            if (app) {
                await this.menuService.selectMenu(app);
            }
        }
    }

    alignWithAccounting() {
        const f = this.state.draftFilters;
        f.invoice_date_from = f.date_from;
        f.invoice_date_to = f.date_to;
        f.payment_period = "this_year";
        f.show_pending_invoices = true;
        this.applyFilters();
        this.notification.add(
            _t("Filtros alineados con el listado de Contabilidad (por fecha de factura)."),
            { type: "info" }
        );
    }

    agingBucketLabel(bk) {
        return this.state.aging.buckets?.[bk]?.label || "";
    }

    agingBucketAmount(bk) {
        const amount = this.state.aging.buckets?.[bk]?.amount;
        if (amount === null || amount === undefined) {
            return formatMoney(0, this.state.currency.id);
        }
        return formatMoney(amount, this.state.currency.id);
    }

    agingBucketCount(bk) {
        return this.state.aging.buckets?.[bk]?.count ?? 0;
    }

    async _init() {
        try {
            const options = await this.orm.call(SERVICE, "get_filter_options", []);
            this.state.filterOptions = options;
            if (options.company_id) {
                this.state.draftFilters.company_id = options.company_id;
                this.state.appliedFilters.company_id = options.company_id;
            }
            if (options.default_page_size) {
                this.state.table.page_size = options.default_page_size;
                this.state.overdueTable.page_size = options.default_page_size;
            }
            this._loadColumnPrefs();
            await this._loadDashboard();
        } catch (e) {
            this.state.loadError = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    async _loadDashboard(notify = false) {
        const seq = ++this._loadSeq;
        this.state.refreshing = true;
        this.state.loadError = null;
        try {
            const data = await this.orm.call(SERVICE, "get_dashboard_init", [this.state.appliedFilters]);
            if (seq !== this._loadSeq) return;
            if (!data?.success) throw new Error(data?.error || _t("Error al cargar el tablero"));
            this.state.header = data.header || {};
            this.state.kpis = data.kpis || { cards: [] };
            this.state.charts = data.charts || {};
            this.state.insights = data.insights || [];
            this.state.aging = data.aging || {};
            this.state.table = data.table || {};
            this.state.currency = data.currency || {};
            this.state.thresholds = data.thresholds || {};
            if (notify) {
                this.notification.add(_t("Reporte actualizado"), { type: "success" });
            }
            if (!this._initialLoadDone) {
                this._initialLoadDone = true;
                this.state.filtersCollapsed = true;
            }
        } catch (e) {
            if (seq === this._loadSeq) {
                this.state.loadError = e.message || String(e);
                this.notification.add(this.state.loadError, { type: "danger" });
            }
        } finally {
            if (seq === this._loadSeq) {
                this.state.refreshing = false;
            }
        }
    }

    onFilterChange(partial) {
        if (partial.company_id !== undefined) {
            partial.company_id = parseInt(partial.company_id, 10);
        }
        Object.assign(this.state.draftFilters, partial);
        if (partial.company_id) {
            this.state.draftFilters.branch_ids = [];
            this.state.draftFilters.user_ids = [];
            this.state.draftFilters.journal_ids = [];
        }
    }

    async applyFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.state.filtersCollapsed = true;
        this.state.filtersExpanded = false;
        await this._loadDashboard();
    }

    onPresetChange(preset) {
        this.state.draftFilters.payment_period = preset;
        if (preset !== "custom") {
            this.onFilterChange({ payment_period: preset });
            this.applyFilters();
        }
    }

    resetFilters() {
        const f = defaultFilters();
        f.company_id = this.state.filterOptions.company_id || f.company_id;
        this.state.draftFilters = f;
        this.state.appliedFilters = { ...f };
        this.state.filtersCollapsed = false;
        this._loadDashboard();
    }

    async refresh() {
        if (this.state.refreshing) return;
        await this._loadDashboard(true);
        if (this.state.activeTab === "overdue") {
            await this._reloadOverdue(this.state.overdueTable.page || 1);
        }
    }

    async onSort(col) {
        const t = this.state.table;
        const dir = t.sort_by === col && t.sort_dir === "desc" ? "asc" : "desc";
        this.state.table = { ...t, sort_by: col, sort_dir: dir };
        await this._reloadTable(t.page || 1);
    }

    async onPageChange(page) {
        await this._reloadTable(page);
    }

    onSearch(text) {
        this.state.tableSearch = text;
        clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(async () => {
            const t = this.state.table;
            const result = await this.orm.call(SERVICE, "get_table_page", [
                this.state.appliedFilters, 1, t.page_size, t.sort_by, t.sort_dir,
                text, this.state.groupBy,
            ]);
            this.state.table = result;
        }, 400);
    }

    async onGroupBy(value) {
        this.state.groupBy = value;
        this.state.expandedGroups = {};
        await this._reloadTable(1);
    }

    onColumnsChange(cols) {
        this.state.columns = cols;
        this._saveColumnPrefs(cols);
    }

    async onRowClick(row) {
        const detail = await this.orm.call(SERVICE, "get_record_detail", [
            row.invoice_id, row.payment_id || null,
        ]);
        this.state.detail = detail;
        this.state.detailOpen = true;
    }

    closeDetail() {
        this.state.detailOpen = false;
    }

    onOpenRecord(type) {
        const act = this.state.detail?.actions?.[type];
        if (!act) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: act.res_model,
            res_id: act.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onInsightAction(action) {
        if (action?.tab) {
            this.setTab(action.tab);
        }
        if (action?.type === "filter" || action?.filters) {
            Object.assign(this.state.draftFilters, action.filters || {});
            this.applyFilters();
        } else if (action?.type === "tab" && action.tab) {
            this.setTab(action.tab);
        }
    }

    async exportFormat(fmt) {
        this.state.exporting = true;
        try {
            const result = await this.orm.call(EXPORT_MODEL, "export_data", [
                this.state.appliedFilters, fmt, {},
            ]);
            const link = document.createElement("a");
            link.href = `data:${result.mimetype};base64,${result.data}`;
            link.download = result.filename;
            link.click();
            this.notification.add(_t("Exportación completada"), { type: "success" });
        } catch (e) {
            const message = e.data?.message || e.message || String(e);
            this.notification.add(message, { type: "danger", sticky: true });
        } finally {
            this.state.exporting = false;
        }
    }

    async saveCurrentView() {
        const name = this.state.saveViewName?.trim();
        if (!name) return;
        await this.orm.call(SERVICE, "save_filter_view", [name, this.state.appliedFilters, false]);
        this.state.showSaveView = false;
        this.state.saveViewName = "";
        this.state.filterOptions = await this.orm.call(SERVICE, "get_filter_options", []);
        this.notification.add(_t("Vista guardada"), { type: "success" });
    }

    loadSavedView(view) {
        Object.assign(this.state.draftFilters, view.filters || {});
        this.applyFilters();
    }

    toggleFiltersExpand() {
        this.state.filtersExpanded = !this.state.filtersExpanded;
    }

    onDensityChange(density) {
        this.state.density = density;
    }

    onChartClick(chartKey, dataIndex) {
        let config = this.state.charts[chartKey];
        if (chartKey === "timeline") {
            config = this.timelineChartConfig;
        }
        if (!config?.drilldown?.[dataIndex]) {
            return;
        }
        const drill = config.drilldown[dataIndex];
        if (drill.tab) {
            this.setTab(drill.tab);
        }
        if (drill.filter && Object.keys(drill.filter).length) {
            Object.assign(this.state.draftFilters, drill.filter);
            this.applyFilters();
            this.notification.add(_t("Filtro aplicado desde gráfico"), { type: "info" });
        }
    }

    get onChartClickBound() {
        return this.onChartClick.bind(this);
    }
}
