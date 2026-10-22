/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import {
    formatAmount,
    formatBankDateTimeDisplay,
    m2oLabel,
} from "./bank_ui_utils";

export class BankSidePanel extends Component {
    static template = "gn_banks_ui.BankSidePanel";
    static props = ["*"];

    get data() {
        return this.props.record.data;
    }

    m2o(field) {
        return m2oLabel(this.data, field);
    }

    get creatorLabel() {
        return this.m2o("create_uid") || this.m2o("write_uid") || "—";
    }

    get validatorLabel() {
        return (
            this.m2o("validated_by") ||
            (this.data.state === "validated" ? this.m2o("write_uid") : "") ||
            "—"
        );
    }

    get validatedDateLabel() {
        return formatBankDateTimeDisplay(this.data.validated_date);
    }

    get differenceLabel() {
        if (!this.hasAmountResidual) {
            return "";
        }
        return formatAmount(this.data, "amount_residual");
    }

    get hasAmountResidual() {
        return "amount_residual" in this.data;
    }

    get showDifference() {
        return this.hasAmountResidual;
    }

    get differenceClass() {
        const residual = Math.abs(this.data.amount_residual || 0);
        return residual < 0.01 ? "gn-bk-difference--ok" : "gn-bk-difference--warn";
    }
}

export const bankSidePanel = {
    component: BankSidePanel,
    fieldDependencies: [
        { name: "create_uid", type: "many2one", relation: "res.users" },
        { name: "write_uid", type: "many2one", relation: "res.users" },
        { name: "validated_by", type: "many2one", relation: "res.users" },
        { name: "approved_by", type: "many2one", relation: "res.users" },
        { name: "validated_date", type: "datetime" },
        { name: "state", type: "selection" },
        { name: "currency_id", type: "many2one", relation: "res.currency" },
        { name: "attachment_count", type: "integer" },
        { name: "document_count", type: "integer" },
        { name: "journal_id", type: "many2one", relation: "account.journal" },
    ],
};

registry.category("view_widgets").add("bank_side_panel", bankSidePanel);
