/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Centralized UI labels for OWL templates (exportable to es_GT).
 */
export function dashboardLabels() {
    return {
        title: _t("Treasury — Dashboard"),
        subtitle: _t("Executive view of gn_banks treasury operations"),
        kpiExpanded: _t("Expanded KPIs"),
        kpiCompact: _t("Compact KPIs"),
        refresh: _t("Refresh"),
        dailyCashflow: _t("Daily cash flow"),
        insights: _t("Insights"),
        noInsights: _t("No insights for this period."),
        operationalAlerts: _t("Operational alerts"),
        noAlerts: _t("No alerts."),
        distributions: _t("Distributions"),
        chartByOperationType: _t("By operation type"),
        chartByBank: _t("By bank"),
        chartByBranch: _t("By branch"),
        chartChecksByState: _t("Checks by status"),
        chartPosByBank: _t("POS settlements by bank"),
        chartTopPartners: _t("Top contacts by amount"),
        operationalRisk: _t("Operational risk"),
        variationVsPrevious: _t("vs previous period"),
        tableLabel: _t("Label"),
        tableDocs: _t("Docs"),
        tableDebit: _t("Debit"),
        tableCredit: _t("Credit"),
        tableNet: _t("Net"),
        periodRange: _t("Period"),
        moreMetrics: _t("More metrics"),
        lessMetrics: _t("Fewer metrics"),
        analysis: _t("Analysis"),
        intelligence: _t("Intelligence"),
        breakdowns: _t("Breakdowns"),
        details: _t("Details"),
        viewDetail: _t("View detail"),
        clickChartHint: _t("Click a segment to open filtered records"),
        noChartData: _t("No data for this view"),
        noChartDataHint: _t(
            "Sin movimientos en este corte. Cambia los filtros o cambia de pestaña."
        ),
        noTableData: _t("Sin filas para mostrar"),
        noTableDataHint: _t(
            "No hay registros que cumplan los filtros aplicados."
        ),
        noAlertsHint: _t(
            "Excelente: no se detectaron incidentes operativos en este período."
        ),
        topRows: _t("Top movements"),
        share: _t("Share"),
    };
}

/** KPI keys shown in the executive hero row (single responsive strip). */
export const PRIMARY_KPI_KEYS = [
    "available_balance",
    "period_inflow",
    "period_outflow",
    "net_flow",
];

export function filterBarLabels() {
    return {
        month: _t("Month"),
        year: _t("Year"),
        dateFrom: _t("From"),
        dateTo: _t("To"),
        company: _t("Company"),
        banksJournals: _t("Banks / journals"),
        apply: _t("Apply"),
        resetFiltersTitle: _t("Reset filters"),
        flowSource: _t("Flow source"),
        flowTreasury: _t("Treasury (gn_banks)"),
        flowTreasuryTitle: _t("Inflows/outflows from gn_banks documents"),
        flowLedger: _t("Accounting ledger"),
        flowLedgerTitle: _t(
            "Inflows/outflows from bank/cash ledger (reconciles with the available balance)"
        ),
    };
}

export function journalSelectorLabels() {
    return {
        selectAll: _t("Select all"),
        selectAllTitle: _t("Select all bank journals"),
        clear: _t("Clear"),
        clearTitle: _t("Clear journal filter"),
        searchPlaceholder: _t("Search bank or journal…"),
        fieldString: _t("Bank journals"),
    };
}

export function chartDatasetLabels() {
    return {
        inflows: _t("Inflows"),
        outflows: _t("Outflows"),
        cumulative: _t("Cumulative"),
        trend: _t("7-day trend"),
        byOperationType: _t("By operation type"),
        byBank: _t("By bank"),
        byBranch: _t("By branch"),
        posByBank: _t("POS settlements by bank"),
        topPartners: _t("Top contacts"),
    };
}

export function summaryTableTitles() {
    return {
        bank: _t("By bank"),
        branch: _t("By branch"),
        operation_type: _t("By operation type"),
        state: _t("By status"),
        user: _t("By user"),
        partner: _t("By contact"),
        account: _t("By account"),
        analytic: _t("By analytic account"),
    };
}
