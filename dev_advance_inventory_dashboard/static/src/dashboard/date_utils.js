/** @odoo-module **/

import { parseDate, parseDateTime, formatDate, formatDateTime } from "@web/core/l10n/dates";

/** Fecha corta según locale Odoo (p. ej. 22/07/2026). */
export function formatDashboardDate(value) {
    if (!value) {
        return "";
    }
    try {
        const dt = parseDate(value);
        return dt ? formatDate(dt) : String(value);
    } catch (_e) {
        return String(value);
    }
}

/** Fecha y hora según locale Odoo (p. ej. 22/07/2026 22:58:58). */
export function formatDashboardDateTime(value) {
    if (!value) {
        return "";
    }
    try {
        const dt = parseDateTime(value);
        return dt ? formatDateTime(dt) : String(value);
    } catch (_e) {
        return String(value);
    }
}
