/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { useSetupAction } from "@web/search/action_hook";
import { getDefaultConfig } from "@web/views/view";

import { Component, useState, onWillStart, useChildSubEnv, useSubEnv } from "@odoo/owl";

import { Layout } from "@web/search/layout";
import { BiAccountReportController } from "./controller";
import { BiAccountReportFilters } from "./filters/filters";
import { BiAccountReportButtonsBar } from "./buttons_bar/buttons_bar";
import { BiInfoPopover } from "./bi_info_popover";
import { BiAnnotationPopover } from "./bi_annotation_popover";
import { usePopover } from "@web/core/popover/popover_hook";

const { DateTime } = luxon;

export class BiAccountReport extends Component {
    static template = "bi_financial_reports_comm.BiAccountReport";
    static props = { ...standardActionServiceProps };
    static components = {
        Layout,
        BiAccountReportFilters,
        BiAccountReportButtonsBar,
    };

    get _t() {
        return _t;
    }

    formatAmount(amount, symbol = "") {
        const n = Number(amount);
        if (Number.isNaN(n)) return (symbol || "") + " 0.00";
        return (symbol || "") + " " + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    /** True when the backend returns an analytic-columns matrix (accounts x analytic). */
    get analyticColumnMode() {
        return this.controller?.state?.data?.column_mode === "analytic";
    }

    get analyticMatrix() {
        return this.controller?.state?.data?.analytic_matrix || { columns: [], rows: [] };
    }

    get analyticMatrixColumns() {
        return this.analyticMatrix.columns || [];
    }

    /** Flatten matrix sections, showing their account children only when expanded. */
    get analyticMatrixRows() {
        const out = [];
        for (const row of this.analyticMatrix.rows || []) {
            out.push(row);
            if (row.type === "section" && this.controller.isAnalyticRowExpanded(row.key)) {
                for (const child of row.children || []) {
                    out.push(child);
                }
            }
        }
        return out;
    }

    get analyticMatrixTitle() {
        const titles = {
            profit_loss: _t("Estado de Resultados"),
            profit_and_loss: _t("Estado de Resultados"),
            balance_sheet: _t("Balance general"),
            trial_balance: _t("Balance de comprobación"),
        };
        return titles[this.reportType] || _t("Reporte");
    }

    getMatrixCell(row, colKey) {
        return (row.values || {})[colKey] ?? 0;
    }

    onToggleAnalyticRow(ev) {
        const key = ev.currentTarget?.getAttribute("data-arow");
        if (key) {
            this.controller.toggleAnalyticRow(key);
        }
    }

    async onDrillAnalyticCell(ev, accountId, analyticId) {
        ev.preventDefault();
        ev.stopPropagation();
        if (!accountId) {
            return;
        }
        const opts = this.buildDrilldownOptions("current", {
            _an_cumulative: this.reportType === "balance_sheet",
        });
        const model = this.controller.modelName;
        try {
            const action = await this.orm.call(model, "action_open_analytic_cell", [
                opts,
                accountId,
                analyticId || false,
            ]);
            if (action) {
                await this.actionService.doAction(action);
            }
        } catch (e) {
            // Fallback to the report's own AML drill-down when analytic lines fail.
            try {
                const action = await this.orm.call(model, "action_open_aml", [opts, accountId]);
                if (action) {
                    await this.actionService.doAction(action);
                }
            } catch (err) {
                this.notification.add(_t("No se pudieron cargar los apuntes"), { type: "danger" });
            }
        }
    }

    get sectionLabels() {
        return {
            income: _t("Ingresos"),
            income_other: _t("Otros ingresos"),
            expense: _t("Gastos operativos"),
            expense_direct_cost: _t("Costo de ventas"),
            expense_depreciation: _t("Depreciación y amortización"),
            expense_other: _t("Otros gastos"),
            bank_cash: _t("Bancos y efectivo"),
            receivables: _t("Cuentas por cobrar"),
            current_assets: _t("Activos corrientes"),
            prepayments: _t("Anticipos"),
            fixed_assets: _t("Activos fijos"),
            non_current: _t("Activos no corrientes"),
            payables: _t("Cuentas por pagar"),
            credit_card: _t("Tarjetas de crédito"),
            current_liabilities: _t("Pasivos corrientes"),
            non_current_liabilities: _t("Pasivos no corrientes"),
            equity: _t("Capital"),
            current_year_earnings: _t("Ganancias del ejercicio"),
        };
    }

    getSectionLabel(key) {
        return this.sectionLabels[key] || key;
    }

    /** Labels for Estado de resultados (P&L) matching Enterprise layout */
    get plSectionLabels() {
        return {
            income: _t("Ingreso"),
            expense_direct_cost: _t("Menos costo de ingresos"),
            gross_profit: _t("Ganancia bruta"),
            expense: _t("Menos gasto de operación"),
            operating_income: _t("Ingreso de operación (o pérdida)"),
            income_other: _t("Más otros ingresos"),
            expense_depreciation: _t("Menos gastos de otro tipo"),
            net_profit: _t("Ganancias netas"),
        };
    }

    getPlSectionLabel(key) {
        return this.plSectionLabels[key] || this.getSectionLabel(key) || key;
    }

    /** Period columns for P&L (current + N comparison periods). */
    get profitLossPeriods() {
        const data = this.controller?.state?.data;
        if (data?.periods?.length) {
            return data.periods;
        }
        const periods = [{
            key: "current",
            label: this.periodHeaderLabel,
            date_from: this.controller?.state?.options?.date_from,
            date_to: this.controller?.state?.options?.date_to,
            is_current: true,
        }];
        if (data?.comparison?.string) {
            periods.unshift({
                key: "cmp_1",
                label: data.comparison.string,
                date_from: data.comparison.date_from,
                date_to: data.comparison.date_to,
                is_current: false,
            });
        }
        return periods;
    }

    get hasProfitLossComparison() {
        return this.profitLossPeriods.length > 1;
    }

    get profitLossComparisonLabel() {
        const periods = this.profitLossPeriods.filter((p) => !p.is_current);
        return periods.length === 1 ? periods[0].label : "";
    }

    getProfitLossPeriodAmount(row, periodKey) {
        if (!row) return 0;
        const balances = row.balances || row.total_by_period;
        if (balances && periodKey in balances) {
            return balances[periodKey];
        }
        if (periodKey === "current") {
            return row.total ?? 0;
        }
        if (periodKey !== "current" && row.comparisonTotal !== undefined) {
            return row.comparisonTotal;
        }
        return 0;
    }

    getProfitLossPercentBaseKey() {
        const periods = this.profitLossPeriods;
        const currentIdx = periods.findIndex((p) => p.key === "current");
        if (currentIdx > 0) {
            return periods[currentIdx - 1].key;
        }
        if (periods.length > 1) {
            return periods[periods.length - 2].key;
        }
        return null;
    }

    getProfitLossPercentChange(row) {
        const baseKey = this.getProfitLossPercentBaseKey();
        if (!baseKey) return "";
        const current = this.getProfitLossPeriodAmount(row, "current");
        const base = this.getProfitLossPeriodAmount(row, baseKey);
        return this.formatPercentChange(current, base, row.isExpense);
    }

    getProfitLossPercentChangeClass(row) {
        const baseKey = this.getProfitLossPercentBaseKey();
        if (!baseKey) return "";
        const current = this.getProfitLossPeriodAmount(row, "current");
        const base = this.getProfitLossPeriodAmount(row, baseKey);
        return this.getPercentChangeClass(current, base, row.isExpense);
    }

    _plBucketTotal(bucket, key, periodKey) {
        return bucket?.[key]?.total_by_period?.[periodKey] ?? bucket?.[key]?.total ?? 0;
    }

    _plSubtotalBalances(income, expense, calc) {
        const balances = {};
        for (const period of this.profitLossPeriods) {
            balances[period.key] = calc(period.key);
        }
        return balances;
    }

    /** Section and subtotal rows (without nested account/group lines). */
    get profitLossRows() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        const income = data.income || {};
        const expense = data.expense || {};

        const grossBalances = this._plSubtotalBalances(income, expense, (pk) =>
            this._plBucketTotal(income, "income", pk) - this._plBucketTotal(expense, "expense_direct_cost", pk)
        );
        const operatingBalances = this._plSubtotalBalances(income, expense, (pk) =>
            (grossBalances[pk] ?? 0) - this._plBucketTotal(expense, "expense", pk)
        );
        const netBalances = this._plSubtotalBalances(income, expense, (pk) =>
            (operatingBalances[pk] ?? 0)
            + this._plBucketTotal(income, "income_other", pk)
            - this._plBucketTotal(expense, "expense_depreciation", pk)
        );

        const sectionRow = (key, labelKey, bucketKey, bucketSide, isExpense = false) => {
            const bucket = bucketSide === "income" ? income[bucketKey] : expense[bucketKey];
            return {
                type: "section",
                key,
                labelKey,
                sectionKey: key,
                balances: bucket?.total_by_period || { current: bucket?.total ?? 0 },
                total_by_period: bucket?.total_by_period || { current: bucket?.total ?? 0 },
                total: bucket?.total ?? 0,
                hierarchy: bucket?.hierarchy || [],
                use_hierarchy: !!bucket?.use_hierarchy,
                accounts: bucket?.accounts || [],
                isExpense,
            };
        };

        return [
            sectionRow("income", "income", "income", "income"),
            sectionRow("expense_direct_cost", "expense_direct_cost", "expense_direct_cost", "expense", true),
            { type: "subtotal", key: "gross_profit", labelKey: "gross_profit", balances: grossBalances, isExpense: false },
            sectionRow("expense", "expense", "expense", "expense", true),
            { type: "subtotal", key: "operating_income", labelKey: "operating_income", balances: operatingBalances, isExpense: false },
            sectionRow("income_other", "income_other", "income_other", "income"),
            sectionRow("expense_depreciation", "expense_depreciation", "expense_depreciation", "expense", true),
            { type: "subtotal", key: "net_profit", labelKey: "net_profit", balances: netBalances, isExpense: false },
        ];
    }

    _flattenPlHierarchy(sectionKey, nodes, isExpense = false) {
        const rows = [];
        const expanded = this.controller?.state?.expandedPlGroups ?? {};
        for (const node of nodes || []) {
            if (node.type === "group") {
                const expandable = (node.children || []).length > 0;
                rows.push({
                    type: "group",
                    sectionKey,
                    key: node.key,
                    label: node.label || `${node.code || ""} ${node.name || ""}`.trim(),
                    level: node.level ?? 0,
                    expandable,
                    balances: node.balances || {},
                    isExpense,
                });
                if (!!expanded[node.key] && node.children?.length) {
                    rows.push(...this._flattenPlHierarchy(sectionKey, node.children, isExpense));
                    rows.push({
                        type: "group_total",
                        sectionKey,
                        key: `total_${node.key}`,
                        label: `${this._t("Total")} ${node.code || ""} ${node.name || ""}`.trim(),
                        level: (node.level ?? 0) + 1,
                        balances: node.balances || {},
                        isExpense,
                    });
                }
            } else if (node.type === "account") {
                rows.push({
                    type: "account",
                    sectionKey,
                    key: node.key,
                    id: node.id,
                    code: node.code,
                    name: node.name,
                    level: node.level ?? 0,
                    balances: node.balances || {},
                    isExpense,
                });
            }
        }
        return rows;
    }

    isPlSectionExpandable(row) {
        if ((row?.accounts || []).length) {
            return true;
        }
        const opts = this.controller?.state?.options || {};
        return !!(opts.hierarchy && row?.use_hierarchy && row?.hierarchy?.length);
    }

    isBsSectionExpandable(row) {
        if ((row?.accounts || []).length) {
            return true;
        }
        const opts = this.controller?.state?.options || {};
        return !!(opts.hierarchy && row?.use_hierarchy && row?.hierarchy?.length);
    }

    /** Flat rows for rendering including expanded hierarchy/account lines. */
    get profitLossDisplayRows() {
        const rows = [];
        const opts = this.controller?.state?.options || {};
        for (const row of this.profitLossRows) {
            rows.push(row);
            if (row.type !== "section") {
                continue;
            }
            if (!this.controller.isPlSectionExpanded(row.key)) {
                continue;
            }
            const useNestedGroups = opts.hierarchy && row.use_hierarchy && row.hierarchy?.length;
            if (useNestedGroups) {
                rows.push(...this._flattenPlHierarchy(row.sectionKey || row.key, row.hierarchy, row.isExpense));
            } else {
                for (const acc of row.accounts || []) {
                    rows.push({
                        type: "account",
                        sectionKey: row.key,
                        key: `acc_${acc.id}`,
                        id: acc.id,
                        code: acc.code,
                        name: acc.name,
                        level: 1,
                        balances: acc.balances || { current: acc.balance ?? 0 },
                        isExpense: row.isExpense,
                    });
                }
            }
        }
        return this._applyHideZeroLines(rows, (r, pk) => this.getProfitLossPeriodAmount(r, pk));
    }

    onTogglePlGroup(ev) {
        const key = ev.currentTarget?.getAttribute("data-group");
        if (key) this.controller.togglePlGroup(key);
    }

    get comparisonPeriodOrderAscending() {
        return (this.controller?.state?.options?.comparison_period_order || "descending") === "ascending";
    }

    get executiveSummarySectionLabels() {
        return {
            cash: _t("Efectivo"),
            profitability: _t("Rentabilidad"),
            balancesheet: _t("Balance general"),
            performance: _t("Rendimiento"),
        };
    }

    getExecutiveSummarySectionLabel(section) {
        return this.executiveSummarySectionLabels[section] || section;
    }

    get executiveSummaryRowLabels() {
        return {
            cash_received: _t("Efectivo recibido"),
            cash_spent: _t("Efectivo gastado"),
            cash_surplus: _t("Superávit de efectivo"),
            closing_bank: _t("Balance bancario de cierre"),
            income: _t("Ingreso"),
            cost_revenue: _t("Costo de ingresos"),
            gross_profit: _t("Ganancia bruta"),
            expenses: _t("Gastos"),
            net_profit: _t("Ganancias netas"),
            receivables: _t("Por cobrar"),
            payables: _t("Por pagar"),
            net_assets: _t("Activos netos"),
            gross_margin: _t("Margen de ganancia bruta (ganancia bruta/ingreso de operación)"),
            net_margin: _t("Margen neto de ganancias (ganancias netas/ingresos)"),
            roi: _t("Retorno de la inversión (ganancia neta/activos)"),
        };
    }

    getExecutiveSummaryRowLabel(labelKey) {
        return this.executiveSummaryRowLabels[labelKey] || labelKey;
    }

    get executiveSummaryRows() {
        const data = this.controller?.state?.data;
        if (!data?.rows) return [];
        const rows = [];
        let lastSection = null;
        for (const row of data.rows) {
            if (row.section && row.section !== lastSection) {
                rows.push({ isSectionHeader: true, section: row.section });
                lastSection = row.section;
            }
            if (row.label) {
                const val = row.value ?? 0;
                const cmpVal = row.comparison_value ?? 0;
                let pctChange = "";
                let pctClass = "";
                if (data.comparison && row.comparison_value !== undefined && !row.is_pct) {
                    pctChange = this.formatPercentChange(val, cmpVal, row.negative_red);
                    pctClass = this.getPercentChangeClass(val, cmpVal, row.negative_red);
                } else if (row.is_pct) {
                    pctChange = "-";
                }
                rows.push({
                    ...row,
                    percent_change: pctChange,
                    percent_change_class: pctClass,
                });
            }
        }
        return rows;
    }

    get hasExecutiveSummaryComparison() {
        return !!(this.controller?.state?.data?.comparison?.string);
    }

    get executiveSummaryComparisonLabel() {
        return this.controller?.state?.data?.comparison?.string || "";
    }

    formatPercentChange(current, comparison, isExpense = false) {
        const c = Number(current ?? 0);
        const p = Number(comparison ?? 0);
        if (Number.isNaN(c) || Number.isNaN(p)) return "";
        if (p === 0) return c === 0 ? "0%" : "-";
        const pct = ((c - p) / Math.abs(p)) * 100;
        const s = pct >= 0 ? `+${pct.toFixed(1)}%` : `${pct.toFixed(1)}%`;
        return s;
    }

    getPercentChangeClass(current, comparison, isExpense = false) {
        const c = Number(current ?? 0);
        const p = Number(comparison ?? 0);
        if (Number.isNaN(c) || Number.isNaN(p) || p === 0) return "";
        const pct = (c - p) / Math.abs(p);
        if (isExpense) return pct > 0 ? "text-danger" : pct < 0 ? "text-success" : "";
        return pct > 0 ? "text-success" : pct < 0 ? "text-danger" : "";
    }

    getFormatAmountClass(balance) {
        const n = Number(balance);
        if (Number.isNaN(n)) return "";
        if (n < 0) return "text-danger";
        if (n === 0) return "text-muted";
        return "";
    }

    onTogglePlSection(ev) {
        const key = ev.currentTarget?.getAttribute("data-section");
        if (key) this.controller.togglePlSection(key);
    }

    /** Balance Sheet: "Al DD/MM/YYYY" format (Enterprise) */
    get periodHeaderLabelBalanceSheet() {
        const opts = this.controller.state.options;
        const to = opts.date_to ? DateTime.fromISO(opts.date_to) : null;
        return to ? `Al ${to.toLocaleString(DateTime.DATE_SHORT)}` : "";
    }

    /** Labels for Balance Sheet matching Enterprise (ACTIVOS, Cuentas bancarias...) */
    get balanceSheetSectionLabels() {
        return {
            bank_cash: _t("Cuentas bancarias y de efectivo"),
            receivables: _t("Cuentas por cobrar"),
            current_assets: _t("Activos corrientes"),
            prepayments: _t("Anticipos"),
            fixed_assets: _t("Activos fijos"),
            non_current: _t("Activos no corrientes"),
            payables: _t("Cuentas por pagar"),
            credit_card: _t("Tarjetas de crédito"),
            current_liabilities: _t("Pasivos corrientes"),
            non_current_liabilities: _t("Pasivos no corrientes"),
            equity: _t("Capital"),
            current_year_earnings: _t("Ganancias del ejercicio"),
        };
    }

    getBalanceSheetSectionLabel(key) {
        return this.balanceSheetSectionLabels[key] || this.getSectionLabel(key) || key;
    }

    get balanceSheetPeriods() {
        const data = this.controller?.state?.data;
        if (data?.periods?.length) {
            return data.periods;
        }
        return [{
            key: "current",
            label: this.periodHeaderLabelBalanceSheet,
            date_from: this.controller?.state?.options?.date_from,
            date_to: this.controller?.state?.options?.date_to,
            is_current: true,
        }];
    }

    get hasBalanceSheetComparison() {
        return this.balanceSheetPeriods.length > 1;
    }

    getBalanceSheetPeriodAmount(row, periodKey) {
        if (!row) return 0;
        const balances = row.balances || row.total_by_period;
        if (balances && periodKey in balances) {
            return balances[periodKey];
        }
        if (periodKey === "current") {
            return row.total ?? 0;
        }
        return row.comparisonTotal ?? 0;
    }

    getBalanceSheetPercentBaseKey() {
        const periods = this.balanceSheetPeriods;
        const currentIdx = periods.findIndex((p) => p.key === "current");
        if (currentIdx > 0) {
            return periods[currentIdx - 1].key;
        }
        if (periods.length > 1) {
            return periods[periods.length - 2].key;
        }
        return null;
    }

    getBalanceSheetPercentChange(row) {
        const baseKey = this.getBalanceSheetPercentBaseKey();
        if (!baseKey) return "";
        const current = this.getBalanceSheetPeriodAmount(row, "current");
        const base = this.getBalanceSheetPeriodAmount(row, baseKey);
        return this.formatPercentChange(current, base);
    }

    getBalanceSheetPercentChangeClass(row) {
        const baseKey = this.getBalanceSheetPercentBaseKey();
        if (!baseKey) return "";
        const current = this.getBalanceSheetPeriodAmount(row, "current");
        const base = this.getBalanceSheetPeriodAmount(row, baseKey);
        return this.getPercentChangeClass(current, base);
    }

    _bsBucketTotal(blocks, key, periodKey) {
        return blocks?.[key]?.total_by_period?.[periodKey] ?? blocks?.[key]?.total ?? 0;
    }

    _bsSectionRow(key, label, bucket, blocks) {
        const sec = blocks[key];
        if (!sec) return null;
        return {
            type: "section",
            section: bucket,
            key,
            label,
            balances: sec.total_by_period || { current: sec.total ?? 0 },
            total_by_period: sec.total_by_period || { current: sec.total ?? 0 },
            total: sec.total ?? 0,
            hierarchy: sec.hierarchy || [],
            use_hierarchy: !!sec.use_hierarchy,
            accounts: sec.accounts || [],
        };
    }

    /** Flat rows for Balance Sheet with expandable sections (Enterprise layout) */
    get balanceSheetRows() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        const assets = data.assets || {};
        const liabilities = data.liabilities || {};
        const equity = data.equity || {};
        const totals = data.totals || {};
        const totalsByPeriod = totals.by_period || {};
        const rows = [];

        const assetKeys = ["bank_cash", "receivables", "current_assets", "prepayments", "fixed_assets", "non_current"];
        rows.push({
            type: "main_header",
            label: _t("ACTIVOS"),
            block: "assets",
            balances: totalsByPeriod.assets || { current: totals.assets ?? 0 },
        });
        for (const key of assetKeys) {
            const row = this._bsSectionRow(key, this.getBalanceSheetSectionLabel(key), "assets", assets);
            if (row) rows.push({ ...row, block: "assets" });
        }
        rows.push({
            type: "main_total",
            label: _t("Total ACTIVOS"),
            block: "assets",
            balances: totalsByPeriod.assets || { current: totals.assets ?? 0 },
        });

        const liabKeys = ["payables", "credit_card", "current_liabilities", "non_current_liabilities"];
        rows.push({
            type: "main_header",
            label: _t("PASIVOS"),
            block: "liabilities",
            balances: totalsByPeriod.liabilities || { current: totals.liabilities ?? 0 },
        });
        for (const key of liabKeys) {
            const row = this._bsSectionRow(key, this.getBalanceSheetSectionLabel(key), "liabilities", liabilities);
            if (row) rows.push({ ...row, block: "liabilities" });
        }
        rows.push({
            type: "main_total",
            label: _t("Total PASIVOS"),
            block: "liabilities",
            balances: totalsByPeriod.liabilities || { current: totals.liabilities ?? 0 },
        });

        const eqKeys = ["equity", "current_year_earnings"];
        rows.push({
            type: "main_header",
            label: _t("PATRIMONIO"),
            block: "equity",
            balances: totalsByPeriod.equity || { current: totals.equity ?? 0 },
        });
        for (const key of eqKeys) {
            const row = this._bsSectionRow(key, this.getBalanceSheetSectionLabel(key), "equity", equity);
            if (row) rows.push({ ...row, block: "equity" });
        }
        rows.push({
            type: "main_total",
            label: _t("Total PASIVOS + PATRIMONIO"),
            block: "equity",
            balances: totalsByPeriod.liabilities_equity || { current: totals.liabilities_equity ?? 0 },
        });

        // Exponer total/comparisonTotal en todas las filas (encabezados y totales de
        // bloque no los traían, por eso mostraban 0.00). Se derivan del diccionario de
        // saldos por periodo para que la plantilla y la columna de comparación cuadren.
        const periods = this.balanceSheetPeriods;
        const cmpKey = (periods.find((p) => !p.is_current) || {}).key;
        return rows.map((row) => {
            const bal = row.balances || row.total_by_period || {};
            return {
                ...row,
                total: row.total ?? (bal.current ?? 0),
                comparisonTotal: cmpKey
                    ? (bal[cmpKey] ?? row.comparisonTotal ?? 0)
                    : (row.comparisonTotal ?? 0),
            };
        });
    }

    _flattenBsHierarchy(sectionKey, nodes) {
        const rows = [];
        const expanded = this.controller?.state?.expandedBsGroups ?? {};
        for (const node of nodes || []) {
            if (node.type === "group") {
                const expandable = (node.children || []).length > 0;
                rows.push({
                    type: "group",
                    sectionKey,
                    key: node.key,
                    label: node.label || `${node.code || ""} ${node.name || ""}`.trim(),
                    level: node.level ?? 0,
                    expandable,
                    balances: node.balances || {},
                });
                if (!!expanded[node.key] && node.children?.length) {
                    rows.push(...this._flattenBsHierarchy(sectionKey, node.children));
                    rows.push({
                        type: "group_total",
                        sectionKey,
                        key: `total_${node.key}`,
                        label: `${this._t("Total")} ${node.code || ""} ${node.name || ""}`.trim(),
                        level: (node.level ?? 0) + 1,
                        balances: node.balances || {},
                    });
                }
            } else if (node.type === "account") {
                rows.push({
                    type: "account",
                    sectionKey,
                    key: node.key,
                    id: node.id,
                    code: node.code,
                    name: node.name,
                    level: node.level ?? 0,
                    balances: node.balances || {},
                });
            }
        }
        return rows;
    }

    /** True si todos los saldos por periodo de la fila son ~0. */
    _isZeroBalances(balances) {
        const periods = this.balanceSheetPeriods;
        const keys = periods?.length ? periods.map((p) => p.key) : ["current"];
        return keys.every((pk) => Math.abs(Number((balances || {})[pk] ?? 0)) < 0.005);
    }

    /** Poda recursiva del árbol de jerarquía: quita cuentas en 0 y grupos que
     *  quedan vacíos (para "Ocultar las líneas en 0"). */
    _pruneZeroBsNodes(nodes) {
        const result = [];
        for (const node of nodes || []) {
            if (node.type === "account") {
                if (!this._isZeroBalances(node.balances)) {
                    result.push(node);
                }
            } else if (node.type === "group") {
                const children = this._pruneZeroBsNodes(node.children);
                if (children.length) {
                    result.push({ ...node, children });
                }
            } else {
                result.push(node);
            }
        }
        return result;
    }

    /** Filas de jerarquía de una sección, aplicando "Ocultar las líneas en 0". */
    bsHierarchyRows(row) {
        let nodes = row?.hierarchy || [];
        if (this.controller?.state?.options?.hide_zero_lines) {
            nodes = this._pruneZeroBsNodes(nodes);
        }
        return this._flattenBsHierarchy(row.key, nodes);
    }

    /** Cuentas (modo plano) visibles según "Ocultar las líneas en 0". */
    bsVisibleAccounts(row) {
        const accounts = row?.accounts || [];
        if (!this.controller?.state?.options?.hide_zero_lines) {
            return accounts;
        }
        return accounts.filter(
            (acc) => !this._isZeroBalances(acc.balances || { current: acc.balance ?? 0 })
        );
    }

    /** True si la sección debe ocultarse: total en 0 y sin cuentas/grupos visibles. */
    isBsSectionHidden(row) {
        if (!this.controller?.state?.options?.hide_zero_lines) {
            return false;
        }
        const totalZero = this._isZeroBalances(
            row.balances || row.total_by_period || { current: row.total ?? 0 }
        );
        if (!totalZero) {
            return false;
        }
        return this.bsHierarchyRows(row).length === 0 && this.bsVisibleAccounts(row).length === 0;
    }

    _isZeroFinancialRow(row, getAmount) {
        const periods = row.block === "assets" || row.block === "liabilities" || row.block === "equity"
            ? this.balanceSheetPeriods
            : this.profitLossPeriods;
        const keys = periods?.length ? periods.map((p) => p.key) : ["current"];
        return keys.every((pk) => Math.abs(Number(getAmount(row, pk) || 0)) < 0.005);
    }

    _applyHideZeroLines(rows, getAmount) {
        if (!this.controller?.state?.options?.hide_zero_lines) {
            return rows;
        }
        return rows.filter((row) => {
            if (["main_header", "main_total", "subtotal", "group_total"].includes(row.type)) {
                return true;
            }
            return !this._isZeroFinancialRow(row, getAmount);
        });
    }

    get horizontalSplit() {
        return !!this.controller?.state?.options?.horizontal_split;
    }

    get balanceSheetLeftDisplayRows() {
        return this.balanceSheetDisplayRows.filter((r) => r.block === "assets");
    }

    get balanceSheetRightDisplayRows() {
        return this.balanceSheetDisplayRows.filter((r) => r.block === "liabilities" || r.block === "equity");
    }

    get balanceSheetRenderBlocks() {
        if (!this.horizontalSplit) {
            return [{ key: "all", rows: this.balanceSheetDisplayRows }];
        }
        return [
            { key: "assets", rows: this.balanceSheetLeftDisplayRows },
            { key: "liabilities", rows: this.balanceSheetRightDisplayRows },
        ];
    }

    get balanceSheetDisplayRows() {
        const rows = [];
        const opts = this.controller?.state?.options || {};
        for (const row of this.balanceSheetRows) {
            rows.push(row);
            if (row.type !== "section") {
                continue;
            }
            if (!this.controller.isBsSectionExpanded(row.key)) {
                continue;
            }
            const block = row.block;
            const useNestedGroups = opts.hierarchy && row.use_hierarchy && row.hierarchy?.length;
            if (useNestedGroups) {
                for (const child of this._flattenBsHierarchy(row.key, row.hierarchy)) {
                    rows.push({ ...child, block });
                }
            } else {
                for (const acc of row.accounts || []) {
                    rows.push({
                        type: "account",
                        sectionKey: row.key,
                        key: `acc_${acc.id}`,
                        id: acc.id,
                        code: acc.code,
                        name: acc.name,
                        level: 1,
                        block,
                        balances: acc.balances || { current: acc.balance ?? 0 },
                        fx_balance: acc.fx_balance,
                        fx_symbol: acc.fx_symbol,
                    });
                }
            }
            if (useNestedGroups || (row.accounts || []).length) {
                rows.push({
                    type: "subtotal",
                    sectionKey: row.key,
                    key: `subtotal_${row.key}`,
                    label: `${this._t("Total")} ${row.label}`,
                    block,
                    balances: row.balances || row.total_by_period || {},
                });
            }
        }
        return this._applyHideZeroLines(rows, (r, pk) => this.getBalanceSheetPeriodAmount(r, pk));
    }

    onToggleBsGroup(ev) {
        const key = ev.currentTarget?.getAttribute("data-group");
        if (key) this.controller.toggleBsGroup(key);
    }

    onToggleBsSection(ev) {
        const key = ev.currentTarget?.getAttribute("data-section");
        if (key) this.controller.toggleBsSection(key);
    }

    get cashFlowComparisonLabel() {
        return this.controller?.state?.data?.comparison?.label || "";
    }

    get hasCashFlowComparison() {
        return !!this.cashFlowComparisonLabel;
    }

    _cashFlowComparisonAmount(row, cmp) {
        if (!cmp || !row) {
            return undefined;
        }
        if (row.type === "summary") {
            if (row.key === "opening_balance") {
                return cmp.opening_balance;
            }
            if (row.key === "closing_balance") {
                return cmp.closing_balance;
            }
        }
        if (row.type === "net_increase") {
            return cmp.net_increase;
        }
        if (row.type === "unexplained") {
            return cmp.unexplained_difference;
        }
        if (row.type === "section") {
            return cmp.sections?.[row.key]?.total;
        }
        if (row.type === "subsection") {
            const dot = row.key.indexOf(".");
            if (dot <= 0) {
                return undefined;
            }
            const secKey = row.key.slice(0, dot);
            const subKey = row.key.slice(dot + 1);
            return cmp.sections?.[secKey]?.subsections?.[subKey]?.total;
        }
        if (row.type === "account" && row.account?.id != null) {
            const parts = row.key.split(".");
            if (parts.length < 3) {
                return undefined;
            }
            const secKey = parts[0];
            const subKey = parts[1];
            const accId = row.account.id;
            const accounts = cmp.sections?.[secKey]?.subsections?.[subKey]?.accounts || [];
            const found = accounts.find((a) => a.id === accId);
            return found?.balance;
        }
        return undefined;
    }

    /** Cash Flow */
    get hasCashFlowData() {
        return this.reportType === "cash_flow" && !!this.controller?.state?.data;
    }

    get cashFlowRows() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        const cmp = data.comparison;
        const opts = this.controller?.state?.options || {};
        const hideZero = !!opts.hide_zero_lines;
        const isZero = (v) => Math.abs(Number(v) || 0) < 0.005;

        const rows = [];
        const sections = data.sections || {};

        const pushRow = (base) => {
            const cAmt = this._cashFlowComparisonAmount(base, cmp);
            rows.push({
                ...base,
                comparisonTotal: cAmt,
            });
        };

        pushRow({
            type: "summary",
            key: "opening_balance",
            label: _t("Efectivo y equivalentes, saldo inicial"),
            total: data.opening_balance || 0,
        });

        const netLabel = _t("Aumento (disminución) neto en efectivo y equivalentes");
        pushRow({
            type: "net_increase",
            key: "net_increase",
            label: netLabel,
            total: data.net_increase || 0,
        });

        const sectionOrder = [
            "operating_activities",
            "investing_activities",
            "financing_activities",
            "unclassified_activities",
        ];

        for (const secKey of sectionOrder) {
            const sec = sections[secKey];
            if (!sec) continue;
            if (hideZero && isZero(sec.total)) continue;
            const expanded = this.controller.isCfSectionExpanded(secKey);
            pushRow({
                type: "section",
                key: secKey,
                label: sec.name,
                total: sec.total || 0,
                expanded,
                expandable: true,
            });
            if (!expanded) continue;
            const subs = sec.subsections || {};
            for (const subKey of Object.keys(subs)) {
                const sub = subs[subKey];
                if (!sub) continue;
                const accounts = sub.accounts || [];
                if (!accounts.length && !sub.total) continue;
                if (hideZero && isZero(sub.total) && !accounts.some((a) => !isZero(a.balance))) continue;
                const subFullKey = `${secKey}.${subKey}`;
                const subExpanded = this.controller.isCfSectionExpanded(subFullKey);
                pushRow({
                    type: "subsection",
                    key: subFullKey,
                    sectionKey: secKey,
                    label: sub.name,
                    total: sub.total || 0,
                    expandable: accounts.length > 0,
                    expanded: subExpanded,
                });
                if (subExpanded) {
                    for (const acc of accounts) {
                        if (hideZero && isZero(acc.balance)) continue;
                        pushRow({
                            type: "account",
                            key: `${subFullKey}.${acc.id}`,
                            label: acc.code ? `${acc.code} ${acc.name}` : acc.name,
                            total: acc.balance || 0,
                            account: acc,
                        });
                    }
                }
            }
        }

        pushRow({
            type: "summary",
            key: "closing_balance",
            label: _t("Efectivo y equivalentes, saldo final"),
            total: data.closing_balance || 0,
        });

        if (data.unexplained_difference) {
            pushRow({
                type: "unexplained",
                key: "unexplained_difference",
                label: _t("Diferencia no explicada"),
                total: data.unexplained_difference,
            });
        }

        return rows;
    }

    onToggleCfSection(ev) {
        const key = ev.currentTarget?.getAttribute("data-section");
        if (key) this.controller.toggleCfSection(key);
    }

    async onOpenBankReconLines(ev, line) {
        ev.preventDefault();
        if (!line?.journal_id) {
            return;
        }
        const opts = this.controller.state.options || {};
        const action = await this.orm.call("bank.reconciliation.report", "action_open_journal_items", [
            line.journal_id,
            opts.date_to,
            opts.target_move || "posted",
        ]);
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    infoForCashFlow(row) {
        return {
            motor: _t("Estado de flujo de efectivo"),
            label: row.key || "",
            formula: row.label || "",
            value: this.formatAmount(row.total, this._currencySymbol()),
        };
    }

    /** Tax Report / Tax Return */
    get hideZeroLines() {
        return !!this.controller?.state?.options?.hide_zero_lines;
    }

    get hierarchyEnabled() {
        const opts = this.controller?.state?.options || {};
        return opts.hierarchy === undefined ? true : !!opts.hierarchy;
    }

    _isAmountsZero(amounts, currency) {
        if (!amounts) return true;
        for (const key of Object.keys(amounts)) {
            const a = amounts[key] || {};
            if (Math.abs(a.base || 0) > 1e-6) return false;
            if (Math.abs(a.tax || 0) > 1e-6) return false;
        }
        return true;
    }

    get taxSections() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        const sections = data.sections || {};
        const hideZero = this.hideZeroLines;
        const out = [];
        for (const key of ["sale", "purchase"]) {
            const sec = sections[key] || { label: "", taxes: [], totals: {} };
            const taxes = sec.taxes || [];
            const visibleTaxes = hideZero
                ? taxes.filter((t) => !this._isAmountsZero(t.amounts))
                : taxes;
            const hasAnyAmount = Object.values(sec.totals || {}).some(
                (v) => Math.abs(v.base || 0) > 1e-6 || Math.abs(v.tax || 0) > 1e-6
            );
            out.push({
                key,
                label: sec.label || (key === "sale" ? _t("Ventas") : _t("Compras")),
                data: sec,
                visibleTaxes,
                hasAnyAmount,
            });
        }
        return out;
    }

    get hasAnyTaxRow() {
        return this.taxSections.some(
            (sec) => sec.visibleTaxes.length > 0 || sec.hasAnyAmount
        );
    }

    get taxReturnRowsByColumn() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        const declTotals = data.declaration_totals || {};
        return [
            {
                key: "sales_tax",
                label: _t("IVA cobrado en ventas"),
                kind: "credit",
                values: this._mapColumns(declTotals, "sales_tax"),
            },
            {
                key: "purchase_tax",
                label: _t("IVA pagado en compras"),
                kind: "debit",
                values: this._mapColumns(declTotals, "purchase_tax"),
            },
            {
                key: "net_tax_due",
                label: _t("Saldo fiscal a pagar (cobrado − pagado)"),
                kind: "total",
                values: this._mapColumns(declTotals, "net_tax_due"),
            },
        ];
    }

    _mapColumns(declTotals, field) {
        const out = {};
        for (const key of Object.keys(declTotals || {})) {
            out[key] = (declTotals[key] && declTotals[key][field]) || 0;
        }
        return out;
    }

    infoForTaxRow(row) {
        const symbol = this._currencySymbol();
        const main = row.amounts?.main || Object.values(row.amounts || {})[0] || {};
        return {
            motor: _t("Reporte fiscal"),
            label: row.name || row.label || "",
            formula: row.type_tax_use === "sale"
                ? _t("Suma de balance: líneas base y de impuesto de ventas")
                : _t("Suma de balance: líneas base y de impuesto de compras"),
            value: this.formatAmount(main.tax || 0, symbol),
        };
    }

    get trialBalanceAccounts() {
        if (this.reportType !== "trial_balance") return [];
        const data = this.controller?.state?.data;
        const accounts = data?.accounts || [];
        const filter = (this.controller?.state?.options?.account_filter || "").trim().toLowerCase();
        const filtered = filter
            ? accounts.filter(
                  (acc) =>
                      (acc.code || "").toLowerCase().includes(filter) ||
                      (acc.name || "").toLowerCase().includes(filter)
              )
            : accounts;
        return filtered;
    }

    get trialBalanceGroups() {
        const accounts = this.trialBalanceAccounts;
        if (!accounts.length) return [];
        const groups = [];
        let currentGroup = null;
        for (const acc of accounts) {
            const groupKey = acc.internal_group || "asset";
            const groupLabel = acc.group_label || groupKey;
            if (!currentGroup || currentGroup.group_key !== groupKey) {
                currentGroup = { group_key: groupKey, group_label: groupLabel, accounts: [] };
                groups.push(currentGroup);
            }
            currentGroup.accounts.push(acc);
        }
        return groups;
    }

    /** Flat list of trial balance rows (group headers, accounts, group totals) from hierarchy or legacy groups. */
    get trialBalanceRows() {
        const data = this.controller?.state?.data;
        if (!data) return [];
        let rows;
        if (data.use_hierarchy && data.hierarchy?.length) {
            rows = this._flattenTrialHierarchy(data.hierarchy);
        } else {
            rows = this._legacyTrialBalanceRows();
        }
        if (!this.controller?.state?.options?.hide_zero_lines) {
            return rows;
        }
        return rows.filter((row) => {
            if (row.type === "group" || row.type === "total") {
                return true;
            }
            if (row.type !== "account") {
                return true;
            }
            const vals = [
                row.balance_inicial_raw,
                row.balance_final_raw,
                row.period_debit_raw,
                row.period_credit_raw,
            ];
            return vals.some((v) => Math.abs(Number(v || 0)) >= 0.005);
        });
    }

    _flattenTrialHierarchy(nodes) {
        const rows = [];
        const expanded = this.controller?.state?.expandedTrialGroups ?? {};
        for (const node of nodes) {
            const key = node.key;
            const isExpanded = !!expanded[key];
            if (node.type === "group") {
                rows.push({
                    type: "group",
                    key,
                    label: node.label || `${node.code} ${node.name}`.trim(),
                    level: node.level ?? 0,
                    expandable: (node.children?.length ?? 0) > 0,
                    totals: node,
                });
                if (isExpanded && node.children?.length) {
                    rows.push(...this._flattenTrialHierarchy(node.children));
                    rows.push({
                        type: "total",
                        key: `total_${key}`,
                        label: `${this._t("Total")} ${node.code} ${node.name}`.trim(),
                        level: (node.level ?? 0) + 1,
                        totals: node,
                    });
                }
            } else if (node.type === "account") {
                rows.push({
                    type: "account",
                    key: node.key,
                    level: node.level ?? 0,
                    ...node,
                });
            }
        }
        return rows;
    }

    _legacyTrialBalanceRows() {
        const groups = this.trialBalanceGroups;
        const expanded = this.controller?.state?.expandedTrialGroups ?? {};
        const rows = [];
        for (const g of groups) {
            rows.push({
                type: "group",
                key: g.group_key,
                label: g.group_label,
                level: 0,
                expandable: true,
                totals: null,
            });
            if (!!expanded[g.group_key] && g.accounts?.length) {
                for (const acc of g.accounts) {
                    rows.push({ type: "account", key: `acc_${acc.id}`, level: 1, ...acc });
                }
            }
        }
        return rows;
    }

    setup() {
        useSubEnv({
            config: {
                ...getDefaultConfig(),
                ...this.env.config,
                noBreadcrumbs: true,
            },
        });
        useSetupAction();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.reportType =
            this.props.action.context?.report_type ||
            this.props.action.context?.report ||
            "general_ledger";
        this.reportVariant = this.props.action.context?.report_variant;
        this.controller = useState(
            new BiAccountReportController(
                this.props.action,
                this.reportType,
                this.orm,
                this.actionService
            )
        );

        useChildSubEnv({
            controller: this.controller,
            reportType: this.reportType,
            reportVariant: this.props.action.context?.report_variant,
        });

        this.infoPopover = usePopover(BiInfoPopover, { position: "bottom" });
        this.annotationPopover = usePopover(BiAnnotationPopover, { position: "bottom" });

        onWillStart(async () => {
            await this.controller.load();
        });
    }

    buildDrilldownOptions(period = "current", extra = {}) {
        const o = this.controller.state.options;
        const data = this.controller.state.data;
        let date_from = o.date_from;
        let date_to = o.date_to;
        if (period && period !== "current" && period !== "comparison") {
            const match = (data?.periods || []).find((p) => p.key === period);
            if (match) {
                date_from = match.date_from;
                date_to = match.date_to;
            }
        } else if (period === "comparison") {
            const cmpPeriod = (data?.periods || []).find((p) => !p.is_current) || data?.comparison;
            if (cmpPeriod) {
                date_from = cmpPeriod.date_from;
                date_to = cmpPeriod.date_to;
            }
        }
        return {
            date_from,
            date_to,
            journal_ids: o.journal_ids || [],
            target_move: o.target_move || "all",
            comparison_filter: o.comparison_filter,
            comparison_number_period: o.comparison_number_period,
            comparison_date_from: o.comparison_date_from,
            comparison_date_to: o.comparison_date_to,
            date_filter_type: o.date_filter_type,
            drill_period: period,
            ...extra,
        };
    }

    async onDrillAccountAml(ev, accountId, period = "current") {
        ev.preventDefault();
        ev.stopPropagation();
        if (!accountId) {
            this.notification.add(_t("Cuenta no identificada"), { type: "warning" });
            return;
        }
        const opts = this.buildDrilldownOptions(period);
        const model = this.controller.modelName;
        try {
            const action = await this.orm.call(model, "action_open_aml", [opts, accountId]);
            if (action) {
                await this.actionService.doAction(action);
            } else {
                this.notification.add(_t("No hay apuntes para esta cuenta en el periodo"), { type: "info" });
            }
        } catch (e) {
            console.error("[bi_account_report] action_open_aml falló", { model, accountId, period, opts, error: e });
            this.notification.add(_t("No se pudieron cargar los apuntes: ") + (e?.message || e), { type: "danger" });
        }
    }

    async onDrillTaxAml(ev, taxId, kind, col) {
        ev.preventDefault();
        ev.stopPropagation();
        if (!taxId || !col) {
            return;
        }
        const opts = this.buildDrilldownOptions("current");
        try {
            const action = await this.orm.call("tax.report", "action_open_tax_aml", [
                opts,
                taxId,
                kind,
                col.date_from,
                col.date_to,
            ]);
            if (action) {
                await this.actionService.doAction(action);
            }
        } catch (e) {
            this.notification.add(_t("No se pudieron cargar los apuntes fiscales"), { type: "danger" });
        }
    }

    openAnnotationPopover(ev, reportType, cellKey) {
        const target = ev.currentTarget || ev.target;
        if (this.annotationPopover.isOpen) {
            this.annotationPopover.close();
        }
        this.annotationPopover.open(target, {
            reportType,
            cellKey,
            close: () => this.annotationPopover.close(),
        });
    }

    openInfoPopover(ev, info) {
        if (!info) return;
        const target = ev.currentTarget || ev.target;
        if (this.infoPopover.isOpen) {
            this.infoPopover.close();
        }
        this.infoPopover.open(target, info);
    }

    _currencySymbol() {
        return (this.controller.state.data?.currency_data || {}).symbol || "";
    }

    _formulaFromAccounts(accounts) {
        const codes = (accounts || [])
            .map((a) => a.code || a.name)
            .filter(Boolean);
        if (!codes.length) return _t("Sin cuentas");
        if (codes.length > 12) {
            return codes.slice(0, 12).join(" + ") + " + … (" + codes.length + ")";
        }
        return codes.join(" + ");
    }

    infoForBsSection(row) {
        return {
            motor: _t("Suma de saldos de cuentas"),
            label: row.key || "",
            formula: this._formulaFromAccounts(row.accounts),
            value: this.formatAmount(this.getBalanceSheetPeriodAmount(row, "current"), this._currencySymbol()),
        };
    }

    infoForBsAccount(acc) {
        return {
            motor: _t("Saldo de cuenta"),
            label: acc.code || "",
            formula: acc.name || _t("Saldo de la cuenta"),
            value: this.formatAmount(this.getBalanceSheetPeriodAmount(acc, "current"), this._currencySymbol()),
        };
    }

    infoForBsSubtotal(row) {
        return {
            motor: _t("Suma de la sección"),
            label: "total_" + (row.key || ""),
            formula: this._formulaFromAccounts(row.accounts) || row.label || "",
            value: this.formatAmount(this.getBalanceSheetPeriodAmount(row, "current"), this._currencySymbol()),
        };
    }

    infoForBsMainHeader(row) {
        const sectionKey = row.section || row.key || "";
        const sections = this._getBsSectionsForGroup(sectionKey);
        return {
            motor: _t("Agregar otras fórmulas"),
            label: sectionKey,
            formula: sections.length ? sections.join(" + ") : (row.label || ""),
            value: this.formatAmount(this.getBalanceSheetPeriodAmount(row, "current"), this._currencySymbol()),
        };
    }

    infoForBsMainTotal(row) {
        const sectionKey = row.section || row.key || "";
        const sections = this._getBsSectionsForGroup(sectionKey);
        return {
            motor: _t("Agregar otras fórmulas"),
            label: "total_" + sectionKey,
            formula: sections.length ? sections.join(" + ") : (row.label || ""),
            value: this.formatAmount(this.getBalanceSheetPeriodAmount(row, "current"), this._currencySymbol()),
        };
    }

    _getBsSectionsForGroup(groupKey) {
        const data = this.controller.state.data || {};
        const map = {
            assets: data.assets || {},
            liabilities: data.liabilities || {},
            equity: data.equity || {},
            liabilities_equity: { ...(data.liabilities || {}), ...(data.equity || {}) },
        };
        return Object.keys(map[groupKey] || {});
    }

    infoForPlSection(row) {
        const current = this.getProfitLossPeriodAmount(row, "current");
        return {
            motor: _t("Suma de saldos de cuentas"),
            label: row.key || "",
            formula: this._formulaFromAccounts(row.accounts),
            value: this.formatAmount(current, this._currencySymbol()),
        };
    }

    infoForPlAccount(acc) {
        const balance = acc.balances?.current ?? acc.balance ?? 0;
        return {
            motor: _t("Saldo de cuenta"),
            label: acc.code || "",
            formula: acc.name || _t("Saldo de la cuenta"),
            value: this.formatAmount(balance, this._currencySymbol()),
        };
    }

    infoForPlSubtotal(row) {
        const current = this.getProfitLossPeriodAmount(row, "current");
        return {
            motor: _t("Agregar otras fórmulas"),
            label: row.labelKey || row.key || "",
            formula: row.formula || row.label || "",
            value: this.formatAmount(current, this._currencySymbol()),
        };
    }

    infoForExecutiveSummary(row) {
        return {
            motor: row.motor || _t("Cálculo del resumen"),
            label: row.label || row.key || "",
            formula: row.formula || row.description || row.label || "",
            value: row.formatted || "",
        };
    }

    get display() {
        return {
            layoutActions: true,
            controlPanel: {
                layoutActions: true,
            },
        };
    }

    get periodLabel() {
        const opts = this.controller.state.options;
        const from = opts.date_from ? DateTime.fromISO(opts.date_from) : null;
        const to = opts.date_to ? DateTime.fromISO(opts.date_to) : null;
        if (from && to && opts.date_filter_type === "month") {
            return from.toLocaleString({ month: "short", year: "numeric" });
        }
        if (from && to) {
            return `${from.toLocaleString(DateTime.DATE_SHORT)} - ${to.toLocaleString(DateTime.DATE_SHORT)}`;
        }
        return "";
    }

    get periodParts() {
        const opts = this.controller.state.options;
        const from = opts.date_from ? DateTime.fromISO(opts.date_from) : null;
        const to = opts.date_to ? DateTime.fromISO(opts.date_to) : null;
        if (from && to && opts.date_filter_type === "month") {
            return {
                month: from.toLocaleString({ month: "short" }),
                year: from.toLocaleString({ year: "numeric" }),
            };
        }
        return null;
    }

    get periodHeaderLabel() {
        if (this.reportType === "balance_sheet") {
            return this.periodHeaderLabelBalanceSheet;
        }
        const opts = this.controller.state.options;
        const from = opts.date_from ? DateTime.fromISO(opts.date_from) : null;
        const to = opts.date_to ? DateTime.fromISO(opts.date_to) : null;
        if (from && to) {
            const type = opts.date_filter_type || "month";
            if (type === "month") {
                const month = from.toLocaleString({ month: "long" });
                const year = from.toLocaleString({ year: "numeric" });
                return `${month} ${year}`;
            }
            if (type === "quarter") {
                const q = Math.ceil(from.month / 3);
                return `${from.toLocaleString({ year: "numeric" })} Q${q}`;
            }
            return from.toLocaleString({ year: "numeric" });
        }
        return this.periodLabel || "";
    }

    /** Muestra columna de importe en moneda del documento (FX) en Libro mayor. */
    get glShowsFxColumn() {
        if (this.reportType !== "general_ledger") {
            return false;
        }
        const accounts = this.controller.state.data?.accounts;
        if (!accounts?.length) {
            return false;
        }
        return accounts.some((acc) => (acc.journal_items || []).some((item) => item.has_fx_line));
    }

    /** Libro de empresa / estado de cuenta: líneas con moneda distinta a compañía. */
    get partnerLedgerShowsFxColumn() {
        if (this.reportType !== "partner_ledger") {
            return false;
        }
        const partners = this.controller.state.data?.partners;
        if (!partners?.length) {
            return false;
        }
        return partners.some((p) => (p.journal_items || []).some((item) => item.has_fx_line));
    }

    async toggleLines(ev) {
        const row = ev.currentTarget.closest("tr");
        const accountName = row?.getAttribute("data-account");
        if (accountName) {
            this.controller.toggleAccount(accountName);
        }
    }

    onToggleTrialGroup(ev) {
        const groupKey = ev.currentTarget?.getAttribute("data-group");
        if (groupKey) this.controller.toggleTrialGroup(groupKey);
    }

    async togglePartnerLines(ev) {
        const row = ev.currentTarget.closest("tr");
        const partnerName = row?.getAttribute("data-partner");
        if (partnerName) {
            this.controller.togglePartner(partnerName);
        }
    }

    async onClickPartnerContact(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const partnerId = row?.getAttribute("data-partner-id");
        if (!partnerId) return;
        try {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                name: _t("Contact"),
                res_model: "res.partner",
                res_id: parseInt(partnerId, 10),
                views: [[false, "form"]],
                view_mode: "form",
                target: "current",
            });
        } finally {
            ev.currentTarget?.blur();
        }
    }

    async onClickPartnerJournalItems(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const partnerName = row?.getAttribute("data-partner");
        if (!partnerName) return;
        try {
            const records = await this.orm.searchRead(
                "account.move.line",
                [["partner_id.name", "=", partnerName]],
                ["id"]
            );
            if (records.length > 0) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: partnerName,
                    res_model: "account.move.line",
                    views: [[false, "list"], [false, "form"]],
                    view_mode: "list",
                    domain: [["id", "in", records.map((r) => r.id)]],
                    target: "new",
                });
            } else {
                this.notification.add(_t("No journal items found for this partner."), {
                    type: "warning",
                    title: _t("No Journal Items"),
                });
            }
        } finally {
            ev.currentTarget?.blur();
        }
    }

    async onClickJournalItems(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const accountId = row?.getAttribute("data-account-id");
        if (!accountId) return;

        try {
            const records = await this.orm.searchRead(
                "account.move.line",
                [["account_id", "=", parseInt(accountId, 10)]],
                ["id"]
            );
            if (records.length > 0) {
                const accountName = row?.getAttribute("data-account") || _t("Journal Items");
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: accountName,
                    res_model: "account.move.line",
                    views: [
                        [false, "list"],
                        [false, "form"],
                    ],
                    view_mode: "list",
                    domain: [["id", "in", records.map((r) => r.id)]],
                    target: "current",
                });
            } else {
                this.notification.add(_t("No journal items found for this account."), {
                    type: "warning",
                    title: _t("No Journal Items"),
                });
            }
        } finally {
            ev.currentTarget?.blur();
        }
    }

    async onClickEntry(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const lineId = row?.getAttribute("data-id");
        if (!lineId) return;

        try {
            const lineRecord = await this.orm.searchRead(
                "account.move.line",
                [["id", "=", parseInt(lineId, 10)]],
                ["move_id"]
            );
            if (
                lineRecord.length > 0 &&
                lineRecord[0].move_id &&
                lineRecord[0].move_id[0]
            ) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Journal Entry"),
                    res_model: "account.move",
                    res_id: lineRecord[0].move_id[0],
                    views: [[false, "form"]],
                    view_mode: "form",
                    target: "current",
                });
            } else {
                this.notification.add(
                    _t("No journal entry associated with this journal item."),
                    { type: "warning", title: _t("No Journal Entry Found") }
                );
            }
        } finally {
            ev.currentTarget?.blur();
        }
    }

    async onClickAnalyticItems(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const accountId = row?.getAttribute("data-account-id");
        if (!accountId) return;
        try {
            const records = await this.orm.searchRead(
                "account.analytic.line",
                [["account_id", "=", parseInt(accountId, 10)]],
                ["id"]
            );
            if (records.length > 0) {
                const accountName = row?.getAttribute("data-account") || _t("Analytic Items");
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: accountName,
                    res_model: "account.analytic.line",
                    views: [[false, "list"], [false, "form"]],
                    view_mode: "list",
                    domain: [["id", "in", records.map((r) => r.id)]],
                    target: "current",
                });
            } else {
                this.notification.add(_t("No analytic items found for this account."), {
                    type: "warning",
                    title: _t("No Analytic Items"),
                });
            }
        } finally {
            ev.currentTarget?.blur();
        }
    }

    async onClickAnalyticEntry(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest("tr");
        const lineId = row?.getAttribute("data-id");
        if (!lineId) return;
        try {
            const lineRecord = await this.orm.searchRead(
                "account.analytic.line",
                [["id", "=", parseInt(lineId, 10)]],
                ["move_line_id"]
            );
            if (!lineRecord.length || !lineRecord[0].move_line_id?.[0]) {
                this.notification.add(
                    _t("No journal entry associated with this analytic item."),
                    { type: "warning", title: _t("No Journal Entry Found") }
                );
                return;
            }
            const moveLineRecord = await this.orm.searchRead(
                "account.move.line",
                [["id", "=", lineRecord[0].move_line_id[0]]],
                ["move_id"]
            );
            if (moveLineRecord.length > 0 && moveLineRecord[0].move_id?.[0]) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Journal Entry"),
                    res_model: "account.move",
                    res_id: moveLineRecord[0].move_id[0],
                    views: [[false, "form"]],
                    view_mode: "form",
                    target: "current",
                });
            } else {
                this.notification.add(
                    _t("No journal entry associated with this analytic item."),
                    { type: "warning", title: _t("No Journal Entry Found") }
                );
            }
        } finally {
            ev.currentTarget?.blur();
        }
    }

    onClickDraftWarning(ev) {
        if (ev.type === "keydown" && ev.key !== "Enter" && ev.key !== " ") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const opts = this.controller.state.options;
        const domain = [["parent_state", "=", "draft"]];
        if (opts.date_to) {
            domain.push(["date", "<=", opts.date_to]);
        }
        if (opts.journal_ids?.length) {
            domain.push(["journal_id", "in", opts.journal_ids]);
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Unposted Journal Items"),
            res_model: "account.move.line",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list",
            domain,
            target: "current",
        });
    }
}

registry.category("actions").add("bi_account_report", BiAccountReport);
