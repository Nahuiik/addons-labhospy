/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { Component, useState, onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

const MONTH_CHOICES = [
    [1, "Enero"],
    [2, "Febrero"],
    [3, "Marzo"],
    [4, "Abril"],
    [5, "Mayo"],
    [6, "Junio"],
    [7, "Julio"],
    [8, "Agosto"],
    [9, "Septiembre"],
    [10, "Octubre"],
    [11, "Noviembre"],
    [12, "Diciembre"],
];

export class LibroReportDashboard extends Component {
    static template = "l10n_hn_reports.LibroReportDashboard";
    static components = { Layout, MultiRecordSelector };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const today = new Date();
        const ctx = this.props.action?.context || {};
        const defaultTipo = ctx.libro_default_tipo || ctx.default_tipo || "compras";

        this.monthChoices = MONTH_CHOICES;
        this.state = useState({
            loading: true,
            error: null,
            payload: null,
            companyId: user.activeCompany?.id || user.defaultCompany?.id,
            year: today.getFullYear(),
            month: today.getMonth() + 1,
            tipo: defaultTipo === "ventas" ? "ventas" : "compras",
            reportLayout: "estandar",
            resumenDocFiscal: false,
            resumenBorradores: false,
            branchIds: [],
            userIds: [],
        });

        onWillStart(async () => {
            if (!this.state.companyId && this.companies.length) {
                this.state.companyId = this.companies[0].id;
            }
            await this.refresh();
        });
    }

    get display() {
        return { controlPanel: {} };
    }

    get companies() {
        return user.allowedCompanies || [];
    }

    get multiCompany() {
        return (this.companies?.length || 0) > 1;
    }

    get userFilterLabel() {
        return this.state.tipo === "ventas" ? _t("Vendedores") : _t("Responsables");
    }

    get branchSelectorProps() {
        const companyId = this.state.companyId;
        return {
            resModel: "res.branch",
            resIds: this.state.branchIds,
            domain: companyId ? [["company_id", "=", companyId]] : [["id", "=", 0]],
            update: (resIds) => {
                this.state.branchIds = resIds;
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
            },
            placeholder: _t("Opcional"),
        };
    }

    _callArgs() {
        return [
            this.state.companyId,
            this.state.tipo,
            this.state.year,
            this.state.month,
            this.state.reportLayout,
            this.state.resumenDocFiscal,
            this.state.resumenBorradores,
            this.state.branchIds,
            this.state.userIds,
        ];
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.payload = await this.orm.call(
                "hn.libro.report",
                "get_libro_dashboard_preview",
                this._callArgs()
            );
        } catch (e) {
            console.error(e);
            this.state.payload = null;
            this.state.error = e.data?.message || e.message || String(e);
        }
        this.state.loading = false;
    }

    onCompanyChange() {
        this.state.branchIds = [];
        this.state.userIds = [];
    }

    async openPdf() {
        const action = await this.orm.call(
            "hn.libro.report",
            "action_libro_dashboard_print_pdf",
            this._callArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    async openHtml() {
        const action = await this.orm.call(
            "hn.libro.report",
            "action_libro_dashboard_print_html",
            this._callArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    async exportXlsx() {
        const action = await this.orm.call(
            "hn.libro.report",
            "action_libro_dashboard_export_xlsx",
            this._callArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    openClassicWizard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hn.libro.report",
            view_mode: "form",
            target: "new",
            views: [[false, "form"]],
            context: {
                default_company_id: this.state.companyId,
                default_tipo: this.state.tipo,
                default_year: this.state.year,
                default_month: String(this.state.month),
                default_report_layout: this.state.reportLayout,
                default_branch_ids: [[6, 0, this.state.branchIds]],
                default_user_ids: [[6, 0, this.state.userIds]],
                default_resumen_filtrar_documento_fiscal: this.state.resumenDocFiscal,
                default_resumen_incluir_borradores_en_totales: this.state.resumenBorradores,
            },
        });
    }

    /** ISO yyyy-mm-dd → dd/mm/yyyy para vista OWL del libro */
    fmtDate(s) {
        if (!s || typeof s !== "string") {
            return "";
        }
        const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!m) {
            return String(s);
        }
        return `${m[3]}/${m[2]}/${m[1]}`;
    }

    fmtNum(v) {
        if (v === undefined || v === null || v === "") {
            return "—";
        }
        const n = Number(v);
        if (Number.isNaN(n)) {
            return String(v);
        }
        return n.toLocaleString("es-HN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
}

registry.category("actions").add("l10n_hn_reports_libro_dashboard", LibroReportDashboard);
