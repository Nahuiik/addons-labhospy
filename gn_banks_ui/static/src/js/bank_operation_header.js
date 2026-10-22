/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { formatAmount, formatBankHeaderDate, formatBankDateTimeDisplay, m2oLabel, workflowStateLabel } from "./bank_ui_utils";

export class BankOperationHeader extends Component {
    static template = "gn_banks_ui.BankOperationHeader";
    static props = ["*"];

    get data() {
        return this.props.record.data;
    }

    get typeKey() {
        return this.data.ui_operation_type_key || "transfer";
    }

    get typeLabel() {
        return this.data.ui_operation_type_label || "Operación bancaria";
    }

    get typeIcon() {
        return this.data.ui_operation_icon || "fa-bank";
    }

    get headerClass() {
        return `gn-bk-header gn-bk-header--${this.typeKey}`;
    }

    get displayNumber() {
        return this.data.ui_document_number || "/";
    }

    get showDisplayNumber() {
        return this.displayNumber !== "/";
    }

    get stateLabel() {
        return workflowStateLabel(this.data.workflow_state);
    }

    get amountFormatted() {
        return formatAmount(this.data);
    }

    get currencyLabel() {
        return "";
    }

    get journalLabel() {
        return m2oLabel(this.data, "journal_id");
    }

    get partnerLabel() {
        return m2oLabel(this.data, "ui_partner_id") || m2oLabel(this.data, "partner_id");
    }

    get destJournalLabel() {
        return m2oLabel(this.data, "dest_journal_id");
    }

    get formattedDate() {
        return formatBankHeaderDate(this.data);
    }

    get ribbonLabel() {
        const labels = {
            draft: "Borrador",
            validated: "Validado",
            cancel: "Cancelado",
        };
        if (this.data.state && labels[this.data.state]) {
            return labels[this.data.state];
        }
        const ws = this.data.workflow_state;
        if (ws === "cancelled") {
            return "Cancelado";
        }
        if (ws === "draft" || ws === "pending_approval" || ws === "approved") {
            return "Borrador";
        }
        return "Validado";
    }

    get ribbonClass() {
        const classes = {
            draft: "text-bg-primary",
            validated: "text-bg-success",
            cancel: "text-bg-danger",
        };
        if (this.data.state && classes[this.data.state]) {
            return classes[this.data.state];
        }
        const ws = this.data.workflow_state;
        if (ws === "cancelled") {
            return "text-bg-danger";
        }
        if (ws === "draft" || ws === "pending_approval" || ws === "approved") {
            return "text-bg-primary";
        }
        return "text-bg-success";
    }
}

export const bankOperationHeader = {
    component: BankOperationHeader,
    fieldDependencies: [
        { name: "ui_document_number", type: "char" },
        { name: "name", type: "char" },
        { name: "dummy_name", type: "char" },
        { name: "state", type: "selection" },
        { name: "workflow_state", type: "selection" },
        { name: "journal_id", type: "many2one", relation: "account.journal" },
        { name: "ui_partner_id", type: "many2one", relation: "res.partner" },
        { name: "total", type: "float" },
        { name: "currency_id", type: "many2one", relation: "res.currency" },
        { name: "date", type: "date" },
        { name: "validated_date", type: "datetime" },
        { name: "write_date", type: "datetime" },
        { name: "description", type: "char" },
        { name: "ui_operation_type_key", type: "char" },
        { name: "ui_operation_type_label", type: "char" },
        { name: "ui_operation_icon", type: "char" },
    ],
};

registry.category("view_widgets").add("bank_operation_header", bankOperationHeader);
