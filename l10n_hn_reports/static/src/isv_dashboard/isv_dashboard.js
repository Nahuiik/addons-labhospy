/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
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

export class IsvReportDashboard extends Component {
    static template = "l10n_hn_reports.IsvReportDashboard";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const today = new Date();
        this.monthChoices = MONTH_CHOICES;
        this.state = useState({
            loading: true,
            error: null,
            payload: null,
            companyId: user.activeCompany?.id || user.defaultCompany?.id,
            year: today.getFullYear(),
            month: today.getMonth() + 1,
            creditoAnt: 0,
            retPos: 0,
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

    /** Convierte monto del input (número, string, coma decimal) para el RPC. */
    _toAmount(raw) {
        if (raw === "" || raw === null || raw === undefined) {
            return 0;
        }
        if (typeof raw === "number") {
            return Number.isFinite(raw) ? raw : 0;
        }
        const cleaned = String(raw).replace(/\s/g, "").replace(",", ".");
        const n = parseFloat(cleaned);
        return Number.isFinite(n) ? n : 0;
    }

    _wizardArgs() {
        return [
            this.state.companyId,
            this.state.year,
            this.state.month,
            this._toAmount(this.state.creditoAnt),
            this._toAmount(this.state.retPos),
        ];
    }

    /** Vuelve a cargar el resumen cuando cambia año, mes, compañía o ajustes manuales. */
    async onParamChange() {
        await this.refresh();
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.payload = await this.orm.call(
                "hn.reporte.isv.wizard",
                "get_dashboard_payload",
                this._wizardArgs()
            );
        } catch (e) {
            console.error(e);
            this.state.payload = null;
            this.state.error = e.data?.message || e.message || String(e);
        }
        this.state.loading = false;
    }

    async openPdf() {
        const action = await this.orm.call(
            "hn.reporte.isv.wizard",
            "action_dashboard_print_pdf",
            this._wizardArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    async openHtml() {
        const action = await this.orm.call(
            "hn.reporte.isv.wizard",
            "action_dashboard_print_html",
            this._wizardArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    async exportXlsx() {
        const action = await this.orm.call(
            "hn.reporte.isv.wizard",
            "action_dashboard_export_xlsx",
            this._wizardArgs()
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    async openClassicWizard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hn.reporte.isv.wizard",
            view_mode: "form",
            target: "new",
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("l10n_hn_reports_isv_dashboard", IsvReportDashboard);
