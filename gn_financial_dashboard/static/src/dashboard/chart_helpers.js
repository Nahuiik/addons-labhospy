/** @odoo-module **/

import { loadBundle } from "@web/core/assets";

export const PALETTE = {
    income: "rgba(25, 135, 84, 0.85)",
    incomeBorder: "rgba(25, 135, 84, 1)",
    expense: "rgba(220, 53, 69, 0.85)",
    expenseBorder: "rgba(220, 53, 69, 1)",
    net: "rgba(13, 110, 253, 1)",
    total: "rgba(91, 44, 111, 0.85)",
    subtotal: "rgba(13, 110, 253, 0.8)",
    down: "rgba(220, 53, 69, 0.8)",
    grid: "rgba(148, 163, 184, 0.18)",
    donut: [
        "#5b2c6f", "#2980b9", "#16a085", "#f39c12", "#c0392b",
        "#7f8c8d", "#8e44ad", "#27ae60", "#d35400", "#2c3e50",
    ],
};

export async function loadChartJs() {
    if (typeof Chart !== "undefined") {
        return;
    }
    if (!loadChartJs._promise) {
        loadChartJs._promise = loadBundle("web.chartjs_lib");
    }
    await loadChartJs._promise;
}

export function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
    return null;
}

// Locale fijo en-US para mantener el separador de miles como coma (,)
// y el separador decimal como punto (.) en todo el tablero, independiente
// del idioma del usuario. Esto unifica la lectura y evita confusión.
const LOCALE = "en-US";

/**
 * Formatea un número con coma como separador de miles y punto como
 * separador decimal.
 *
 * @param {number} value
 * @param {number} [decimals=2]
 * @returns {string}
 */
export function formatNumber(value, decimals = 2) {
    const n = Number(value ?? 0);
    return n.toLocaleString(LOCALE, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

export function formatMoney(value, symbol = "$", decimals = 2) {
    return `${symbol}${formatNumber(value, decimals)}`;
}

export function compactNumber(value) {
    const n = Number(value ?? 0);
    const abs = Math.abs(n);
    if (abs >= 1e9) {
        return (n / 1e9).toFixed(1) + "B";
    }
    if (abs >= 1e6) {
        return (n / 1e6).toFixed(1) + "M";
    }
    if (abs >= 1e3) {
        return (n / 1e3).toFixed(1) + "k";
    }
    return n.toFixed(0);
}

/**
 * Formatea una fecha o datetime al formato dd/mm/yyyy.
 * Acepta strings ISO ("2026-06-29" o "2026-06-29 10:23:45"), Date u
 * objetos Luxon DateTime. Devuelve cadena vacía si la entrada es
 * falsy o no parseable.
 */
export function formatDate(value) {
    if (!value) return "";
    if (typeof value === "string") {
        // Solo fecha (YYYY-MM-DD) — evita problemas de zona horaria.
        const m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (m) {
            return `${m[3]}/${m[2]}/${m[1]}`;
        }
    }
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = d.getFullYear();
    return `${dd}/${mm}/${yy}`;
}

/**
 * Formatea fecha+hora a dd/mm/yyyy HH:mm.
 */
export function formatDateTime(value) {
    if (!value) return "";
    let d;
    if (typeof value === "string") {
        // Convierte "2026-06-29 10:23:45" o ISO en Date.
        d = new Date(value.replace(" ", "T"));
    } else {
        d = value instanceof Date ? value : new Date(value);
    }
    if (Number.isNaN(d.getTime())) return String(value);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${yy} ${hh}:${mi}`;
}
