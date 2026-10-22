/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class GeneralLedgerReport extends Component {
    static template = "GeneralLedgerReport";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            accounts: [],
            expandedAccounts: {},
            generaltotalDebit:'',
            generaltotalCredit:'',
            generaltotalBalance:'',
        });
        onWillStart(async () => {
            await this.fetchGeneralLedgerData();
        });
    }

    async fetchGeneralLedgerData() {
        let records = [];

        if (this.props.action.params.balance_account_id) {
            records = await this.orm.call(
                "general.ledger.report", 
                "get_data_general_ledger", 
                [this.props.action.params.balance_account_id]
            );
        } else if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("general.ledger.report", "get_data_general_ledger", []);
        }
        this.state.generaltotalDebit = records[3]
        this.state.generaltotalCredit = records[2]
        this.state.generaltotalBalance = records[1]

        this.state.accounts = records[0].map(account => ({
            ...account,
            journal_items: account.journal_items || [],
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

    async _onClickJournalItems(ev) {
        var self=this;
        var $action = (ev.currentTarget);            
        var accountName =$action.closest('tr').getAttribute('data-account');
        const records = await this.orm.searchRead('account.move.line', [['account_id.name', '=', accountName]], ['id']);
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

    async _onClickEntry(ev) {
        var self=this;
        var $action = (ev.currentTarget);
        var lineId =$action.closest('tr').getAttribute('data-id');
        const lineRecord = await this.orm.searchRead('account.move.line', 
            [['id', '=', parseInt(lineId, 10)]], 
            ['move_id']
        );
        if (lineRecord.length > 0 && lineRecord[0].move_id) {
            const moveId = lineRecord[0].move_id[0];
            self.action.doAction({
                type: 'ir.actions.act_window',
                name: "Journal Entry",
                res_model: 'account.move',
                res_id: moveId,
                views: [[false, "form"]],
                view_mode: "form",
                target: 'current',
            });
        } else {
            self.notification.add({
                type: 'warning',
                title: 'No Journal Entry Found',
                message: 'No journal entry associated with this journal item.',
                sticky: false,
            });
        }
    }
    async openFilterPopup() {
        const ExistingFilter = await this.orm.search('general.ledger.report',[],{ limit: 1, order: "id DESC" });    
            if (ExistingFilter.length > 0) {
                this.env.services.action.doAction({
                    name: "General Ledger Filters",
                    type: "ir.actions.act_window",
                    res_model: "general.ledger.report",
                    views: [[false, "form"]],
                    view_mode: "form",
                    res_id: ExistingFilter[0],
                    target: "new",
                });
            } else {
                this.env.services.action.doAction("bi_financial_reports_comm.action_general_ledger");
            }
    }

    async printReport() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.general_ledger_pdf_report',
            report_name: 'bi_financial_reports_comm.general_ledger_pdf_report',
            data: {
                reportname: 'General Ledger',
                accounts: this.state.accounts,
                total_credit: this.state.generaltotalCredit,
                total_debit: this.state.generaltotalDebit,
                total_balance: this.state.generaltotalBalance,
                expanded_accounts: this.state.expandedAccounts,
            },
            context: {
                active_model: 'general.ledger.report',
            },
        };
        return this.action.doAction(reportaction);
    }

    async printXls() {
        const reportData = {
            accounts: this.state.accounts,
            expanded_accounts: this.state.expandedAccounts,
            generaltotalDebit: this.state.generaltotalDebit,
            generaltotalCredit: this.state.generaltotalCredit,
            generaltotalBalance: this.state.generaltotalBalance,
        };

        const data = await this.orm.call("general.ledger.report", "general_ledger_excel_report", [reportData]);
        if (data && data.excel_file) {
            const link = document.createElement('a');
            link.href = `data:application/vnd.ms-excel;base64,${data.excel_file}`;
            link.download = data.file_name || 'General_Ledger.xls';
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

registry.category("actions").add("general_ledger_report_tag", GeneralLedgerReport);

