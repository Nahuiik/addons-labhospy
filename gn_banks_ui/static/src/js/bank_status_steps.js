/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { stepIndex, visibleWorkflowSteps } from "./bank_ui_utils";

export class BankStatusSteps extends Component {
    static template = "gn_banks_ui.BankStatusSteps";
    static props = ["*"];

    get data() {
        return this.props.record.data;
    }

    get steps() {
        return visibleWorkflowSteps(this.data.approval_required);
    }

    get currentIndex() {
        if (this.data.workflow_state === "cancelled") {
            return -1;
        }
        return stepIndex(this.steps, this.data.workflow_state);
    }

    get stepItems() {
        const current = this.currentIndex;
        const cancelled = this.data.workflow_state === "cancelled";
        return this.steps.map((step, index) => {
            let status = "pending";
            if (cancelled) {
                status = "cancelled";
            } else if (index < current) {
                status = "done";
            } else if (index === current) {
                status = "current";
            }
            return { ...step, status, index };
        });
    }
}

export const bankStatusSteps = {
    component: BankStatusSteps,
};

registry.category("view_widgets").add("bank_status_steps", bankStatusSteps);
