/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DueAlertSystray extends Component {
    static template = "gn_due_alert_notifications.DueAlertSystray";
    static props = {};

    setup() {
        this.dueAlertBus = useService("gn_due_alert_bus");
        this.action = useService("action");
        this.state = useState({ pendingCount: 0 });
        this._unsubscribe = null;
        onMounted(() => {
            this._unsubscribe = this.dueAlertBus.subscribe((payload) => {
                this.state.pendingCount = payload?.pending_count || 0;
            });
        });
        onWillUnmount(() => {
            if (this._unsubscribe) {
                this._unsubscribe();
            }
        });
    }

    onClick() {
        this.action.doAction("gn_due_alert_notifications.action_gn_due_alert_notification");
    }
}

export const dueAlertSystrayItem = {
    Component: DueAlertSystray,
};

registry.category("systray").add(
    "gn_due_alert_notifications.DueAlertSystray",
    dueAlertSystrayItem,
    { sequence: 25 }
);
