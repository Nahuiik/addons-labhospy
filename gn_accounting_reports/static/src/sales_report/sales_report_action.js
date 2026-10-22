/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";

export class GnAccountingSalesReportAction extends Component {
    static template = "gn_accounting_reports.SalesReport";
    static props = { ...standardActionServiceProps };
    static components = { MultiRecordSelector };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const pad = (n) => String(n).padStart(2, "0");
        const d = new Date();
        const today = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const first = new Date(d.getFullYear(), d.getMonth(), 1);
        const monthStart = `${first.getFullYear()}-${pad(first.getMonth() + 1)}-01`;

        this.state = useState({
            dateFrom: monthStart,
            dateTo: today,
            companyId: null,
            branchIds: [],
            userIds: [],
            groupBy: "month",
            includeUntaxed: true,
            wizardId: null,
        });

        onWillStart(async () => {
            this.allowedCompanies = user.allowedCompanies?.length
                ? user.allowedCompanies
                : user.activeCompany
                  ? [user.activeCompany]
                  : [];
            if (!this.state.companyId) {
                const def = user.activeCompany || this.allowedCompanies[0];
                this.state.companyId = def?.id || null;
            }
        });
    }

    get branchSelectorProps() {
        const companyId = this.state.companyId;
        return {
            resModel: "res.branch",
            resIds: this.state.branchIds,
            domain: companyId ? [["company_id", "=", companyId]] : [["id", "=", 0]],
            update: (resIds) => {
                this.state.branchIds = resIds;
                this.state.wizardId = null;
            },
            placeholder: _t("Sucursales (opcional)"),
        };
    }

    get userSelectorProps() {
        const companyId = this.state.companyId;
        return {
            resModel: "res.users",
            resIds: this.state.userIds,
            domain: companyId
                ? [["company_ids", "in", companyId], ["share", "=", false]]
                : [["share", "=", false]],
            update: (resIds) => {
                this.state.userIds = resIds;
                this.state.wizardId = null;
            },
            placeholder: _t("Vendedores (opcional)"),
        };
    }

    get iframeSrc() {
        if (!this.state.wizardId) {
            return "";
        }
        return `/report/html/gn_accounting_reports.report_sales_html/${this.state.wizardId}`;
    }

    onCompanyChange(ev) {
        this.state.companyId = parseInt(ev.target.value, 10);
        this.state.branchIds = [];
        this.state.userIds = [];
        this.state.wizardId = null;
    }

    onDateFrom(ev) {
        this.state.dateFrom = ev.target.value;
        this.state.wizardId = null;
    }

    onDateTo(ev) {
        this.state.dateTo = ev.target.value;
        this.state.wizardId = null;
    }

    onGroupByChange(ev) {
        this.state.groupBy = ev.target.value;
        this.state.wizardId = null;
    }

    onIncludeUntaxed(ev) {
        this.state.includeUntaxed = ev.target.checked;
        this.state.wizardId = null;
    }

    async _ensureWizard() {
        if (!this.state.companyId || !this.state.dateFrom || !this.state.dateTo) {
            return null;
        }
        if (this.state.wizardId) {
            return this.state.wizardId;
        }
        const res = await this.orm.create("gn.accounting.sales.report.wizard", [
            {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                company_id: this.state.companyId,
                group_by: this.state.groupBy,
                include_untaxed_value: this.state.includeUntaxed,
                branch_ids: [[6, 0, this.state.branchIds]],
                user_ids: [[6, 0, this.state.userIds]],
            },
        ]);
        this.state.wizardId = Array.isArray(res) ? res[0] : res;
        return this.state.wizardId;
    }

    async refreshReport() {
        this.state.wizardId = null;
        await this._ensureWizard();
    }

    async exportPdf() {
        const wizardId = await this._ensureWizard();
        if (!wizardId) {
            return;
        }
        const act = await this.orm.call(
            "gn.accounting.sales.report.wizard",
            "action_print_pdf",
            [[wizardId]]
        );
        this.action.doAction(act);
    }

    async exportHtml() {
        const wizardId = await this._ensureWizard();
        if (!wizardId) {
            return;
        }
        const act = await this.orm.call(
            "gn.accounting.sales.report.wizard",
            "action_export_html_browser",
            [[wizardId]]
        );
        this.action.doAction(act);
    }
}

registry.category("actions").add("gn_accounting_sales_report", GnAccountingSalesReportAction);
