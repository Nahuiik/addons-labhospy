/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatCurrency as formatCurrencyValue } from "@web/core/currency";

class ProfitLossReport extends Component {
    static template = "ProfitLossReport";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            ProfitLossData: {},
            expandedType: {},
            currency:'',
        });        
        onWillStart(async () => {
            await this.fetchProfitLossData();
        });
    }

    async fetchProfitLossData() {
        let records = [];
        if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("profit.loss.report", "get_data_profit_loss", [],{'date_range': "this_financialyear"});
        }
        this.state.ProfitLossData = records;
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

    get grossProfitTotal() {
        const total_revenue = this.state.ProfitLossData.income.income.total;
        const total_cost_of_revenue = this.state.ProfitLossData.expense.expense_direct_cost.total;
        return total_revenue - total_cost_of_revenue;
    }

    get operatingIncomeTotal() {
        const total_revenue = this.state.ProfitLossData.income.income.total;
        const total_cost_of_revenue = this.state.ProfitLossData.expense.expense_direct_cost.total;
        const total_operating_expenses = this.state.ProfitLossData.expense.expense.total;
        return total_revenue - total_cost_of_revenue - total_operating_expenses;
    }

    get netProfitTotal() {
        const total_revenue = this.state.ProfitLossData.income.income.total;
        const total_income_other = this.state.ProfitLossData.income.income_other.total;
        const total_cost_of_revenue = this.state.ProfitLossData.expense.expense_direct_cost.total;
        const total_expenses= this.state.ProfitLossData.expense.expense.total;
        const total_expense_direct_cost = this.state.ProfitLossData.expense.expense_direct_cost.total;
        return total_revenue + total_income_other - total_cost_of_revenue - total_expenses - total_expense_direct_cost;
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
                analytic_account_ids: false,
                target_move: 'all',
                report_type: 'general_ledger',
            },
            target: 'current',
        });
       
    }

    async openProfitLossPopup() {
        const ExistingFilter = await this.orm.search('profit.loss.report',[],{ limit: 1, order: "id DESC" }) || [];    
        if (ExistingFilter.length > 0) {
            this.env.services.action.doAction({
                name: "Profit and Loss Filters",
                type: "ir.actions.act_window",
                res_model: "profit.loss.report",
                views: [[false, "form"]],
                view_mode: "form",
                res_id: ExistingFilter[0],
                target: "new",
            });
        } else {
            this.env.services.action.doAction("bi_financial_reports_comm.action_profit_loss");
        }
    }

    async printProfitLoss() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.profit_loss_pdf_report',
            report_name: 'bi_financial_reports_comm.profit_loss_pdf_report',
            data: {
                reportname: 'Profit and Loss',
                ProfitLossData: this.state.ProfitLossData,
                currency: this.state.currency,
                grossProfitTotal: this.grossProfitTotal,
                operatingIncomeTotal: this.operatingIncomeTotal,
                netProfitTotal: this.netProfitTotal,
                expandedType: this.state.expandedType,
            },
            context: {
                active_model: 'profit.loss.report',
            },
        };
        return this.action.doAction(reportaction);
    }

    async xlsxProfitLoss() {
        const reportData = {
            ProfitLossData: this.state.ProfitLossData,
            currency: this.state.currency,
            grossProfitTotal: this.grossProfitTotal,
            operatingIncomeTotal: this.operatingIncomeTotal,
            netProfitTotal: this.netProfitTotal,
            expandedType: this.state.expandedType,
        };
        const data = await this.orm.call("profit.loss.report", "profit_loss_excel_report", [reportData]);
        if (data && data.excel_file) {
            const link = document.createElement('a');
            link.href = `data:application/vnd.ms-excel;base64,${data.excel_file}`;
            link.download = data.file_name || 'Profit_and_Loss.xls';
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

registry.category("actions").add("profit_loss_report_tag", ProfitLossReport);


