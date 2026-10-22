/** @odoo-module **/

export function formatDashboardDate(value) {
    if (!value) return "";
    const d = typeof value === "string" ? value.slice(0, 10) : value;
    try {
        const dt = new Date(`${d}T12:00:00`);
        return dt.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    } catch {
        return d;
    }
}

export function formatDashboardDateTime(value) {
    if (!value) return "";
    try {
        const dt = new Date(value);
        return dt.toLocaleString(undefined, {
            year: "numeric", month: "short", day: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    } catch {
        return value;
    }
}

export function periodLabel(filters) {
    if (!filters?.date_from || !filters?.date_to) return "";
    return `${formatDashboardDate(filters.date_from)} – ${formatDashboardDate(filters.date_to)}`;
}
