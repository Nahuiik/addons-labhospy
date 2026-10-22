/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpcErrorMessage } from "./dashboard_utils";

const AGING_ORDER = ["b0_30", "b31_60", "b61_90", "b90_plus"];

export class AgingDashboard extends Component {
    static template = "gn_invoice_due_alerts.AgingDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    get agingOrder() {
        return AGING_ORDER;
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "gn.invoice.due.alert",
                "get_aging_dashboard_data",
                []
            );
        } catch (error) {
            this.state.error = rpcErrorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    async onReload() {
        await this.loadData();
    }

    openPartner(id) {
        this.action.doAction("gn_invoice_due_alerts.action_invoice_due_list", {
            domain: [
                ["partner_id", "=", id],
                ["move_type", "in", ["in_invoice", "in_refund"]],
                ["state", "=", "posted"],
                ["payment_state", "in", ["not_paid", "partial"]],
                ["amount_residual", ">", 0],
            ],
            context: { search_default_overdue: 0 },
        });
    }
}

registry.category("actions").add(
    "gn_invoice_due_aging_dashboard",
    AgingDashboard
);
