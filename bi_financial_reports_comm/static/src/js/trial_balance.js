/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class TrialBalanceReport extends Component {
    static template = "TrialBalanceReport";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            accountData: [],
            balanceData:'',
        });
        onWillStart(async () => {
            await this.fetchTrialBalanceData();
        });
    }

    async fetchTrialBalanceData() {
        let records = [];
        if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("trial.balance.report", "get_data_trial_balance", [],{'date_range': "this_financialyear"});
        }
        this.state.accountData = records[0]
        this.state.balanceData = records[1]
    }
    
    async _onClickJournalItems(ev) {
        var self=this;
        var $action = (ev.currentTarget);
        var accountName =$action.closest('tr').getAttribute('data-account');
        var accountId =$action.closest('tr').getAttribute('data-id');
                var date_from = this.state.balanceData.date_from;
        var date_to = this.state.balanceData.date_to;
        if (this.state.balanceData.journal_ids){
            var journal_ids = this.state.balanceData.journal_ids 
        }
        else{
            journal_ids = []
        }
        var domain = [['account_id', '=', parseInt(accountId)]]; 
        if (date_from) {
            domain.push(['date', '>=', date_from]);
        }
        if (date_to) {
            domain.push(['date', '<=', date_to]);
        }
        if (journal_ids.length >0) {
            domain.push(['journal_id', 'in', journal_ids]);
        }
        const records = await this.orm.searchRead('account.move.line', domain, ['id']);
        if (records.length > 0) {
            self.action.doAction({
                type: 'ir.actions.act_window',
                name: accountName,
                res_model: 'account.move.line',
                views: [[false, "list"], [false, "form"]],
                view_mode: "list",
                domain: [['id', 'in', records.map(r => r.id)]],
                target: 'current',
            });
        } else {
            self.notification.add({
                type: 'warning',
                title: 'No Journal Items',
                message: 'No journal items found for this account.',
                sticky: false,
            });
        }
    }

    async openTrialBalancePopup() {
        const ExistingFilter = await this.orm.search('trial.balance.report',[],{ limit: 1, order: "id DESC" }) || [];
        if (ExistingFilter.length > 0) {
            this.env.services.action.doAction({
                name: "Trial Balance Filters",
                type: "ir.actions.act_window",
                res_model: "trial.balance.report",
                views: [[false, "form"]],
                view_mode: "form",
                res_id: ExistingFilter[0],
                target: "new",
            });
        } else {
            this.env.services.action.doAction("bi_financial_reports_comm.action_trial_balance");
        }
    }

    async printTrialBalanceReport() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.trial_balance_pdf_report',
            report_name: 'bi_financial_reports_comm.trial_balance_pdf_report',
            data: {
                reportname: 'Trial Balance',
                accountData: this.state.accountData,
                balanceData: this.state.balanceData,
            },
            context: {
                active_model: 'trial.balance.report',
            },
        };
        return this.action.doAction(reportaction);
    }

    async printTrialBalanceXls() {
        const reportData = {
            accountData: this.state.accountData,
            balanceData: this.state.balanceData,
        };
        const data = await this.orm.call("trial.balance.report", "trial_balance_excel_report", [reportData]);
        if (data && data.excel_file) {
            const link = document.createElement('a');
            link.href = `data:application/vnd.ms-excel;base64,${data.excel_file}`;
            link.download = data.file_name || 'trial_balance.xls';
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

registry.category("actions").add("trial_balance_report_tag", TrialBalanceReport);