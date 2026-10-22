/** @odoo-module **/

import {
    formatMany2one,
    formatMonetary,
} from "@web/views/fields/formatters";

const { DateTime } = luxon;

/**
 * Read a many2one field value from a form record data object (Odoo 19 format).
 */
export function m2oLabel(data, fieldName) {
    const value = data[fieldName];
    if (!value) {
        return "";
    }
    if (Array.isArray(value)) {
        return value[1] || "";
    }
    if (typeof value === "object" && value.id && !value.display_name) {
        return "";
    }
    return formatMany2one(value) || "";
}

export function currencyIdFromRecord(data, currencyField = "currency_id") {
    const currency = data[currencyField];
    if (!currency) {
        return undefined;
    }
    if (Array.isArray(currency)) {
        return currency[0];
    }
    if (typeof currency === "object" && currency.id) {
        return currency.id;
    }
    return currency;
}

export function formatAmount(data, amountField = "total", currencyField = "currency_id") {
    const amount = data[amountField] || 0;
    return formatMonetary(amount, {
        currencyId: currencyIdFromRecord(data, currencyField),
    });
}

export function toLuxon(value) {
    if (!value) {
        return null;
    }
    if (value.toISO) {
        return value;
    }
    if (typeof value === "string") {
        if (value.includes("T")) {
            return DateTime.fromISO(value);
        }
        return DateTime.fromISO(`${value}T00:00:00`);
    }
    return null;
}

/** dd MMM yyyy — always includes year. */
export function formatRecordDateFull(value) {
    const dt = toLuxon(value);
    return dt ? dt.toFormat("dd MMM yyyy") : "";
}

/** h:mm a — 12-hour clock. */
export function formatRecordTime12h(value) {
    const dt = toLuxon(value);
    return dt ? dt.toFormat("h:mm a") : "";
}

/** dd MMM yyyy | h:mm a */
export function formatBankDateTimeDisplay(value) {
    const dt = toLuxon(value);
    if (!dt) {
        return "";
    }
    return `${dt.toFormat("dd MMM yyyy")} | ${dt.toFormat("h:mm a")}`;
}

/** Header operation date with optional validation time. */
export function formatBankHeaderDate(data) {
    const datePart = formatRecordDateFull(data.date);
    if (!datePart) {
        return "";
    }
    const timePart = formatRecordTime12h(data.validated_date || data.write_date);
    return timePart ? `${datePart} | ${timePart}` : datePart;
}

export function workflowStateLabel(state) {
    const labels = {
        draft: "Borrador",
        pending_approval: "Pendiente aprobación",
        approved: "Aprobado",
        validated: "Validado",
        posted: "Validado",
        reconciled: "Validado",
        cancelled: "Cancelado",
    };
    return labels[state] || state || "";
}

/** Visible workflow steps — ends at Validado (contabilización es automática). */
export const WORKFLOW_STEPS = [
    { key: "draft", label: "Borrador" },
    { key: "pending_approval", label: "Aprobación", optional: true },
    { key: "approved", label: "Aprobado", optional: true },
    { key: "validated", label: "Validado" },
];

export function visibleWorkflowSteps(approvalRequired) {
    let steps = WORKFLOW_STEPS;
    if (!approvalRequired) {
        steps = steps.filter(
            (s) => !["pending_approval", "approved"].includes(s.key)
        );
    }
    return steps;
}

export function stepIndex(steps, workflowState) {
    if (workflowState === "cancelled") {
        return -1;
    }
    if (workflowState === "posted" || workflowState === "reconciled") {
        return steps.length;
    }
    const normalized = workflowState;
    const idx = steps.findIndex((s) => s.key === normalized);
    if (idx >= 0) {
        return idx;
    }
    const order = ["draft", "pending_approval", "approved", "validated"];
    const pos = order.indexOf(normalized);
    return pos >= 0 ? pos : 0;
}
