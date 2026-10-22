/** @odoo-module **/

/**
 * Motor del Gantt de ausencias: escalas (día / semana / mes / trimestre) y ventana visible.
 */

const { DateTime } = luxon;

export const CAL_SCALE = {
    DAY: "day",
    WEEK: "week",
    MONTH: "month",
    QUARTER: "quarter",
};

export const SLOT_MODE = {
    HALF: "half",
    HOUR: "hour",
};

/**
 * @param {string} calScale key CAL_SCALE.*
 * @param {import("luxon").DateTime} pivot
 */
export function resolveVisibleWindow(calScale, pivot) {
    const p = pivot.startOf("day");
    switch (calScale) {
        case CAL_SCALE.DAY:
            return { start: p, end: p };
        case CAL_SCALE.WEEK: {
            const start = p.startOf("week");
            return { start, end: start.plus({ days: 6 }) };
        }
        case CAL_SCALE.MONTH:
            return { start: p.startOf("month"), end: p.endOf("month") };
        case CAL_SCALE.QUARTER:
        default: {
            const start = p.startOf("month");
            return { start, end: start.plus({ months: 2 }).endOf("month") };
        }
    }
}

/**
 * @param {string} calScale
 * @param {import("luxon").DateTime} pivot
 * @param {number} direction +1 / -1
 */
export function advancePivot(calScale, pivot, direction) {
    const p = pivot.startOf("day");
    switch (calScale) {
        case CAL_SCALE.DAY:
            return p.plus({ days: direction });
        case CAL_SCALE.WEEK:
            return p.plus({ weeks: direction });
        case CAL_SCALE.MONTH:
            return p.plus({ months: direction });
        case CAL_SCALE.QUARTER:
        default:
            return p.plus({ months: direction });
    }
}

export function describeWindow(start, end) {
    return `${start.toFormat("dd/MM/yyyy")} -> ${end.toFormat("dd/MM/yyyy")}`;
}

/** Altura de fila de empleado para virtualización vertical (px). */
export const VIRTUAL_ROW_PX = 48;

/** Columna mínima aproximada según ranura (px). */
export function columnHintPx(slotMode, calScale) {
    if (slotMode === SLOT_MODE.HOUR) {
        return calScale === CAL_SCALE.DAY ? 10 : 8;
    }
    if (calScale === CAL_SCALE.DAY) {
        return 48;
    }
    if (calScale === CAL_SCALE.WEEK) {
        return 18;
    }
    return 14;
}
