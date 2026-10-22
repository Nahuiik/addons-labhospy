/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

export function fmtMoney(value, currency) {
    const num = (value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    if (!currency || !currency.symbol) {
        return num;
    }
    return currency.position === "after"
        ? `${num} ${currency.symbol}`
        : `${currency.symbol} ${num}`;
}

export function rpcErrorMessage(error, fallback = _t("Error al cargar los datos.")) {
    return error?.data?.message || error?.message || fallback;
}
