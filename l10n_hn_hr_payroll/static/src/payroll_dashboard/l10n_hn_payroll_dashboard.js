/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Dashboard HN sobre el motor CE: datos vía get_payroll_dashboard_data (base)
 * y get_l10n_hn_dashboard_data (local). Sin dependencias de hr_payroll Enterprise.
 */
export class L10nHnPayrollDashboard extends Component {
    static template = "l10n_hn_hr_payroll.L10nHnPayrollDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            hub: null,
            hn: null,
        });
        onWillStart(async () => {
            try {
                const [hub, hn] = await Promise.all([
                    this.orm.call("hr.payslip", "get_payroll_dashboard_data", []),
                    this.orm.call("hr.payslip", "get_l10n_hn_dashboard_data", []),
                ]);
                this.state.hub = hub;
                this.state.hn = hn;
            } catch (e) {
                this.state.error = e;
            } finally {
                this.state.loading = false;
            }
        });
    }

    get loadingLabel() {
        return _t("Loading…");
    }

    get errorLabel() {
        return _t("Could not load payroll dashboard.");
    }

    get noEmployeesText() {
        return _t("No employees in this company. Create employees before running payroll.");
    }

    get noAlertsText() {
        return _t("No alerts for now. Your payroll data looks up to date.");
    }

    openItem(action) {
        if (!action) {
            return;
        }
        this.actionService.doAction(action);
    }

    openWizard() {
        this.actionService.doAction("l10n_hn_hr_payroll.action_payroll_generation_wizard");
    }

    openPlanillas() {
        this.actionService.doAction("l10n_hn_hr_payroll.action_l10n_hn_payroll_sheet_my");
    }

    openPayRun(id) {
        if (!id) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Pay Run"),
            res_model: "hr.payslip.run",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("l10n_hn_payroll_dashboard", L10nHnPayrollDashboard);
