/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatCurrency as formatCurrencyValue } from "@web/core/currency";

class PartnerAgeing extends Component {
    static template = "PartnerAgeing";
    
    async setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            partners: [],
            expandedPartners: {},
            periods: {},
            currency:{},
            PeriodTotal:''

        });
        onWillStart(async () => {
            await this.fetchPartnerAgeingData();
        });
    }

    async fetchPartnerAgeingData() {
        let records = [];
        if (this.props.action.params?.filtered_records) {
            records = this.props.action.params.filtered_records;
        } else {
            records = await this.orm.call("partner.ageing", "get_data_ageing_report", []);
        }
      
        this.state.partners = (records[0] || []).map(partner => {
            const formattedPartner = {
                ...partner,
                journal_items: partner.journal_items
            };
            
            ['period0', 'period1', 'period2', 'period3', 'period4', 'period5'].forEach(period => {
                if (!(period in formattedPartner)) {
                    formattedPartner[period] = this.formatCurrency(0);
                }
            });
            return formattedPartner;
        });
        
        this.state.periods = records[1] || {};
        if (records[2]) {
            this.state.currency = {
                symbol: records.symbol || '$',
                decimal_places: records.decimal_places || 2,
                position: records.position || 'before'
            };
        }
        this.state.PeriodTotal = records[3] || {};
    }

    async toggleLines(ev) {
        const partnerName = ev.currentTarget.closest("tr").getAttribute("data-partner");
        const currenttoggle = ev.currentTarget.querySelector("i");

        const toggleButton = document.getElementsByClassName('dropdown');
        if (this.state.expandedPartners[partnerName]) {
            delete this.state.expandedPartners[partnerName];
            currenttoggle.classList.remove("fa-caret-down");
            currenttoggle.classList.add("fa-caret-right");
            ev.currentTarget.closest("tr").style.fontWeight = "normal";
        } else {
            this.state.expandedPartners[partnerName] = true;
            currenttoggle.classList.remove("fa-caret-right");
            currenttoggle.classList.add("fa-caret-down");
            ev.currentTarget.closest("tr").style.fontWeight = "bold";
        }
    }

    async _onClickPartner(ev){
        var self=this;
        var $action = (ev.currentTarget);            
        var partnerName =$action.closest('tr').getAttribute('data-partner');
        const records = await this.orm.searchRead('res.partner', [['name', '=', partnerName]], ['id']);
        const partnerId = records[0].id;
        if (records.length > 0) {
            self.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'res.partner',
                views: [[false, "form"]],
                res_id: partnerId,
                name: "partnerName",
                view_mode: "form",
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

    async _onClickJournalItems(ev) {
        var self=this;
        var $action = (ev.currentTarget);            
        var partnerName =$action.closest('tr').getAttribute('data-partner');
        var accountType = $action.closest('tr').getAttribute('data-account-type'); 
        const domain = [['partner_id.name', '=', partnerName]];
    
        if (accountType === 'payable') {
            domain.push(['account_id.account_type', '=', 'liability_payable']);
        } else if (accountType === 'receivable') {
            domain.push(['account_id.account_type', '=', 'asset_receivable']);
        } else if (accountType === 'both') {
            domain.push(['account_id.account_type', 'in', ['liability_payable', 'asset_receivable']]);
        }
        const records = await this.orm.searchRead('account.move.line', domain , ['id']);
        if (records.length > 0) {
            self.action.doAction({
                type: 'ir.actions.act_window',
                name: "Journal Items - " + partnerName,
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
        var lineId =$action.closest('tr').getAttribute('data-id')
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

    async openAgeingPopup() {
        const ExistingFilter = await this.orm.search('partner.ageing',[],{ limit: 1, order: "id DESC" }) || [];    
            if (ExistingFilter.length > 0) {
                this.action.doAction({
                    name: "Partner Ageing Filters",
                    type: "ir.actions.act_window",
                    res_model: "partner.ageing",
                    views: [[false, "form"]],
                    view_mode: "form",
                    res_id: ExistingFilter[0],
                    target: "new",
                });
            } else {
                this.action.doAction("bi_financial_reports_comm.action_partner_ageing_report");
            }
    }

    async printAgeingReport() {
        const reportaction = {
            type: "ir.actions.report",
            report_type: 'qweb-pdf',
            report_file: 'bi_financial_reports_comm.partner_ageing_pdf_report',
            report_name: 'bi_financial_reports_comm.partner_ageing_pdf_report',
            data: {
                reportname: 'Partner Ageing Report',
                partners: this.state.partners,
                periods: this.state.periods,
                period_total: this.state.PeriodTotal,
                currency: this.state.currency,
                expandedPartners: this.state.expandedPartners,
            },
            context: {
                active_model: 'partner.ageing',
            },
        };    
        return this.action.doAction(reportaction);
    }

    async printAgeingXls() {
        const reportData = {
            partners: this.state.partners,
            expandedPartners: this.state.expandedPartners,
            periods: this.state.periods,
            currency: this.state.currency,
            PeriodTotal: this.state.PeriodTotal,
        };

        const data = await this.orm.call("partner.ageing", "partner_ageing_excel_report", [reportData]);
        if (data && data.excel_file) {
            const link = document.createElement('a');
            link.href = `data:application/vnd.ms-excel;base64,${data.excel_file}`;
            link.download = data.file_name || 'partner_ageing.xls';
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
    
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }
}

registry.category("actions").add("partner_ageing_report_tag", PartnerAgeing);


