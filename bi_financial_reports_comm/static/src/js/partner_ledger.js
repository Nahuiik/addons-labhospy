/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class PartnerLedgerReport extends Component {
	static template = "PartnerLedgerReport";
	
	async setup() {
		this.orm = useService("orm");
		this.notification = useService("notification");
		this.action = useService("action");
		this.state = useState({
			partners: [],
			expandedPartners: {},
			partnertotalDebit:'',
			partnertotalCredit:'',
			partnertotalBalance:'',

		});        
		onWillStart(async () => {
			await this.fetchPartnerLedgerData();
		});
	}

	async fetchPartnerLedgerData() {
		let records = [];
		if (this.props.action.params?.filtered_records) {
			records = this.props.action.params.filtered_records;
		} else {
			records = await this.orm.call("partner.ledger.report", "get_data_partner_ledger", []);
		}
		this.state.partnertotalDebit = records[3]
		this.state.partnertotalCredit = records[2]
		this.state.partnertotalBalance = records[1]
		this.state.partners = records[0].filter(partner => partner.journal_items && partner.journal_items.length > 0).map(partner => ({
			...partner,
			journal_items: partner.journal_items,
		}));
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

	async _onClickJournalItems(ev) {
		var self=this;
		var $action = (ev.currentTarget);            
		var partnerName =$action.closest('tr').getAttribute('data-partner');
		const records = await this.orm.searchRead('account.move.line', [['partner_id.name', '=', partnerName],['account_id.account_type', 'in', ['liability_payable', 'asset_receivable']]], ['id']);
		if (records.length > 0) {
			self.action.doAction({
				type: 'ir.actions.act_window',
				name: partnerName,
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
		const ExistingFilter = await this.orm.search('partner.ledger.report',[],{ limit: 1, order: "id DESC" }) || [];    
			if (ExistingFilter.length > 0) {
				this.env.services.action.doAction({
					name: "partner Ledger Filters",
					type: "ir.actions.act_window",
					res_model: "partner.ledger.report",
					views: [[false, "form"]],
					view_mode: "form",
					res_id: ExistingFilter[0],
					target: "new",
				});
			} else {
				this.env.services.action.doAction("bi_financial_reports_comm.action_partner_ledger");
			}
	}

	async printReport() {
		const reportaction = {
			type: "ir.actions.report",
			report_type: 'qweb-pdf',
			report_file: 'bi_financial_reports_comm.partner_ledger_pdf_report',
			report_name: 'bi_financial_reports_comm.partner_ledger_pdf_report',
			data: {
				reportname: 'partner Ledger',
				partners: this.state.partners,
				total_credit: this.state.partnertotalCredit,
				total_debit: this.state.partnertotalDebit,
				total_balance: this.state.partnertotalBalance,
				expanded_partners: this.state.expandedPartners,
			},
			context: {
				active_model: 'partner.ledger.report',
			},
			
		};    
		return this.action.doAction(reportaction);
	}

	async printXls() {
		const reportData = {
			partners: this.state.partners,
			expanded_partners: this.state.expandedPartners,
			partnertotalDebit: this.state.partnertotalDebit,
			partnertotalCredit: this.state.partnertotalCredit,
			partnertotalBalance: this.state.partnertotalBalance,
		};

		const data = await this.orm.call("partner.ledger.report", "partner_ledger_excel_report", [reportData]);
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

registry.category("actions").add("partner_ledger_report_tag", PartnerLedgerReport);

