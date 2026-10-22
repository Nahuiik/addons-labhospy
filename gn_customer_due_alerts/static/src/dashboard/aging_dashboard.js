/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpcErrorMessage } from "./dashboard_utils";

const AGING_ORDER = ["b0_30", "b31_60", "b61_90", "b90_plus"];

export class AgingDashboard extends Component {
    static template = "gn_customer_due_alerts.AgingDashboard";
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
                "gn.customer.due.alert",
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
        const partner = (this.state.data?.partners || []).find((p) => p.id === id);
        this.action.doAction("gn_customer_due_alerts.action_customer_due_partner_all", {
            name: partner ? `CxC - ${partner.name}` : undefined,
            domain: [
                ["partner_id", "=", id],
                ["parent_state", "=", "posted"],
                ["account_id.account_type", "=", "asset_receivable"],
                ["reconciled", "=", false],
                ["amount_residual", ">", 0],
                ["move_id.move_type", "in", ["out_invoice", "out_refund", "entry"]],
            ],
            context: { search_default_group_partner: 0 },
        });
    }
}

registry.category("actions").add(
    "gn_customer_due_aging_dashboard",
    AgingDashboard
);
