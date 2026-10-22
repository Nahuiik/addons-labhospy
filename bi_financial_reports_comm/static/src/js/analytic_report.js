/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class AnalyticReport extends Component {
    static template = "AnalyticReport";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            analytic_accounts: [],
            expandedAccounts: {},
            TotalAmount:'',
            date_from:'',
            date_to:'',

        });    
        onWillStart(async () => {
            await this.fetchAnalyticAccountData();
        });
    }

    async fetchAnalyticAccountData() {
        let records = [];
        if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("analytic.report", "get_data_analytic_report", [],{'date_range': "this_financialyear"});
        }      
        this.state.TotalAmount = records[1]
        this.state.date_from = records[2]
        this.state.date_to = records[3]
        this.state.analytic_accounts = records[0].map(account => ({
            ...account,
            analytic_items: account.analytic_items || [],
        }));
    }
    
    async toggleLines(ev) {
        const accountName = ev.currentTarget.closest("tr").getAttribute("data-account");
        const currenttoggle = ev.currentTarget.querySelector("i");
        const toggleButton = document.getElementsByClassName('dropdown');
        if (this.state.expandedAccounts[accountName]) {
            delete this.state.expandedAccounts[accountName];
            currenttoggle.classList.remove("fa-caret-down");
            currenttoggle.classList.add("fa-caret-right");
            ev.currentTarget.closest("tr").style.fontWeight = "normal";
        } else {
            this.state.expandedAccounts[accountName] = true;
            currenttoggle.classList.remove("fa-caret-right");
            currenttoggle.classList.add("fa-caret-down");
            ev.currentTarget.closest("tr").style.fontWeight = "bold";
        }
    }


    async _onClickAnalyticItems(ev) {
        var self=this;
        var $action = (ev.currentTarget);            
        var accountName =$action.closest('tr').getAttribute('data-account');
        const records = await this.orm.searchRead('account.analytic.line', [['account_id.name', '=', accountName]], ['id']);
        if (records.length > 0) {
            self.action.doAction({
                type: 'ir.actions.act_window',
                name: accountName,
                res_model: 'account.analytic.line',
                views: [[false, "list"], [false, "form"]],
                view_mode: "list",
                domain: [['id', 'in', records.map(r => r.id)]],
                target: 'current',
            });
        } else {
            self.notification.add({
                type: 'warning',
                title: 'No Analytic Items',
                message: 'No Analytic Items found for this account.',
                sticky: false,
            });
        }
    }

    async _onClickEntry(ev) {
        var self=this;
        var $action = (ev.currentTarget);
        var lineId =$action.closest('tr').getAttribute('data-id');

        const analyticline = await this.orm.searchRead('account.analytic.line', 
            [['id', '=', parseInt(lineId, 10)]], 
            ['move_line_id']
        );
        if (!analyticline[0].move_line_id || analyticline.length===0 ){
            return self.notification.add({
                type: 'warning',
                title: 'No Journal Item Found',
                message: 'No journal item associated with this analytic item.',
                sticky: false,
            });
        }

        const movelineId = analyticline[0].move_line_id[0];
        const moveLine = await this.orm.searchRead('account.move.line', 
            [['id', '=', movelineId]], 
            ['move_id']
        );
        if (!moveLine[0].move_id || moveLine.length===0 ){
            return self.notification.add({
                type: 'warning',
                title: 'No Journal Entry Found',
                message: 'No journal entry associated with this journal item.',
                sticky: false,
            });
        }
        const moveId = moveLine[0].move_id[0];

        const move = await this.orm.searchRead('account.move', 
            [['id', '=', moveId]], ['journal_id', 'move_type']
        );
        
        const journal = await this.orm.searchRead('account.journal', 
            [['id', '=', move[0].journal_id[0]]], ['type']
        );

        if (journal.length > 0 && journal[0].type === 'bank') {
            const payment = await this.orm.searchRead('account.payment', 
            [['payment_reference', '=', move[0].name]],['id']
        );
            self.action.doAction({
                type: 'ir.actions.act_window',
                name: "Payments",
                res_model: 'account.payment',
                res_id: payment[0].id,
                views: [[false, "form"]],
                view_mode: "form",
                target: 'current',
            });
            return;
        }

        self.action.doAction({
            type: 'ir.actions.act_window',
            name: "Journal Entry",
            res_model: 'account.move',
            res_id: moveId,
            views: [[false, "form"]],
            view_mode: "form",
            target: 'current',
        });
    }

    async openAnalyticPopup() {
        const ExistingFilter = await this.orm.search('analytic.report',[],{ limit: 1, order: "id DESC" }) || [];    
        if (ExistingFilter.length > 0) {
            this.env.services.action.doAction({
                name: "Analytic Report Filters",
                type: "ir.actions.act_window",
                res_model: "analytic.report",
                views: [[false, "form"]],
                view_mode: "form",
                res_id: ExistingFilter[0],
                target: "new",
            });
        } else {
            this.env.services.action.doAction("bi_financial_reports_comm.action_analytic_report");
        }
    }

    async printReport() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.analytic_report_pdf_report',
            report_name: 'bi_financial_reports_comm.analytic_report_pdf_report',
            data: {
                reportname: 'Analytic Report',
                accounts: this.state.analytic_accounts,
                total_amount: this.state.TotalAmount,
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                expanded_accounts: this.state.expandedAccounts,
            },
            context: {
                active_model: 'analytic.report',
            },
            
        };
    
        return this.action.doAction(reportaction);
    }

    async printXls() {
        const reportData = {
            accounts: this.state.analytic_accounts,
            expanded_accounts: this.state.expandedAccounts,
            total_amount: this.state.TotalAmount,
        };
        const data = await this.orm.call("analytic.report", "analytic_report_excel_report", [reportData]);
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

registry.category("actions").add("analytic_report_tag", AnalyticReport);


