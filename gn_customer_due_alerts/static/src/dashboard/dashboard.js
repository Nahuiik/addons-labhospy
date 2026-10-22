/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpcErrorMessage } from "./dashboard_utils";

const BUCKET_ORDER = ["overdue", "today", "soon", "upcoming"];
const BUCKET_ICON = {
    overdue: "fa-exclamation-triangle",
    today: "fa-bell",
    soon: "fa-clock-o",
    upcoming: "fa-calendar",
};

export class InvoiceDueDashboard extends Component {
    static template = "gn_customer_due_alerts.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            selected: "overdue",
            sending: false,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    get order() {
        return BUCKET_ORDER;
    }

    icon(key) {
        return BUCKET_ICON[key] || "fa-file";
    }

    get selectedBills() {
        const data = this.state.data;
        if (!data) {
            return [];
        }
        const bucket = data.buckets[this.state.selected];
        return (bucket && bucket.bills) || [];
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "gn.customer.due.alert",
                "get_dashboard_data",
                []
            );
            const buckets = this.state.data.buckets;
            const first =
                BUCKET_ORDER.find((key) => buckets[key] && buckets[key].count) ||
                "overdue";
            this.state.selected = first;
        } catch (error) {
            this.state.error = rpcErrorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    selectBucket(key) {
        this.state.selected = key;
    }

    async onReload() {
        await this.loadData();
    }

    openBill(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onSendAlerts() {
        if (this.state.sending) {
            return;
        }
        this.state.sending = true;
        try {
            const action = await this.orm.call(
                "gn.customer.due.alert",
                "action_send_alerts_now",
                []
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (error) {
            this.notification.add(rpcErrorMessage(error, _t("No se pudo enviar.")), {
                title: _t("Error"),
                type: "danger",
            });
        } finally {
            this.state.sending = false;
        }
    }
}

registry.category("actions").add(
    "gn_customer_due_alerts_dashboard",
    InvoiceDueDashboard
);
