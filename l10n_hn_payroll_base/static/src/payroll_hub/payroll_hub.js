/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Vista cliente del centro de nómina: lista de avisos con acciones (datos vía RPC).
 */
export class PayrollHub extends Component {
    static template = "l10n_hn_payroll_base.PayrollHub";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            sectionTitle: "",
            items: [],
            error: null,
        });
        onWillStart(async () => {
            try {
                const data = await this.orm.call("hr.payslip", "get_payroll_dashboard_data", []);
                this.state.sectionTitle = data.section_title || _t("Today");
                this.state.items = data.items || [];
            } catch (e) {
                this.state.error = e;
                this.state.sectionTitle = _t("Today");
            } finally {
                this.state.loading = false;
            }
        });
    }

    get loadingLabel() {
        return _t("Loading…");
    }

    get errorLabel() {
        return _t("Could not load payroll alerts.");
    }

    get emptyLabel() {
        return _t("No alerts for now. Your payroll data looks up to date.");
    }
    openItem(act) {
        if (!act) {
            return;
        }
        this.action.doAction(act);
    }
}

registry.category("actions").add("hn_payroll_overview", PayrollHub);
