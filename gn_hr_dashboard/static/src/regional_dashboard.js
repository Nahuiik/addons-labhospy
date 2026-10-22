/** @odoo-module **/

/**
 * Vista regional (KPIs + gráficos). Filtros: país, año, mes, rango de fechas.
 * Si hay fecha desde/hasta, tienen prioridad sobre año/mes para el período de KPIs.
 */

import { _t } from "@web/core/l10n/translation";
import { formatCurrency } from "@web/core/currency";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { loadJS } from "@web/core/assets";
import {
    Component,
    onWillStart,
    useRef,
    useEffect,
    onWillUnmount,
    useState,
} from "@odoo/owl";

const FILTERS_STORAGE_KEY = "gn_hr_dashboard.regional.filters";

const INCIDENT_LABEL_KEYS = {
    late: _t("Tardanzas"),
    overtime: _t("Horas extra"),
    absence: _t("Ausencias"),
    incomplete: _t("Jornada incompleta"),
    error: _t("Error"),
};

function monthNames() {
    return [
        _t("Enero"),
        _t("Febrero"),
        _t("Marzo"),
        _t("Abril"),
        _t("Mayo"),
        _t("Junio"),
        _t("Julio"),
        _t("Agosto"),
        _t("Septiembre"),
        _t("Octubre"),
        _t("Noviembre"),
        _t("Diciembre"),
    ];
}

function todayParts() {
    const d = new Date();
    return { y: d.getFullYear(), m: d.getMonth() + 1 };
}

function toInputDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

function loadSavedFilters() {
    try {
        const raw = sessionStorage.getItem(FILTERS_STORAGE_KEY);
        if (!raw) {
            return null;
        }
        const saved = JSON.parse(raw);
        return saved && typeof saved === "object" ? saved : null;
    } catch {
        return null;
    }
}

function saveFiltersToStorage(filters) {
    try {
        sessionStorage.setItem(
            FILTERS_STORAGE_KEY,
            JSON.stringify({
                country_id: filters.country_id ?? "",
                year: filters.year,
                month: filters.month,
                date_from: filters.date_from ?? "",
                date_to: filters.date_to ?? "",
            })
        );
    } catch {
        /* ignore quota / private mode */
    }
}

export class RegionalHrDashboard extends Component {
    static template = "gn_hr_dashboard.RegionalDashboard";
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        const { y, m } = todayParts();
        const saved = loadSavedFilters();
        this.state = useState({
            initialLoading: true,
            refreshing: false,
            loadError: null,
            filters: {
                country_id: saved?.country_id ?? "",
                year: saved?.year ?? y,
                month: saved?.month ?? m,
                date_from: saved?.date_from ?? "",
                date_to: saved?.date_to ?? "",
            },
            yearOptions: [],
        });

        this.headcountChartRef = useRef("headcountChart");
        this.payrollTrendRef = useRef("payrollTrendChart");
        this.incidentChartRef = useRef("incidentChart");
        this.movementChartRef = useRef("movementChart");
        this.absenceByTypeChartRef = useRef("absenceByTypeChart");
        this.diversityChartRef = useRef("diversityChart");
        this.tenureBandsChartRef = useRef("tenureBandsChart");
        this.payrollPerEmpTrendRef = useRef("payrollPerEmpTrendChart");
        this.contractTypeLineRef = useRef("contractTypeLineChart");
        this.contractTypePieRef = useRef("contractTypePieChart");

        this._charts = [];
        this.data = null;

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            const years = [];
            for (let i = y - 5; i <= y + 1; i++) {
                years.push(i);
            }
            this.state.yearOptions = years;
            await this._fetchData();
        });

        useEffect(
            () => {
                if (!this.state.initialLoading && !this.state.refreshing && this.data) {
                    this._destroyCharts();
                    this._renderCharts();
                }
            },
            () => [this.state.initialLoading, this.state.refreshing]
        );

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    _destroyCharts() {
        for (const c of this._charts) {
            try {
                c.destroy();
            } catch {
                /* ignore */
            }
        }
        this._charts = [];
    }

    _rpcPayload() {
        const f = this.state.filters;
        const payload = {
            year: f.year,
            month: f.month,
        };
        if (f.country_id) {
            payload.country_id = parseInt(f.country_id, 10);
        }
        if (f.date_from && f.date_to) {
            payload.date_from = f.date_from;
            payload.date_to = f.date_to;
        }
        return payload;
    }

    _rpcErrorMessage(error) {
        const d = error?.data;
        if (d?.message) {
            if (typeof d.message === "string") {
                return d.message;
            }
            if (Array.isArray(d.message) && d.message[0]) {
                return String(d.message[0]);
            }
        }
        if (error?.message) {
            return String(error.message);
        }
        return _t("Error al cargar los datos.");
    }

    async _fetchData() {
        const first = !this.data;
        if (first) {
            this.state.initialLoading = true;
            this.state.loadError = null;
        } else {
            this.state.refreshing = true;
        }
        this._destroyCharts();
        try {
            this.data = await rpc("/gn_hr_dashboard/regional", this._rpcPayload());
            const af = this.data.applied_filters || {};
            if (af.period_mode === "month" && af.year && af.month) {
                this.state.filters.year = af.year;
                this.state.filters.month = af.month;
            }
            if (af.period_mode === "range" && af.date_from && af.date_to) {
                this.state.filters.date_from = af.date_from;
                this.state.filters.date_to = af.date_to;
            }
            this.state.loadError = null;
            saveFiltersToStorage(this.state.filters);
        } catch (e) {
            const msg = this._rpcErrorMessage(e);
            if (first) {
                this.state.loadError = msg;
                this.data = null;
            }
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.initialLoading = false;
            this.state.refreshing = false;
        }
    }

    async onRetryLoad() {
        this.state.loadError = null;
        await this._fetchData();
    }

    countryOptions() {
        return this.data?.filter_options?.countries || [];
    }

    monthName(mi) {
        const names = monthNames();
        return names[mi - 1] || "";
    }

    incidentLabel(type) {
        return INCIDENT_LABEL_KEYS[type] || type;
    }

    async onApplyFilters() {
        await this._fetchData();
    }

    onClearDateRange() {
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
    }

    periodDescription() {
        if (!this.data || !this.data.applied_filters) {
            return "";
        }
        const af = this.data.applied_filters;
        if (af.period_mode === "range" && af.date_from && af.date_to) {
            return `${af.date_from} → ${af.date_to}`;
        }
        if (af.year && af.month) {
            return `${this.monthName(af.month)} ${af.year}`;
        }
        return "";
    }

    kpiPeriodHint() {
        const af = this.data?.applied_filters;
        if (af?.period_mode === "range") {
            return _t("período seleccionado");
        }
        return _t("mes seleccionado");
    }

    turnoverHint() {
        return _t("12 meses hasta fin de período");
    }

    chartPayrollHint() {
        return _t("6 meses hasta fin de período");
    }

    chartMovementHint() {
        return _t("12 meses hasta fin de período");
    }

    chartIncidentHint() {
        return this.kpiPeriodHint();
    }

    _renderCharts() {
        this._renderPayrollPerEmpTrendChart();
        this._renderAbsenceByTypeChart();
        this._renderDiversityChart();
        this._renderTenureBandsChart();
        this._renderHeadcountChart();
        this._renderPayrollTrendChart();
        this._renderIncidentChart();
        this._renderMovementChart();
        this._renderContractTypeLineChart();
        this._renderContractTypePieChart();
    }

    _renderHeadcountChart() {
        const el = this.headcountChartRef.el;
        if (!el) {
            return;
        }
        const ctx = el.getContext("2d");
        const items = this.data.headcount_by_company || [];
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"];
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: items.map((i) => i.company),
                datasets: [
                    {
                        label: _t("Headcount"),
                        data: items.map((i) => i.count),
                        backgroundColor: items.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
        this._charts.push(chart);
    }

    _renderPayrollTrendChart() {
        const el = this.payrollTrendRef.el;
        if (!el) {
            return;
        }
        const ctx = el.getContext("2d");
        const trend = this.data.payroll_trend || [];
        const companyNames = this.data.company_names || [];
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5"];
        const datasets = companyNames.map((name, idx) => ({
            label: name,
            data: trend.map((m) => m[name] || 0),
            borderColor: colors[idx % colors.length],
            backgroundColor: colors[idx % colors.length] + "33",
            fill: true,
            tension: 0.3,
        }));
        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: trend.map((m) => m.month),
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { beginAtZero: true } },
            },
        });
        this._charts.push(chart);
    }

    _renderIncidentChart() {
        const el = this.incidentChartRef.el;
        if (!el) {
            return;
        }
        const ctx = el.getContext("2d");
        const dist = this.data.incident_distribution || [];
        const colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"];
        const chart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: dist.map((d) => this.incidentLabel(d.type)),
                datasets: [
                    {
                        data: dist.map((d) => d.count),
                        backgroundColor: dist.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
        this._charts.push(chart);
    }

    _renderMovementChart() {
        const el = this.movementChartRef.el;
        if (!el) {
            return;
        }
        const ctx = el.getContext("2d");
        const trend = this.data.movement_trend || [];
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: trend.map((m) => m.month),
                datasets: [
                    {
                        type: "bar",
                        label: _t("Altas"),
                        data: trend.map((m) => m.hires),
                        backgroundColor: "rgba(25, 135, 84, 0.7)",
                        yAxisID: "y",
                    },
                    {
                        type: "bar",
                        label: _t("Bajas"),
                        data: trend.map((m) => m.departures),
                        backgroundColor: "rgba(220, 53, 69, 0.7)",
                        yAxisID: "y",
                    },
                    {
                        type: "line",
                        label: _t("Headcount (fin de mes)"),
                        data: trend.map((m) => m.headcount_end ?? 0),
                        borderColor: "#6f42c1",
                        backgroundColor: "rgba(111, 66, 193, 0.15)",
                        yAxisID: "y1",
                        tension: 0.3,
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: {
                    x: { stacked: false },
                    y: {
                        position: "left",
                        beginAtZero: true,
                        ticks: { precision: 0 },
                    },
                    y1: {
                        position: "right",
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderAbsenceByTypeChart() {
        const el = this.absenceByTypeChartRef.el;
        if (!el) {
            return;
        }
        const items = this.data.absence_by_type || [];
        if (!items.length) {
            return;
        }
        const ctx = el.getContext("2d");
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"];
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: items.map((d) => d.name),
                datasets: [
                    {
                        label: _t("Días"),
                        data: items.map((d) => d.days),
                        backgroundColor: items.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true },
                    y: { ticks: { autoSkip: false } },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderDiversityChart() {
        const el = this.diversityChartRef.el;
        if (!el) {
            return;
        }
        const items = this.data.diversity_by_sex || [];
        if (!items.length) {
            return;
        }
        const ctx = el.getContext("2d");
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"];
        const chart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: items.map((d) => d.label),
                datasets: [
                    {
                        data: items.map((d) => d.count),
                        backgroundColor: items.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
        this._charts.push(chart);
    }

    _renderTenureBandsChart() {
        const el = this.tenureBandsChartRef.el;
        if (!el) {
            return;
        }
        const bands = this.data.tenure_bands || [];
        if (!bands.length) {
            return;
        }
        const ctx = el.getContext("2d");
        const labels = bands.map((b) => this.tenureBandLabel(b.band));
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"];
        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: _t("Empleados"),
                        data: bands.map((b) => b.count),
                        backgroundColor: labels.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderPayrollPerEmpTrendChart() {
        const el = this.payrollPerEmpTrendRef.el;
        if (!el) {
            return;
        }
        const ctx = el.getContext("2d");
        const trend = this.data.payroll_per_employee_trend || [];
        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: trend.map((m) => m.month),
                datasets: [
                    {
                        label: _t("Costo bruto / empleado"),
                        data: trend.map((m) =>
                            m.value === null || m.value === undefined
                                ? null
                                : m.value
                        ),
                        borderColor: "#198754",
                        backgroundColor: "rgba(25, 135, 84, 0.2)",
                        fill: true,
                        tension: 0.3,
                        spanGaps: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { beginAtZero: true } },
            },
        });
        this._charts.push(chart);
    }

    _renderContractTypeLineChart() {
        const el = this.contractTypeLineRef.el;
        if (!el) {
            return;
        }
        const payload = this.data.contract_type_monthly || {};
        const months = payload.months || [];
        const series = payload.series || [];
        if (!series.length) {
            return;
        }
        const ctx = el.getContext("2d");
        const palette = [
            "#4472C4",
            "#ED7D31",
            "#A5A5A5",
            "#FFC000",
            "#5B9BD5",
            "#70AD47",
            "#9E480E",
            "#264478",
        ];
        const datasets = series.map((s, idx) => ({
            label: s.name,
            data: s.data || [],
            borderColor: palette[idx % palette.length],
            backgroundColor: palette[idx % palette.length] + "33",
            fill: false,
            tension: 0.3,
        }));
        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: months,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
        this._charts.push(chart);
    }

    _renderContractTypePieChart() {
        const el = this.contractTypePieRef.el;
        if (!el) {
            return;
        }
        const dist = this.data.contract_type_distribution || [];
        if (!dist.length) {
            return;
        }
        const ctx = el.getContext("2d");
        const colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47"];
        const chart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: dist.map((d) => d.name),
                datasets: [
                    {
                        data: dist.map((d) => d.count),
                        backgroundColor: dist.map(
                            (_, idx) => colors[idx % colors.length]
                        ),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
        this._charts.push(chart);
    }

    _formatNumber(n) {
        if (n === undefined || n === null) {
            return "0";
        }
        return n.toLocaleString("es-HN");
    }

    /**
     * Importes monetarios en la moneda de la compañía activa (`user.activeCompany`),
     * mismo criterio que el resto del backend Odoo (símbolo y posición según res.currency).
     */
    _formatMoney(n) {
        const amount = n === undefined || n === null ? 0 : n;
        const currencyId = user.activeCompany?.currency_id;
        return formatCurrency(amount, currencyId, { trailingZeros: true });
    }

    _formatVariationPct(pct) {
        if (pct === null || pct === undefined) {
            return "—";
        }
        const sign = pct > 0 ? "+" : "";
        return `${sign}${pct}%`;
    }

    _formatNetMovement(n) {
        if (n === undefined || n === null) {
            return "0";
        }
        const sign = n > 0 ? "+" : "";
        return `${sign}${this._formatNumber(n)}`;
    }

    _openReport(action_xmlid) {
        this.actionService.doAction(action_xmlid);
    }

    _openHeadcountReport() {
        this._openReport("gn_hr_intercompany.action_headcount_cost_wizard");
    }

    _openTurnoverReport() {
        this._openReport("gn_hr_intercompany.action_turnover_analysis_wizard");
    }

    _openLeaveReport() {
        this._openReport("gn_hr_intercompany.action_consolidated_leave_wizard");
    }

    _openAttendanceReport() {
        this._openReport("gn_hr_intercompany.action_consolidated_attendance_wizard");
    }

    _openPayrollReport() {
        this._openReport("gn_hr_intercompany.action_consolidated_payroll_wizard");
    }

    _openTransfers() {
        this._openReport("gn_hr_intercompany.action_hr_employee_transfer");
    }

    _openContractsExpiringDrilldown() {
        const dd = this.data?.drilldown?.employee_contract_expiring;
        if (!dd?.today || !dd?.end_90) {
            this.notification.add(
                _t("No hay datos de contratos para abrir la lista."),
                { type: "warning" }
            );
            return;
        }
        const companyIds = dd.company_ids || [];
        const domain = [
            ["active", "=", true],
            ["contract_date_end", "!=", false],
            ["contract_date_end", ">=", dd.today],
            ["contract_date_end", "<=", dd.end_90],
        ];
        if (companyIds.length) {
            domain.push(["company_id", "in", companyIds]);
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Contratos por vencer (90 días)"),
            res_model: "hr.employee",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
            context: { search_default_active: 1 },
        });
    }

    /* Cadenas UI para plantilla (traducibles) */
    uiStr(key) {
        const map = {
            loading: _t("Cargando..."),
            load_failed: _t("No se pudieron cargar los datos del dashboard."),
            retry: _t("Reintentar"),
            country: _t("País"),
            all_countries: _t("Todos"),
            year: _t("Año"),
            month: _t("Mes"),
            date_from: _t("Desde"),
            date_to: _t("Hasta"),
            apply_filters: _t("Aplicar filtros"),
            clear_range: _t("Quitar rango"),
            preset_this_month: _t("Este mes"),
            preset_last_month: _t("Mes ant."),
            preset_ytd: _t("YTD"),
            filter_hint: _t(
                "Si indica desde y hasta, el rango tiene prioridad sobre año/mes para nómina, ausencias, horas extra e incidencias. Gráficos de tendencia usan el fin del período como referencia."
            ),
            title: _t("Vista regional HR"),
            period_label: _t("Período:"),
            kpi_headcount: _t("Headcount"),
            kpi_headcount_sub: _t("empleados activos"),
            kpi_payroll: _t("Costo nómina"),
            kpi_turnover: _t("Rotación"),
            kpi_absence_pct: _t("Ausentismo"),
            kpi_overtime: _t("Horas extra"),
            kpi_leave_bal: _t("Vacaciones pend."),
            kpi_leave_sub: _t("días acumulados"),
            kpi_absence_days: _t("Días ausencia"),
            kpi_absence_days_sub: _t("total días en período"),
            kpi_late: _t("Tardanzas"),
            kpi_late_sub: _t("incidencias tipo tardanza"),
            kpi_payroll_var: _t("Var. nómina vs mes ant."),
            kpi_payroll_var_sub: _t("mes calendario anterior"),
            kpi_movement: _t("Movimiento neto"),
            kpi_movement_sub: _t("altas − bajas en período"),
            kpi_contracts: _t("Contratos por vencer"),
            kpi_contracts_sub: _t("ventana 30 / 60 / 90 días"),
            kpi_tenure: _t("Antigüedad media"),
            kpi_tenure_sub: _t("años, empleados activos"),
            kpi_payroll_per_emp: _t("Costo nómina / empleado"),
            kpi_payroll_per_emp_sub: _t("bruto ÷ headcount, mismo período"),
            kpi_overtime_var: _t("Var. horas extra vs mes ant."),
            kpi_overtime_var_sub: _t("mes calendario anterior"),
            sec_absence_by_type: _t("Ausencias por tipo"),
            sec_diversity: _t("Plantilla por sexo"),
            sec_tenure_bands: _t("Antigüedad por bandas (años)"),
            sec_recruitment: _t("Reclutamiento"),
            rec_jobs: _t("Puestos con meta de contratación"),
            rec_target_sum: _t("Suma de metas (vacantes objetivo)"),
            rec_hired: _t("Contrataciones en período"),
            rec_avg_days: _t("Días medio hasta cierre"),
            rec_na_module: _t("Instale Reclutamiento para métricas de candidatos."),
            th_leave_type: _t("Tipo"),
            th_days: _t("Días"),
            th_band: _t("Banda"),
            th_count: _t("Empleados"),
            band_lt1: _t("Menos de 1"),
            band_1_3: _t("1 a menos de 3"),
            band_3_5: _t("3 a menos de 5"),
            band_5_10: _t("5 a menos de 10"),
            band_10p: _t("10 o más"),
            chart_hc_company: _t("Headcount por compañía"),
            chart_payroll_title: _t("Costo nómina"),
            chart_payroll_per_emp_trend: _t("Costo nómina / empleado por mes"),
            chart_incidents: _t("Incidencias"),
            chart_movement: _t("Altas y bajas"),
            chart_contract_type_line: _t("Tipo de contrato por mes"),
            chart_contract_type_pie: _t("Distribución tipo de contrato"),
            alerts_title: _t("Alertas pendientes"),
            alert_contracts: _t(
                "Actividades con resumen «Contrato por vencer»"
            ),
            alert_incidents: _t("Incidencias pendientes"),
            quick_actions: _t("Acciones rápidas"),
            qa_payroll: _t("Nómina consolidada"),
            qa_attendance: _t("Asistencia"),
            qa_leave: _t("Ausencias"),
            qa_turnover: _t("Rotación"),
            qa_headcount: _t("Headcount"),
            qa_transfers: _t("Transferencias"),
        };
        return map[key] || key;
    }

    tenureBandLabel(code) {
        const m = {
            "<1": this.uiStr("band_lt1"),
            "1-3": this.uiStr("band_1_3"),
            "3-5": this.uiStr("band_3_5"),
            "5-10": this.uiStr("band_5_10"),
            "10+": this.uiStr("band_10p"),
        };
        return m[code] || code;
    }

    setDateRangePreset(preset) {
        const now = new Date();
        let start;
        let end;
        if (preset === "this_month") {
            start = new Date(now.getFullYear(), now.getMonth(), 1);
            end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        } else if (preset === "last_month") {
            start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            end = new Date(now.getFullYear(), now.getMonth(), 0);
        } else if (preset === "ytd") {
            start = new Date(now.getFullYear(), 0, 1);
            end = now;
        } else {
            return;
        }
        this.state.filters.date_from = toInputDate(start);
        this.state.filters.date_to = toInputDate(end);
    }
}
