/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatCurrency as formatCurrencyValue } from "@web/core/currency";

class BalanceSheetReport extends Component {
    static template = "BalanceSheetReport";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            balanceSheetData: {},
            expandedType: {},
            totals:{
                assets:0,
                equity:0,
                liabilities:0,
                liabilities_equity:0,
            },
            currency:'',
        });
        onWillStart(async () => {
            await this.fetchBalanceSheetData();
        });
    }

    async fetchBalanceSheetData() {
        let records = [];
        if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("balance.sheet.report", "get_data_balance_sheet", [],{'date_range': "this_financialyear"});
        }
        this.state.balanceSheetData = records;
        this.state.currency = records.currency_data
        this.state.totals = records.totals
    }

    formatCurrency(amount) {
        if (amount === undefined || amount === null || isNaN(amount)) return '';
        const cid = this.state.currency?.id;
        if (cid) {
            return formatCurrencyValue(parseFloat(amount), cid);
        }
        const formattedAmount = parseFloat(amount).toFixed(this.state.currency.decimal_places)
            .replace(/\d(?=(\d{3})+\.)/g, '$&,');
        return this.state.currency.position === 'after'
            ? `${formattedAmount} ${this.state.currency.symbol}`
            : `${this.state.currency.symbol} ${formattedAmount}`;
    }

    get currentAssetsTotal() {
        const total_bank_cash = this.state.balanceSheetData.assets.bank_cash.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_receivables = this.state.balanceSheetData.assets.receivables.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_current_assets = this.state.balanceSheetData.assets.current_assets.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_prepayments = this.state.balanceSheetData.assets.prepayments.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
    
        return total_bank_cash + total_receivables + total_current_assets + total_prepayments;
    }

    get AssetsTotalBalance() {
        const total_fixed_assets = this.state.balanceSheetData.assets.fixed_assets.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_non_current = this.state.balanceSheetData.assets.non_current.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
    
        return total_fixed_assets + total_non_current + this.currentAssetsTotalBalance;
    }

    get currentLiabilitiesTotal() {
        const total_current_liabilities = this.state.balanceSheetData.liabilities.current_liabilities.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_payables = this.state.balanceSheetData.liabilities.payables.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
        const total_credit_card = this.state.balanceSheetData.liabilities.credit_card.accounts
            ?.reduce((sum, acc) => sum + acc.balance, 0) || 0;
    
        return total_current_liabilities + total_payables + total_credit_card;
    }
    
    async toggleLines(ev) {
        const accountType = ev.currentTarget.closest("tr").getAttribute("data-type");
        const currenttoggle = ev.currentTarget.querySelector("i");
        const toggleButton = document.getElementsByClassName('dropdown');
        
        if (this.state.expandedType[accountType]) {
            delete this.state.expandedType[accountType];
            currenttoggle.classList.remove("fa-caret-down");
            currenttoggle.classList.add("fa-caret-right");
            ev.currentTarget.closest("tr").style.fontWeight = "normal";
        } else {
            this.state.expandedType[accountType] = true;
            currenttoggle.classList.remove("fa-caret-right");
            currenttoggle.classList.add("fa-caret-down");
            ev.currentTarget.closest("tr").style.fontWeight = "bold";
        }
    }

    async _onClick_GeneralLedger(ev) {
        var self=this;
        const accountName = ev.currentTarget.closest("tr").getAttribute("data-account");
        const accountId = ev.currentTarget.closest("tr").getAttribute("data-id");         
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'general_ledger_report_tag',
            name: `General Ledger - ${accountName}`,
            params: {
                balance_account_id: accountId,
                balance_account_name: accountName,
                date_from: false,
                date_to: false,
                journal_ids: false,
                target_move: 'all',
                report_type: 'general_ledger',
            },
            context: {
                reset_filters: true,
            },
            target: 'current',
        });
       
    }

    async openBalanceSheetPopup() {
        const ExistingFilter = await this.orm.search('balance.sheet.report',[],{ limit: 1, order: "id DESC" }) || [];
        
        if (ExistingFilter.length > 0) {
            this.env.services.action.doAction({
                name: "Balance Sheet Filters",
                type: "ir.actions.act_window",
                res_model: "balance.sheet.report",
                views: [[false, "form"]],
                view_mode: "form",
                res_id: ExistingFilter[0],
                target: "new",
            });
        } else {
            this.env.services.action.doAction("bi_financial_reports_comm.action_balance_sheet");
        }
    }

    async printBalanceSheet() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.balance_sheet_pdf_report',
            report_name: 'bi_financial_reports_comm.balance_sheet_pdf_report',
            res_model: 'balance.sheet.report',
            data: {
                reportname: 'Balance Sheet',
                currency: this.state.currency,
                expandedType: this.state.expandedType,
                totals: this.state.totals,
                balanceSheetData: this.state.balanceSheetData,
                AssetsTotalBalance: this.AssetsTotalBalance,
                currentAssetsTotal: this.currentAssetsTotal,
                currentLiabilitiesTotal: this.currentLiabilitiesTotal,
            },
            context: {
                active_model: 'balance.sheet.report',
            },
        };
        return this.action.doAction(reportaction);
    }

    async xlsxBalanceSheet() {
        const reportData = {
            balanceSheetData: this.state.balanceSheetData,
            expandedType: this.state.expandedType,
            totals: this.state.totals,
            currentAssetsTotal: this.currentAssetsTotal,
            AssetsTotalBalance: this.AssetsTotalBalance,
            currentLiabilitiesTotal: this.currentLiabilitiesTotal,
        };
        const data = await this.orm.call("balance.sheet.report", "balance_sheet_excel_report", [reportData]);
        if (data && data.excel_file) {
            const link = document.createElement('a');
            link.href = `data:application/vnd.ms-excel;base64,${data.excel_file}`;
            link.download = data.file_name || 'analytic_report.xls';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else {
            this.notification.add({
                type: 'warning',
                title: 'Error',
                message: 'Could not generate the XLS report.',
                sticky: false,
            });
        }
    }
}

registry.category("actions").add("balance_sheet_report_tag", BalanceSheetReport);


