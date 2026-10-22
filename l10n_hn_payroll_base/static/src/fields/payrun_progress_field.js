/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { jsonField } from "@web/views/fields/json/json_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Renders the Employees → Time → Payslips progress hint for pay runs (clean-room UI).
 */
export class PayrunProgressField extends Component {
    static template = "l10n_hn_payroll_base.PayrunProgressField";
    static props = { ...standardFieldProps };

    get payload() {
        const name = this.props.name;
        const data = this.props.record?.data;
        if (!name || !data) {
            return { palette: "draft", steps: [] };
        }
        const raw = data[name];
        if (raw && typeof raw === "object" && Array.isArray(raw.steps)) {
            return raw;
        }
        return { palette: "draft", steps: [] };
    }

    /**
     * Enterprise-style: paid runs show a check inside the last node only.
     */
    showTerminalCheck(stepIndex) {
        const steps = this.payload.steps;
        if (!steps?.length) {
            return false;
        }
        return this.payload.palette === "paid" && stepIndex === steps.length - 1;
    }

    /** Pasos en curso (p. ej. borrador): mismo indicador que Enterprise (caret en el nodo activo). */
    showActiveCaret(step) {
        return step?.stage === "active";
    }

    /**
     * pending: muted node (draft tail phases). active/done: palette accent fill.
     */
    nodeClass(step) {
        if (step.stage === "pending") {
            return "o_payrun_node_pending";
        }
        return "o_payrun_node_fill";
    }
}

const payrunProgressField = {
    ...jsonField,
    component: PayrunProgressField,
    displayName: _t("Pay run progress"),
    supportedTypes: ["json"],
};

registry.category("fields").add("payrun_progress", payrunProgressField);
