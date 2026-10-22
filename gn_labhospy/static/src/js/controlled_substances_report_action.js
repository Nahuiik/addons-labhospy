/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { Component, onWillStart, useState } from "@odoo/owl";

import { user } from "@web/core/user";

export class ControlledSubstancesReportAction extends Component {
    static template = "gn_labhospy.ControlledSubstancesReport";
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
            productIds: [],
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

    get productSelectorProps() {
        return {
            resModel: "product.product",
            resIds: this.state.productIds,
            domain: [["product_tmpl_id.gn_labhospy_is_controlled", "=", true]],
            update: (resIds) => {
                this.state.productIds = resIds;
                this.state.wizardId = null;
            },
            placeholder: _t("Producto (opcional)"),
        };
    }

    get iframeSrc() {
        if (!this.state.wizardId) {
            return "";
        }
        return `/report/html/gn_labhospy.report_controlled_substances_html/${this.state.wizardId}`;
    }

    onCompanyChange(ev) {
        const val = parseInt(ev.target.value, 10);
        this.state.companyId = val;
        this.state.branchIds = [];
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

    async refreshReport() {
        if (!this.state.companyId || !this.state.dateFrom || !this.state.dateTo) {
            return;
        }
        const res = await this.orm.create("gn.labhospy.controlled.substances.report.wizard", [
            {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                company_id: this.state.companyId,
                branch_ids: [[6, 0, this.state.branchIds]],
                product_ids: [[6, 0, this.state.productIds]],
            },
        ]);
        this.state.wizardId = Array.isArray(res) ? res[0] : res;
    }

    async exportPdf() {
        if (!this.state.wizardId) {
            await this.refreshReport();
        }
        if (!this.state.wizardId) {
            return;
        }
        const act = await this.orm.call(
            "gn.labhospy.controlled.substances.report.wizard",
            "action_print_pdf",
            [[this.state.wizardId]]
        );
        this.action.doAction(act);
    }

    async exportHtml() {
        if (!this.state.wizardId) {
            await this.refreshReport();
        }
        if (!this.state.wizardId) {
            return;
        }
        const act = await this.orm.call(
            "gn.labhospy.controlled.substances.report.wizard",
            "action_export_html_browser",
            [[this.state.wizardId]]
        );
        this.action.doAction(act);
    }

    async exportXlsx() {
        if (!this.state.wizardId) {
            await this.refreshReport();
        }
        if (!this.state.wizardId) {
            return;
        }
        const act = await this.orm.call(
            "gn.labhospy.controlled.substances.report.wizard",
            "action_export_xlsx",
            [[this.state.wizardId]]
        );
        this.action.doAction(act);
    }
}

registry
    .category("actions")
    .add("gn_labhospy_controlled_substances_report", ControlledSubstancesReportAction);
