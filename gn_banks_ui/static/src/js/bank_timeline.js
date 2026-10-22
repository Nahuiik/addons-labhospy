/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class BankTimeline extends Component {
    static template = "gn_banks_ui.BankTimeline";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ events: [], loading: true });
        onWillStart(async () => {
            await this.loadEvents();
        });
    }

    get record() {
        return this.props.record;
    }

    async loadEvents() {
        const rec = this.record;
        if (!rec.resId) {
            this.state.loading = false;
            return;
        }
        try {
            const events = await this.orm.call(
                rec.resModel,
                "get_bank_timeline_events",
                [[rec.resId]]
            );
            this.state.events = events || [];
        } finally {
            this.state.loading = false;
        }
    }
}

export const bankTimeline = {
    component: BankTimeline,
};

registry.category("view_widgets").add("bank_timeline", bankTimeline);
