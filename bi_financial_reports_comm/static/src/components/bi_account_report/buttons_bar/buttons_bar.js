/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class BiAccountReportButtonsBar extends Component {
    static template = "bi_financial_reports_comm.BiAccountReportButtonsBar";
    static props = {
        controller: { type: Object, optional: true },
    };

    get _t() {
        return _t;
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
    }

    get reportType() {
        return this.env.reportType || "general_ledger";
    }

    get controller() {
        return this.props.controller || this.env.controller;
    }

    get canPrintPdf() {
        return [
            "general_ledger",
            "partner_ledger",
            "partner_ageing",
            "analytic_report",
            "executive_summary",
            "trial_balance",
            "balance_sheet",
            "profit_loss",
            "profit_and_loss",
        ].includes(this.reportType);
    }

    get canExportXlsx() {
        return [
            "general_ledger",
            "partner_ageing",
            "partner_ledger",
            "executive_summary",
            "analytic_report",
            "trial_balance",
            "balance_sheet",
            "profit_loss",
            "profit_and_loss",
            "cash_flow",
            "tax_report",
            "tax_return",
        ].includes(this.reportType);
    }

    _sumAccountBalances(sections, keys) {
        let total = 0;
        for (const key of keys) {
            const sec = sections?.[key];
            if (sec?.total_by_period?.current != null) {
                total += Number(sec.total_by_period.current || 0);
            } else {
                for (const acc of sec?.accounts || []) {
                    total += Number(acc.balance || acc.balances?.current || 0);
                }
            }
        }
        return total;
    }

    _profitLossPdfTotals(data) {
        const income = data.income || {};
        const expense = data.expense || {};
        const incTotal = Number((income.income || {}).total || 0);
        const costRevenue = Number((expense.expense_direct_cost || {}).total || 0);
        const grossProfit = incTotal - costRevenue;
        const opExpense = Number((expense.expense || {}).total || 0);
        const operatingIncome = grossProfit - opExpense;
        const otherIncome = Number((income.income_other || {}).total || 0);
        const otherExpense = Number((expense.expense_depreciation || {}).total || 0);
        const netProfit = operatingIncome + otherIncome - otherExpense;
        return { grossProfit, operatingIncome, netProfit };
    }

    get showReportExportBar() {
        return this.canPrintPdf || this.canExportXlsx;
    }

    async printReport() {
        if (!this.controller?.state?.data) {
            this.notification.add(_t("No data to print. Load the report first."), {
                type: "warning",
                title: _t("Report"),
            });
            return;
        }
        const d = this.controller.state.data;
        try {
            if (this.reportType === "general_ledger") {
                await this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.general_ledger_pdf_report",
                    report_name: "bi_financial_reports_comm.general_ledger_pdf_report",
                    data: {
                        reportname: _t("General Ledger"),
                        accounts: d.accounts || [],
                        total_credit: d.total_credit || "0.00",
                        total_debit: d.total_debit || "0.00",
                        total_balance: d.total_balance || "0.00",
                        expanded_accounts: this.controller.state.expandedAccounts || {},
                    },
                    context: { active_model: "general.ledger.report" },
                });
            } else if (this.reportType === "partner_ageing") {
                this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.partner_ageing_pdf_report",
                    report_name: "bi_financial_reports_comm.partner_ageing_pdf_report",
                    data: {
                        receivable: d?.receivable,
                        payable: d?.payable,
                        periods: d?.periods,
                        currency_data: d?.currency_data,
                        expandedPartners: this.controller.state.expandedPartners || {},
                    },
                    context: { active_model: "partner.ageing" },
                });
            } else if (this.reportType === "partner_ledger") {
                this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.partner_ledger_pdf_report",
                    report_name: "bi_financial_reports_comm.partner_ledger_pdf_report",
                    data: {
                        reportname: _t("Partner Ledger"),
                        partners: d.partners || [],
                        total_credit: d.total_credit || "0.00",
                        total_debit: d.total_debit || "0.00",
                        total_balance: d.total_balance || "0.00",
                        expanded_partners: this.controller.state.expandedPartners || {},
                    },
                    context: { active_model: "partner.ledger.report" },
                });
            } else if (this.reportType === "executive_summary") {
                this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.executive_summary_pdf_report",
                    report_name: "bi_financial_reports_comm.executive_summary_pdf_report",
                    data: {
                        reportname: _t("Resumen ejecutivo"),
                        ...this.controller.state.data,
                    },
                    context: { active_model: "executive.summary.report" },
                });
            } else if (this.reportType === "analytic_report") {
                this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.analytic_report_pdf_report",
                    report_name: "bi_financial_reports_comm.analytic_report_pdf_report",
                    data: {
                        reportname: _t("Analytic Report"),
                        accounts: d.accounts || [],
                        total_amount: d.total_amount || "0.00",
                        date_from: d.date_from,
                        date_to: d.date_to,
                        expanded_accounts: this.controller.state.expandedAccounts || {},
                    },
                    context: { active_model: "analytic.report" },
                });
            } else if (this.reportType === "trial_balance") {
                const accounts = d.accounts || [];
                const accountData = accounts.map((a) => ({
                    code: a.code,
                    name: a.name,
                    initial_debit: a.initial_debit,
                    initial_credit: a.initial_credit,
                    period_debit: a.period_debit,
                    period_credit: a.period_credit,
                    ending_debit: a.ending_debit,
                    ending_credit: a.ending_credit,
                }));
                const balanceData = {
                    date_from: d.date_from,
                    date_to: d.date_to,
                    total_initial_debit: d.total_initial_debit,
                    total_initial_credit: d.total_initial_credit,
                    total_period_debit: d.total_period_debit,
                    total_period_credit: d.total_period_credit,
                    total_ending_debit: d.total_ending_debit,
                    total_ending_credit: d.total_ending_credit,
                };
                await this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.trial_balance_pdf_report",
                    report_name: "bi_financial_reports_comm.trial_balance_pdf_report",
                    data: {
                        accountData,
                        balanceData,
                    },
                    context: { active_model: "trial.balance.report" },
                });
            } else if (this.reportType === "balance_sheet") {
                const assets = d.assets || {};
                const liabilities = d.liabilities || {};
                const currentAssetKeys = ["bank_cash", "receivables", "current_assets", "prepayments"];
                const currentLiabKeys = ["current_liabilities", "payables", "credit_card"];
                const currentAssetsTotal = this._sumAccountBalances(assets, currentAssetKeys);
                const currentLiabilitiesTotal = this._sumAccountBalances(liabilities, currentLiabKeys);
                const fixedAssetsTotal = this._sumAccountBalances(assets, ["fixed_assets"]);
                const nonCurrentAssetsTotal = this._sumAccountBalances(assets, ["non_current"]);
                await this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.balance_sheet_pdf_report",
                    report_name: "bi_financial_reports_comm.balance_sheet_pdf_report",
                    data: {
                        reportname: _t("Balance Sheet"),
                        currency: d.currency_data || {},
                        expandedType: this.controller.state.expandedBsSections || {},
                        totals: d.totals || {},
                        balanceSheetData: d,
                        AssetsTotalBalance: fixedAssetsTotal + nonCurrentAssetsTotal + currentAssetsTotal,
                        currentAssetsTotal,
                        currentLiabilitiesTotal,
                    },
                    context: { active_model: "balance.sheet.report" },
                });
            } else if (this.reportType === "profit_loss" || this.reportType === "profit_and_loss") {
                const totals = this._profitLossPdfTotals(d);
                await this.action.doAction({
                    type: "ir.actions.report",
                    report_type: "qweb-pdf",
                    report_file: "bi_financial_reports_comm.profit_loss_pdf_report",
                    report_name: "bi_financial_reports_comm.profit_loss_pdf_report",
                    data: {
                        reportname: _t("Estado de Resultados"),
                        ProfitLossData: d,
                        currency: d.currency_data || {},
                        expandedType: this.controller.state.expandedPlSections || {},
                        grossProfitTotal: totals.grossProfit,
                        operatingIncomeTotal: totals.operatingIncome,
                        netProfitTotal: totals.netProfit,
                    },
                    context: { active_model: "profit.loss.report" },
                });
            }
        } catch (err) {
            this.notification.add(err?.message || _t("Could not generate the PDF report."), {
                type: "danger",
                title: _t("Error"),
            });
        }
    }

    async exportXls() {
        if (!this.controller?.state?.data) {
            this.notification.add(_t("No data to export. Load the report first."), {
                type: "warning",
                title: _t("Report"),
            });
            return;
        }
        const d = this.controller.state.data;
        try {
            let result;
            if (this.reportType === "general_ledger") {
                result = await this.orm.call("general.ledger.report", "general_ledger_excel_report", [
                    {
                        accounts: d.accounts || [],
                        expanded_accounts: this.controller.state.expandedAccounts || {},
                        generaltotalDebit: d.total_debit || "0.00",
                        generaltotalCredit: d.total_credit || "0.00",
                        generaltotalBalance: d.total_balance || "0.00",
                    },
                ]);
            } else if (this.reportType === "partner_ageing") {
                result = await this.orm.call("partner.ageing", "partner_ageing_excel_report", [
                    {
                        receivable: d?.receivable,
                        payable: d?.payable,
                        periods: d?.periods,
                        currency_data: d?.currency_data,
                        expanded_partners: this.controller.state.expandedPartners || {},
                    },
                ]);
            } else if (this.reportType === "partner_ledger") {
                result = await this.orm.call("partner.ledger.report", "partner_ledger_excel_report", [
                    {
                        partners: d.partners || [],
                        expanded_partners: this.controller.state.expandedPartners || {},
                        partnertotalDebit: d.total_debit || "0.00",
                        partnertotalCredit: d.total_credit || "0.00",
                        partnertotalBalance: d.total_balance || "0.00",
                    },
                ]);
            } else if (this.reportType === "executive_summary") {
                result = await this.orm.call("executive.summary.report", "executive_summary_excel_report", [
                    this.controller.state.data || {},
                ]);
            } else if (this.reportType === "analytic_report") {
                result = await this.orm.call("analytic.report", "analytic_report_excel_report", [
                    {
                        accounts: d.accounts || [],
                        expanded_accounts: this.controller.state.expandedAccounts || {},
                        total_amount: d.total_amount || "0.00",
                    },
                ]);
            } else if (this.reportType === "trial_balance") {
                result = await this.orm.call("trial.balance.report", "trial_balance_owl_xlsx", [d]);
            } else if (this.reportType === "balance_sheet") {
                result = await this.orm.call("balance.sheet.report", "balance_sheet_owl_xlsx", [d]);
            } else if (this.reportType === "profit_loss" || this.reportType === "profit_and_loss") {
                result = await this.orm.call("profit.loss.report", "profit_loss_owl_xlsx", [d]);
            } else if (this.reportType === "cash_flow") {
                result = await this.orm.call("cash.flow.report", "cash_flow_owl_xlsx", [d]);
            } else if (this.reportType === "tax_report" || this.reportType === "tax_return") {
                result = await this.orm.call("tax.report", "tax_report_owl_xlsx", [d]);
            }
            if (result?.excel_file) {
                const name = result.file_name || "Report.xls";
                const isXlsx = name.toLowerCase().endsWith(".xlsx");
                const mime = isXlsx
                    ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    : "application/vnd.ms-excel";
                const link = document.createElement("a");
                link.href = `data:${mime};base64,${result.excel_file}`;
                link.download = name;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else if (result !== undefined) {
                this.notification.add(_t("Could not generate the XLS report."), {
                    type: "warning",
                    title: _t("Error"),
                });
            }
        } catch (err) {
            this.notification.add(err?.message || _t("Could not generate the XLS report."), {
                type: "danger",
                title: _t("Error"),
            });
        }
    }
}
