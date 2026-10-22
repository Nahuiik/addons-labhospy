/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
import { StockReportSearchPanel } from "@stock/views/search/stock_report_search_panel";

function normalizeWarehouseIds(value) {
    if (!value) {
        return [];
    }
    if (Array.isArray(value)) {
        return value.map((id) => Number(id)).filter((id) => id);
    }
    const id = Number(value);
    return id ? [id] : [];
}

patch(StockReportSearchModel.prototype, {
    /**
     * @returns {{id: number, name: string}[]}
     */
    getBranches() {
        const byId = new Map();
        for (const wh of this.warehouses || []) {
            const branch = wh.branch_id;
            if (!branch) {
                continue;
            }
            const branchId = Array.isArray(branch) ? branch[0] : branch;
            const branchName = Array.isArray(branch) ? branch[1] : String(branch);
            if (branchId && !byId.has(branchId)) {
                byId.set(branchId, { id: branchId, name: branchName });
            }
        }
        return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
    },

    getSelectedWarehouseIds() {
        return normalizeWarehouseIds(this.globalContext.warehouse_id);
    },

    clearWarehouseContext() {
        delete this.globalContext.warehouse_id;
        this._notify();
    },

    /**
     * Toggle de almacén (multi-selección). Clic otra vez lo quita.
     * @param {number} warehouse_id
     */
    applyWarehouseContext(warehouse_id) {
        const selected = this.getSelectedWarehouseIds();
        const id = Number(warehouse_id);
        const idx = selected.indexOf(id);
        if (idx >= 0) {
            selected.splice(idx, 1);
        } else {
            selected.push(id);
        }
        if (!selected.length) {
            delete this.globalContext.warehouse_id;
        } else {
            this.globalContext.warehouse_id = selected.length === 1 ? selected[0] : selected;
        }
        this._notify();
    },

    /**
     * Selecciona todos los almacenes de la sucursal.
     * @param {number} branch_id
     */
    applyBranchContext(branch_id) {
        const ids = (this.warehouses || [])
            .filter((wh) => {
                const branch = wh.branch_id;
                if (!branch) {
                    return false;
                }
                const bid = Array.isArray(branch) ? branch[0] : branch;
                return bid === branch_id;
            })
            .map((wh) => wh.id);
        if (!ids.length) {
            delete this.globalContext.warehouse_id;
        } else {
            this.globalContext.warehouse_id = ids.length === 1 ? ids[0] : ids;
        }
        this._notify();
    },
});

patch(StockReportSearchPanel.prototype, {
    setup() {
        super.setup(...arguments);
        // Compat: el core usa selectedWarehouse; mantenemos sync con lista
        this.selectedWarehouse = false;
    },

    get branches() {
        return this.env.searchModel.getBranches();
    },

    get selectedWarehouseIds() {
        return this.env.searchModel.getSelectedWarehouseIds();
    },

    get selectedBranchId() {
        const selected = this.selectedWarehouseIds;
        if (!selected.length) {
            return false;
        }
        const branches = this.branches;
        for (const branch of branches) {
            const whIds = (this.warehouses || [])
                .filter((wh) => {
                    const b = wh.branch_id;
                    const bid = Array.isArray(b) ? b[0] : b;
                    return bid === branch.id;
                })
                .map((wh) => wh.id)
                .sort((a, b) => a - b);
            const sorted = [...selected].sort((a, b) => a - b);
            if (
                whIds.length &&
                whIds.length === sorted.length &&
                whIds.every((id, i) => id === sorted[i])
            ) {
                return branch.id;
            }
        }
        return false;
    },

    isWarehouseSelected(warehouseId) {
        return this.selectedWarehouseIds.includes(warehouseId);
    },

    clearWarehouseContext() {
        this.env.searchModel.clearWarehouseContext();
        this.selectedWarehouse = null;
    },

    applyWarehouseContext(warehouse_id) {
        this.env.searchModel.applyWarehouseContext(warehouse_id);
        const selected = this.env.searchModel.getSelectedWarehouseIds();
        this.selectedWarehouse = selected.length === 1 ? selected[0] : selected.length ? true : null;
    },

    applyBranchContext(branch_id) {
        this.env.searchModel.applyBranchContext(branch_id);
        const selected = this.env.searchModel.getSelectedWarehouseIds();
        this.selectedWarehouse = selected.length === 1 ? selected[0] : selected.length ? true : null;
    },
});
