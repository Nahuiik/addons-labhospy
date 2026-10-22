/** @odoo-module **/

import { reactive } from "@odoo/owl";

const { DateTime } = luxon;

export class BiAccountReportController {
    constructor(action, reportType, orm, actionService) {
        this.action = action;
        this.reportType = reportType;
        this.orm = orm;
        this.actionService = actionService;

        const now = DateTime.now();
        const startOfMonth = now.startOf("month");
        const endOfMonth = now.endOf("month");

        this.state = reactive({
            loading: true,
            data: null,
            options: {
                date_from: startOfMonth.toISODate(),
                date_to: endOfMonth.toISODate(),
                date_filter_type: "month",
                date_filter_reference: now.toISODate(),
                journal_ids: [],
                account_ids: [],
                account_filter: "",
                analytic_filter: "",
                display_account: "movement",
                target_move: "all",
                analytic_account_ids: [],
                analytic_columns: false,
                plan_ids: [],
                account_tag_ids: [],
                partner_ids: [],
                // partner_ageing
                period_length: 30,
                account_type: "both",
                // partner_ledger: multi-select account types (trade/non-trade receivables/payables)
                account_type_ids: ["trade_receivable", "trade_payable"],
                // partner_ledger / estados financieros / balance de comprobación (Enterprise-style)
                hierarchy: true,
                unreconciled: false,
                show_fx_balance: false,
                unfold_all: false,
                based_on: "due",
                partner_tag_ids: [],
                partner_name_filter: "",
                partner_tag_name_filter: "",
                // comparison (Enterprise-style: previous period, same last year)
                comparison_filter: "no_comparison",
                comparison_number_period: 1,
                comparison_date_from: null,
                comparison_date_to: null,
                comparison_period_order: "descending",
                // cash flow: ocultar filas con balance == 0
                hide_zero_lines: false,
                report_cash_basis: false,
                horizontal_split: false,
                include_analytic_without_aml: false,
                report_currency_id: null,
            },
            expandedAccounts: {},
            expandedPartners: {},
            expandedTrialGroups: {},
            expandedPlSections: {},
            expandedPlGroups: {},
            expandedBsSections: {},
            expandedBsGroups: {},
            expandedCfSections: {},
            expandedAnalyticRows: {},
        });
    }

    toggleAnalyticRow(rowKey) {
        const next = !this.state.expandedAnalyticRows[rowKey];
        this.state.expandedAnalyticRows = {
            ...this.state.expandedAnalyticRows,
            [rowKey]: next,
        };
    }

    isAnalyticRowExpanded(rowKey) {
        return !!this.state.expandedAnalyticRows[rowKey];
    }

    get modelName() {
        const modelMap = {
            general_ledger: "general.ledger.report",
            partner_ledger: "partner.ledger.report",
            analytic_report: "analytic.report",
            executive_summary: "executive.summary.report",
            trial_balance: "trial.balance.report",
            partner_ageing: "partner.ageing",
            profit_loss: "profit.loss.report",
            profit_and_loss: "profit.loss.report",
            balance_sheet: "balance.sheet.report",
            cash_flow: "cash.flow.report",
            tax_report: "tax.report",
            tax_return: "tax.report",
            bank_reconciliation: "bank.reconciliation.report",
        };
        return modelMap[this.reportType] || "general.ledger.report";
    }

    async load() {
        this.state.loading = true;
        try {
            const filterOpts = this.action.context?.filter_options;
            if (filterOpts && !this.state.data) {
                Object.assign(this.state.options, filterOpts);
            }
            if (this.action.params?.filtered_records) {
                this.state.data = this._adaptFilteredRecords(
                    this.action.params.filtered_records
                );
                const opts = this.action.context?.filter_options || {};
                Object.assign(this.state.options, opts);
            } else {
                const opts = this.state.options;
                let context = {
                    ...opts,
                    journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                    account_ids: opts.account_ids || undefined,
                    account_filter: (opts.account_filter || "").trim() || undefined,
                    analytic_filter: (opts.analytic_filter || "").trim() || undefined,
                    analytic_account_ids: opts.analytic_account_ids || undefined,
                    partner_ids: opts.partner_ids || undefined,
                };
                if (this.reportType === "partner_ledger") {
                    context = {
                        ...context,
                        account_type_ids: opts.account_type_ids || ["trade_receivable", "trade_payable"],
                        partner_name_filter: (opts.partner_name_filter || "").trim() || undefined,
                        partner_tag_name_filter: (opts.partner_tag_name_filter || "").trim() || undefined,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        unreconciled: opts.unreconciled || false,
                        unfold_all: opts.unfold_all || false,
                    };
                }
                if (this.reportType === "partner_ageing") {
                    context = {
                        ...context,
                        on_date: opts.date_to || opts.date_from,
                        period_length: opts.period_length ?? 30,
                        account_type: opts.account_type || "both",
                        partner_ids: opts.partner_ids || [],
                        partner_tag_ids: opts.partner_tag_ids || [],
                        partner_name_filter: (opts.partner_name_filter || "").trim() || undefined,
                        partner_tag_name_filter: (opts.partner_tag_name_filter || "").trim() || undefined,
                        account_ids: opts.account_ids || [],
                        based_on: opts.based_on || "due",
                        target_move: opts.target_move || "posted",
                    };
                }
                if (this.reportType === "trial_balance") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        account_ids: opts.account_ids || undefined,
                        partner_ids: opts.partner_ids || undefined,
                        account_tag_ids: opts.account_tag_ids || undefined,
                        account_filter: (opts.account_filter || "").trim() || undefined,
                        analytic_filter: (opts.analytic_filter || "").trim() || undefined,
                        display_account: opts.display_account || "movement",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        date_filter_type: opts.date_filter_type || "month",
                        hierarchy: !!opts.hierarchy,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        report_cash_basis: !!opts.report_cash_basis,
                        include_analytic_without_aml: !!opts.include_analytic_without_aml,
                        analytic_account_ids: opts.analytic_account_ids?.length ? opts.analytic_account_ids : undefined,
                        analytic_columns: !!opts.analytic_columns,
                        plan_ids: opts.plan_ids?.length ? opts.plan_ids : undefined,
                    };
                }
                if (this.reportType === "profit_loss" || this.reportType === "profit_and_loss") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        display_account: opts.display_account || "movement",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        date_filter_type: opts.date_filter_type || "month",
                        hierarchy: !!opts.hierarchy,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        report_cash_basis: !!opts.report_cash_basis,
                        include_analytic_without_aml: !!opts.include_analytic_without_aml,
                        analytic_account_ids: opts.analytic_account_ids?.length ? opts.analytic_account_ids : undefined,
                        analytic_columns: !!opts.analytic_columns,
                        plan_ids: opts.plan_ids?.length ? opts.plan_ids : undefined,
                    };
                }
                if (this.reportType === "balance_sheet") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        display_account: opts.display_account || "movement",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        date_filter_type: opts.date_filter_type || "month",
                        hierarchy: !!opts.hierarchy,
                        show_fx_balance: !!opts.show_fx_balance,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        report_cash_basis: !!opts.report_cash_basis,
                        horizontal_split: !!opts.horizontal_split,
                        include_analytic_without_aml: !!opts.include_analytic_without_aml,
                        analytic_account_ids: opts.analytic_account_ids?.length ? opts.analytic_account_ids : undefined,
                        analytic_columns: !!opts.analytic_columns,
                        plan_ids: opts.plan_ids?.length ? opts.plan_ids : undefined,
                    };
                }
                if (this.reportType === "cash_flow") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        date_filter_type: opts.date_filter_type || "month",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        hierarchy: !!opts.hierarchy,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        unfold_all: !!opts.unfold_all,
                    };
                }
                if (this.reportType === "bank_reconciliation") {
                    context = {
                        ...context,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "posted",
                    };
                }
                if (this.reportType === "tax_report" || this.reportType === "tax_return") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "posted",
                        date_filter_type: opts.date_filter_type || "month",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        hierarchy: !!opts.hierarchy,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        unfold_all: !!opts.unfold_all,
                    };
                }
                if (this.reportType === "executive_summary") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        target_move: opts.target_move || "all",
                        comparison_filter: opts.comparison_filter || "no_comparison",
                        comparison_number_period: opts.comparison_number_period || 1,
                        comparison_date_from: opts.comparison_date_from,
                        comparison_date_to: opts.comparison_date_to,
                        comparison_period_order: opts.comparison_period_order || "descending",
                        date_filter_type: opts.date_filter_type || "month",
                        hierarchy: !!opts.hierarchy,
                        hide_zero_lines: !!opts.hide_zero_lines,
                        report_cash_basis: !!opts.report_cash_basis,
                        include_analytic_without_aml: !!opts.include_analytic_without_aml,
                        analytic_account_ids: opts.analytic_account_ids?.length ? opts.analytic_account_ids : undefined,
                        plan_ids: opts.plan_ids?.length ? opts.plan_ids : undefined,
                    };
                }
                if (this.reportType === "analytic_report") {
                    context = {
                        ...context,
                        date_from: opts.date_from,
                        date_to: opts.date_to,
                        journal_ids: opts.journal_ids?.length ? opts.journal_ids : undefined,
                        account_ids: opts.account_ids || undefined,
                        partner_ids: opts.partner_ids || undefined,
                        account_tag_ids: opts.account_tag_ids || undefined,
                        plan_ids: opts.plan_ids || undefined,
                        analytic_account_ids: opts.analytic_account_ids || undefined,
                        analytic_filter: (opts.analytic_filter || "").trim() || undefined,
                    };
                }
                if (
                    opts.report_currency_id &&
                    [
                        "balance_sheet",
                        "profit_loss",
                        "profit_and_loss",
                        "trial_balance",
                        "cash_flow",
                        "tax_report",
                        "tax_return",
                        "executive_summary",
                    ].includes(this.reportType)
                ) {
                    context.report_currency_id = opts.report_currency_id;
                }
                const result = await this.orm.call(
                    this.modelName,
                    this._getDataMethod(),
                    [],
                    { context }
                );
                this.state.data = this._adaptResult(result);
            }
            if (this.reportType === "partner_ledger" && this.state.data?.partners) {
                if (this.state.options.unfold_all) {
                    const expanded = { ...this.state.expandedPartners };
                    for (const p of this.state.data.partners) {
                        if (p?.name) expanded[p.name] = true;
                    }
                    this.state.expandedPartners = expanded;
                } else {
                    this.state.expandedPartners = {};
                }
            }
            if (this.reportType === "trial_balance") {
                this._applyTrialBalanceUnfoldAll();
            }
            if (
                this.reportType === "balance_sheet" ||
                this.reportType === "profit_loss" ||
                this.reportType === "profit_and_loss" ||
                this.reportType === "cash_flow"
            ) {
                this._applyStatementUnfoldAll();
            }
        } finally {
            this.state.loading = false;
        }
    }

    _getDataMethod() {
        const methodMap = {
            general_ledger: "get_data_general_ledger",
            partner_ledger: "get_data_partner_ledger",
            analytic_report: "get_data_analytic_report",
            executive_summary: "get_data_executive_summary",
            trial_balance: "get_data_trial_balance",
            partner_ageing: "get_data_ageing_report",
            profit_loss: "get_data_profit_loss",
            profit_and_loss: "get_data_profit_loss",
            balance_sheet: "get_data_balance_sheet",
            cash_flow: "get_data_cash_flow",
            tax_report: "get_data_tax_report",
            tax_return: "get_data_tax_report",
            bank_reconciliation: "get_data_bank_reconciliation",
        };
        return methodMap[this.reportType] || "get_data_general_ledger";
    }

    _adaptResult(result) {
        if (this.reportType === "general_ledger") {
            return {
                accounts: result[0] || [],
                total_balance: result[1] || "0.00",
                total_credit: result[2] || "0.00",
                total_debit: result[3] || "0.00",
                total_balance_negative: result[4] || false,
                has_draft_warning: result[5] || false,
            };
        }
        if (this.reportType === "partner_ledger") {
            return {
                partners: result[0] || [],
                total_balance: result[1] || "0.00",
                total_credit: result[2] || "0.00",
                total_debit: result[3] || "0.00",
                total_balance_negative: result[4] || false,
                total_debit_negative: result[5] || false,
                total_credit_negative: result[6] || false,
                has_draft_warning: result[7] || false,
            };
        }
        if (this.reportType === "trial_balance") {
            const accounts = Array.isArray(result[0]) ? result[0] : [];
            const balanceDict = result[1] || {};
            return {
                accounts,
                hierarchy: balanceDict.hierarchy || [],
                use_hierarchy: balanceDict.use_hierarchy || false,
                total_initial_debit: balanceDict.total_initial_debit || "0.00",
                total_initial_credit: balanceDict.total_initial_credit || "0.00",
                total_period_debit: balanceDict.total_period_debit || "0.00",
                total_period_credit: balanceDict.total_period_credit || "0.00",
                total_ending_debit: balanceDict.total_ending_debit || "0.00",
                total_ending_credit: balanceDict.total_ending_credit || "0.00",
                total_balance_inicial: balanceDict.total_balance_inicial || "0.00",
                total_balance_inicial_negative: balanceDict.total_balance_inicial_negative || false,
                total_balance_final: balanceDict.total_balance_final || "0.00",
                total_balance_final_negative: balanceDict.total_balance_final_negative || false,
                date_from: balanceDict.date_from,
                date_to: balanceDict.date_to,
                has_draft_warning: balanceDict.has_draft_warning || false,
                currency_data: balanceDict.currency || {},
                report_currency_note: balanceDict.report_currency_note || "",
                column_mode: balanceDict.column_mode,
                columns: balanceDict.columns || [],
                analytic_matrix: balanceDict.analytic_matrix || null,
            };
        }
        if (this.reportType === "profit_loss" || this.reportType === "profit_and_loss") {
            return result;
        }
        if (this.reportType === "balance_sheet") {
            return result;
        }
        if (this.reportType === "cash_flow") {
            return result;
        }
        if (this.reportType === "tax_report" || this.reportType === "tax_return") {
            return result;
        }
        if (this.reportType === "bank_reconciliation") {
            return result;
        }
        if (this.reportType === "analytic_report") {
            const accounts = Array.isArray(result[0]) ? result[0] : [];
            const extra = result[4] || {};
            return {
                accounts,
                total_amount: result[1] || "0.00",
                date_from: result[2],
                date_to: result[3],
                total_amount_negative: extra.total_amount_negative || false,
            };
        }
        return result;
    }

    _adaptFilteredRecords(records) {
        if (!Array.isArray(records)) return records;
        if (records.length >= 4) {
            if (this.reportType === "general_ledger") {
                return {
                    accounts: records[0] || [],
                    total_balance: records[1] || "0.00",
                    total_credit: records[2] || "0.00",
                    total_debit: records[3] || "0.00",
                    total_balance_negative: records[4] || false,
                    has_draft_warning: records[5] || false,
                };
            }
            if (this.reportType === "partner_ledger") {
                const hasNewFormat = records.length >= 8;
                return {
                    partners: records[0] || [],
                    total_balance: records[1] || "0.00",
                    total_credit: records[2] || "0.00",
                    total_debit: records[3] || "0.00",
                    total_balance_negative: hasNewFormat ? (records[4] || false) : false,
                    total_debit_negative: hasNewFormat ? (records[5] || false) : false,
                    total_credit_negative: hasNewFormat ? (records[6] || false) : false,
                    has_draft_warning: hasNewFormat ? (records[7] || false) : (records[4] || false),
                };
            }
        }
        if (records.length === 1 && Array.isArray(records[0])) {
            const base = {
                total_balance: "0.00",
                total_credit: "0.00",
                total_debit: "0.00",
                total_balance_negative: false,
                total_debit_negative: false,
                total_credit_negative: false,
            };
            if (this.reportType === "general_ledger") {
                return { ...base, accounts: records[0] };
            }
            if (this.reportType === "partner_ledger") {
                return { ...base, partners: records[0], has_draft_warning: false };
            }
        }
        if (this.reportType === "analytic_report" && records.length >= 4) {
            const accounts = Array.isArray(records[0]) ? records[0] : [];
            const extra = records[4] || {};
            return {
                accounts,
                total_amount: records[1] || "0.00",
                date_from: records[2],
                date_to: records[3],
                total_amount_negative: extra.total_amount_negative || false,
            };
        }
        if (records.length >= 2 && this.reportType === "trial_balance") {
            const accounts = Array.isArray(records[0]) ? records[0] : [];
            const balanceDict = records[1] || {};
            return {
                accounts,
                hierarchy: balanceDict.hierarchy || [],
                use_hierarchy: balanceDict.use_hierarchy || false,
                total_initial_debit: balanceDict.total_initial_debit || "0.00",
                total_initial_credit: balanceDict.total_initial_credit || "0.00",
                total_period_debit: balanceDict.total_period_debit || "0.00",
                total_period_credit: balanceDict.total_period_credit || "0.00",
                total_ending_debit: balanceDict.total_ending_debit || "0.00",
                total_ending_credit: balanceDict.total_ending_credit || "0.00",
                total_balance_inicial: balanceDict.total_balance_inicial || "0.00",
                total_balance_inicial_negative: balanceDict.total_balance_inicial_negative || false,
                total_balance_final: balanceDict.total_balance_final || "0.00",
                total_balance_final_negative: balanceDict.total_balance_final_negative || false,
                date_from: balanceDict.date_from,
                date_to: balanceDict.date_to,
                has_draft_warning: balanceDict.has_draft_warning || false,
                currency_data: balanceDict.currency || {},
                column_mode: balanceDict.column_mode,
                columns: balanceDict.columns || [],
                analytic_matrix: balanceDict.analytic_matrix || null,
            };
        }
        return records;
    }

    async setOptions(newOptions, { reload = true } = {}) {
        this.state.options = { ...this.state.options, ...newOptions };
        if (reload) {
            await this.load();
        }
    }

    toggleUnfoldAll() {
        this.setUnfoldAll(!this.state.options.unfold_all);
    }

    setUnfoldAll(unfold) {
        this.state.options = { ...this.state.options, unfold_all: !!unfold };
        this._syncExpandedFromUnfoldAll();
    }

    unfoldAll() {
        this.setUnfoldAll(true);
    }

    foldAll() {
        this.setUnfoldAll(false);
    }

    _syncExpandedFromUnfoldAll() {
        const unfold = !!this.state.options.unfold_all;
        if (
            this.reportType === "balance_sheet" ||
            this.reportType === "profit_loss" ||
            this.reportType === "profit_and_loss" ||
            this.reportType === "cash_flow"
        ) {
            this._applyStatementUnfoldAll();
            return;
        }
        if (this.reportType === "trial_balance") {
            this._applyTrialBalanceUnfoldAll();
            return;
        }
        if (this.reportType === "partner_ledger") {
            if (unfold && this.state.data?.partners) {
                const expanded = {};
                for (const p of this.state.data.partners) {
                    if (p?.name) expanded[p.name] = true;
                }
                this.state.expandedPartners = expanded;
            } else {
                this.state.expandedPartners = {};
            }
            return;
        }
        if (this.reportType === "general_ledger") {
            if (unfold && this.state.data?.accounts) {
                const expanded = {};
                for (const acc of this.state.data.accounts) {
                    const key = acc?.code ? `${acc.code} ${acc.name}` : acc?.name;
                    if (key) expanded[key] = true;
                }
                this.state.expandedAccounts = expanded;
            } else {
                this.state.expandedAccounts = {};
            }
        }
    }

    toggleAccount(accountName) {
        if (this.state.expandedAccounts[accountName]) {
            delete this.state.expandedAccounts[accountName];
        } else {
            this.state.expandedAccounts[accountName] = true;
        }
    }

    togglePartner(partnerName) {
        if (this.state.expandedPartners[partnerName]) {
            delete this.state.expandedPartners[partnerName];
        } else {
            this.state.expandedPartners[partnerName] = true;
        }
    }

    toggleTrialGroup(groupKey) {
        if (this.state.expandedTrialGroups[groupKey]) {
            delete this.state.expandedTrialGroups[groupKey];
        } else {
            this.state.expandedTrialGroups[groupKey] = true;
        }
    }

    isTrialGroupExpanded(groupKey) {
        return !!this.state.expandedTrialGroups[groupKey];
    }

    togglePlGroup(groupKey) {
        const next = !this.isPlGroupExpanded(groupKey);
        this.state.expandedPlGroups = { ...this.state.expandedPlGroups, [groupKey]: next };
    }

    isPlGroupExpanded(groupKey) {
        return !!this.state.expandedPlGroups[groupKey];
    }

    _collectPlGroupKeysFromHierarchy(nodes, out = []) {
        if (!nodes?.length) return out;
        for (const node of nodes) {
            if (node.type === "group" && node.key) {
                out.push(node.key);
                this._collectPlGroupKeysFromHierarchy(node.children || [], out);
            }
        }
        return out;
    }

    _collectPlGroupKeysFromData() {
        const data = this.state.data;
        if (!data) return [];
        const keys = [];
        const buckets = [data.income || {}, data.expense || {}];
        for (const bucket of buckets) {
            for (const sec of Object.values(bucket)) {
                if (sec?.use_hierarchy && sec?.hierarchy?.length) {
                    this._collectPlGroupKeysFromHierarchy(sec.hierarchy, keys);
                }
            }
        }
        return keys;
    }

    togglePlSection(sectionKey) {
        const next = !this.isPlSectionExpanded(sectionKey);
        this.state.expandedPlSections = { ...this.state.expandedPlSections, [sectionKey]: next };
    }

    isPlSectionExpanded(sectionKey) {
        return !!this.state.expandedPlSections[sectionKey];
    }

    toggleBsGroup(groupKey) {
        const next = !this.isBsGroupExpanded(groupKey);
        this.state.expandedBsGroups = { ...this.state.expandedBsGroups, [groupKey]: next };
    }

    isBsGroupExpanded(groupKey) {
        return !!this.state.expandedBsGroups[groupKey];
    }

    _collectBsGroupKeysFromData() {
        const data = this.state.data;
        if (!data) return [];
        const keys = [];
        const buckets = [data.assets || {}, data.liabilities || {}, data.equity || {}];
        for (const bucket of buckets) {
            for (const sec of Object.values(bucket)) {
                if (sec?.use_hierarchy && sec?.hierarchy?.length) {
                    this._collectPlGroupKeysFromHierarchy(sec.hierarchy, keys);
                }
            }
        }
        return keys;
    }

    toggleBsSection(sectionKey) {
        const next = !this.isBsSectionExpanded(sectionKey);
        this.state.expandedBsSections = { ...this.state.expandedBsSections, [sectionKey]: next };
    }

    isBsSectionExpanded(sectionKey) {
        return !!this.state.expandedBsSections[sectionKey];
    }

    toggleCfSection(sectionKey) {
        const next = !this.isCfSectionExpanded(sectionKey);
        this.state.expandedCfSections = { ...this.state.expandedCfSections, [sectionKey]: next };
    }

    isCfSectionExpanded(sectionKey) {
        return !!this.state.expandedCfSections[sectionKey];
    }

    _collectTrialGroupKeys(nodes, out = []) {
        if (!nodes?.length) return out;
        for (const node of nodes) {
            if (node.type === "group" && node.key) {
                out.push(node.key);
                this._collectTrialGroupKeys(node.children || [], out);
            }
        }
        return out;
    }

    _applyTrialBalanceUnfoldAll() {
        const data = this.state.data;
        if (!data || this.reportType !== "trial_balance") return;
        let keys = [];
        if (data.use_hierarchy && data.hierarchy?.length) {
            keys = this._collectTrialGroupKeys(data.hierarchy);
        } else {
            const seen = new Set();
            for (const acc of data.accounts || []) {
                const g = acc.internal_group || "asset";
                if (!seen.has(g)) {
                    seen.add(g);
                    keys.push(g);
                }
            }
        }
        if (!keys.length) return;
        if (this.state.options.unfold_all) {
            const next = {};
            for (const k of keys) next[k] = true;
            this.state.expandedTrialGroups = next;
        } else {
            this.state.expandedTrialGroups = {};
        }
    }

    _balanceSheetSectionKeys() {
        return [
            "bank_cash",
            "receivables",
            "current_assets",
            "prepayments",
            "fixed_assets",
            "non_current",
            "payables",
            "credit_card",
            "current_liabilities",
            "non_current_liabilities",
            "equity",
            "current_year_earnings",
        ];
    }

    _profitLossSectionKeys() {
        return [
            "income",
            "expense_direct_cost",
            "expense",
            "income_other",
            "expense_depreciation",
        ];
    }

    _applyStatementUnfoldAll() {
        const unfold = !!this.state.options.unfold_all;
        if (this.reportType === "balance_sheet") {
            if (!unfold) {
                this.state.expandedBsSections = {};
                this.state.expandedBsGroups = {};
                return;
            }
            const nextSections = {};
            for (const k of this._balanceSheetSectionKeys()) nextSections[k] = true;
            this.state.expandedBsSections = nextSections;
            const groupKeys = this._collectBsGroupKeysFromData();
            const nextGroups = {};
            for (const k of groupKeys) nextGroups[k] = true;
            this.state.expandedBsGroups = nextGroups;
        }
        if (this.reportType === "profit_loss" || this.reportType === "profit_and_loss") {
            if (!unfold) {
                this.state.expandedPlSections = {};
                this.state.expandedPlGroups = {};
                return;
            }
            const nextSections = {};
            for (const k of this._profitLossSectionKeys()) nextSections[k] = true;
            this.state.expandedPlSections = nextSections;
            const groupKeys = this._collectPlGroupKeysFromData();
            const nextGroups = {};
            for (const k of groupKeys) nextGroups[k] = true;
            this.state.expandedPlGroups = nextGroups;
        }
        if (this.reportType === "cash_flow") {
            if (!unfold) {
                this.state.expandedCfSections = {};
                return;
            }
            const data = this.state.data || {};
            const sections = data.sections || {};
            const next = {};
            for (const sk of Object.keys(sections)) {
                next[sk] = true;
                const subs = sections[sk]?.subsections || {};
                for (const sub of Object.keys(subs)) {
                    next[`${sk}.${sub}`] = true;
                }
            }
            this.state.expandedCfSections = next;
        }
    }

    get reportTitle() {
        const titles = {
            general_ledger: "General Ledger",
            partner_ledger: "Partner Ledger",
            analytic_report: "Analytic Account Report",
            executive_summary: "Resumen ejecutivo",
            trial_balance: "Trial Balance",
            partner_ageing: "Partner Ageing",
            profit_loss: "Estado de Resultados",
            profit_and_loss: "Estado de Resultados",
            balance_sheet: "Balance general",
            cash_flow: "Estado de flujo de efectivo",
            tax_report: "Reporte fiscal",
            tax_return: "Declaración fiscal",
        };
        return titles[this.reportType] || "Financial Report";
    }
}
