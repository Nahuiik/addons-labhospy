/** @odoo-module **/

/**
 * Lightweight bus for synchronised week highlighting across charts and table.
 * Charts call setHighlightedWeek; table and other charts react via callback.
 */
export class ChartWeekSync {
    constructor() {
        this._weekKey = null;
        this._listeners = new Set();
    }

    get weekKey() {
        return this._weekKey;
    }

    subscribe(fn) {
        this._listeners.add(fn);
        return () => this._listeners.delete(fn);
    }

    setHighlightedWeek(weekKey) {
        this._weekKey = weekKey || null;
        for (const fn of this._listeners) {
            fn(this._weekKey);
        }
    }

    clear() {
        this.setHighlightedWeek(null);
    }
}
