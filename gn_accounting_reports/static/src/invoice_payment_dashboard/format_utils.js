/** @odoo-module **/

import { formatMonetary } from "@web/views/fields/formatters";

export function formatMoney(value, currencyId, digits = 2) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const n = Number(value);
    if (Number.isNaN(n)) {
        return "—";
    }
    const rounded = Math.round(n * 10 ** digits) / 10 ** digits;
    return formatMonetary(rounded, { currencyId, digits });
}

const MONEY_COLUMNS = new Set([
    "amount_untaxed",
    "amount_tax",
    "amount_total",
    "amount_applied",
    "balance_pending",
    "credit_granted",
]);

export function isMoneyColumn(colId) {
    return MONEY_COLUMNS.has(colId);
}

export function formatCompact(value, currencySymbol = "") {
    const n = Number(value) || 0;
    if (Math.abs(n) >= 1_000_000) {
        return `${currencySymbol}${(n / 1_000_000).toFixed(1)}M`;
    }
    if (Math.abs(n) >= 1_000) {
        return `${currencySymbol}${(n / 1_000).toFixed(1)}K`;
    }
    return `${currencySymbol}${n.toFixed(0)}`;
}

export function formatPct(value, digits = 1) {
    if (value === null || value === undefined) {
        return "—";
    }
    return `${Number(value).toFixed(digits)}%`;
}

export const PRIMARY_KPI_KEYS = [
    "total_invoiced", "total_paid", "total_pending", "recovery_pct",
    "invoice_count", "payment_count", "avg_invoice", "avg_payment",
];

export const SECONDARY_KPI_KEYS = [
    "overdue_count", "overdue_balance", "avg_collection_days", "unique_clients",
];

const ES_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

export function formatDateDisplay(iso) {
    if (!iso) return "—";
    const [y, m, d] = iso.split("-");
    if (!y || !m || !d) return iso;
    return `${d}/${m}/${y}`;
}

export function formatPeriodChip(dateFrom, dateTo) {
    if (!dateFrom) return "";
    const [y, m] = dateFrom.split("-");
    const monthIdx = parseInt(m, 10) - 1;
    const monthName = ES_MONTHS[monthIdx] || m;
    if (dateTo && dateFrom.slice(0, 7) === dateTo.slice(0, 7)) {
        return `${monthName.charAt(0).toUpperCase()}${monthName.slice(1)} ${y}`;
    }
    return `${formatDateDisplay(dateFrom)} — ${formatDateDisplay(dateTo)}`;
}

export function formatDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso.replace(" ", "T") + "Z");
    const pad = (n) => String(n).padStart(2, "0");
    const hours = d.getHours();
    const h12 = hours % 12 || 12;
    const ampm = hours >= 12 ? "p. m." : "a. m.";
    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} · ${h12}:${pad(d.getMinutes())} ${ampm}`;
}

export function statusBadgeClass(state) {
    const map = {
        paid: "text-bg-success",
        partial: "text-bg-warning",
        not_paid: "text-bg-secondary",
        in_payment: "text-bg-info",
        reversed: "text-bg-dark",
    };
    return map[state] || "text-bg-light text-dark";
}

export function overdueClass(days) {
    if (!days || days <= 0) return "";
    if (days <= 30) return "o_inv_pay_overdue-mild";
    if (days <= 60) return "o_inv_pay_overdue-warn";
    if (days <= 90) return "o_inv_pay_overdue-high";
    return "o_inv_pay_overdue-critical";
}

export function defaultFilters() {
    const pad = (n) => String(n).padStart(2, "0");
    const d = new Date();
    const today = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const first = new Date(d.getFullYear(), d.getMonth(), 1);
    const monthStart = `${first.getFullYear()}-${pad(first.getMonth() + 1)}-01`;
    return {
        company_id: false,
        payment_period: "this_month",
        date_from: monthStart,
        date_to: today,
        invoice_date_from: "",
        invoice_date_to: "",
        branch_ids: [],
        user_ids: [],
        partner_ids: [],
        journal_ids: [],
        categ_ids: [],
        payment_state: "all",
        credit_term_filter: "all",
        show_pending_invoices: true,
        overdue_only: false,
        compare_mode: "previous",
        view_mode: "by_payment",
        search: "",
        amount_min: "",
        amount_max: "",
    };
}

export const DEFAULT_COLUMNS = [
    "customer", "invoice_number", "invoice_date", "due_date",
    "payment_receipt", "payment_date", "advisor", "bank",
    "amount_total", "amount_applied", "balance_pending",
    "invoice_status", "days_overdue",
];

export const COLUMN_TOOLTIPS = {
    days_invoice_to_payment: "Días transcurridos entre la fecha de emisión de la factura y la fecha del pago registrado.",
};

export const DATE_COLUMNS = new Set([
    "invoice_date", "payment_date", "due_date",
]);

export const CENTER_COLUMNS = new Set([
    "invoice_date", "payment_date", "due_date", "days_invoice_to_payment", "days_overdue",
]);

export const STICKY_COLUMNS = new Set(["customer", "invoice_number"]);

export const ALL_COLUMNS = [
    { id: "customer", label: "Cliente" },
    { id: "invoice_number", label: "Número de factura" },
    { id: "invoice_date", label: "Fecha de factura" },
    { id: "due_date", label: "Fecha de vencimiento" },
    { id: "payment_receipt", label: "Número de recibo" },
    { id: "payment_date", label: "Fecha de pago" },
    { id: "days_invoice_to_payment", label: "Días factura → pago" },
    { id: "days_overdue", label: "Días de atraso" },
    { id: "advisor", label: "Asesor" },
    { id: "bank", label: "Banco / diario" },
    { id: "branch", label: "Sucursal" },
    { id: "amount_untaxed", label: "Subtotal" },
    { id: "amount_tax", label: "Impuesto" },
    { id: "amount_total", label: "Total factura" },
    { id: "amount_applied", label: "Monto pagado" },
    { id: "balance_pending", label: "Saldo pendiente" },
    { id: "invoice_status", label: "Estado de factura" },
    { id: "payment_state", label: "Estado de pago" },
    { id: "credit_term_days", label: "Plazo de crédito" },
    { id: "within_credit", label: "Dentro del plazo" },
    { id: "collection_priority", label: "Prioridad de cobro" },
    { id: "payment_method", label: "Método de pago" },
    { id: "currency_symbol", label: "Moneda" },
    { id: "bank_reference", label: "Referencia bancaria" },
    { id: "payment_user", label: "Usuario de pago" },
    { id: "credit_granted", label: "Crédito otorgado" },
    { id: "customer_rank", label: "Ranking cliente" },
    { id: "product_categories", label: "Categorías" },
];

export const TABS = [
    { id: "summary", label: "Resumen", icon: "fa-chart-pie" },
    { id: "analysis", label: "Análisis", icon: "fa-chart-bar" },
    { id: "detail", label: "Detalle", icon: "fa-table" },
    { id: "overdue", label: "Vencimientos", icon: "fa-clock" },
];
