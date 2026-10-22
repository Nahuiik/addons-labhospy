/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Entry dashboard for accountant workflows (HN); navigation only — rules stay on the server.
 */
export class AccountantHub extends Component {
    static template = "l10n_hn_base.AccountantHub";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
    }

    async openAction(xmlId) {
        try {
            await this.action.doAction(xmlId);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }
}

registry.category("actions").add("l10n_hn_base.AccountantHub", AccountantHub);
