/** @odoo-module **/

const STORAGE_KEY = "gn_banks_dashboard.filters.v1";

/**
 * Persist dashboard filters in localStorage (date range, company, journals).
 * @param {object} filters
 */
export function saveStoredFilters(filters) {
    try {
        const payload = {
            date_from: filters.date_from,
            date_to: filters.date_to,
            company_id: filters.company_id,
            journal_ids: filters.journal_ids || [],
            flow_source: filters.flow_source || "treasury",
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
        // private mode / quota — ignore
    }
}

/**
 * @returns {object|null}
 */
export function loadStoredFilters() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return null;
        }
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

export function clearStoredFilters() {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {
        // ignore
    }
}
