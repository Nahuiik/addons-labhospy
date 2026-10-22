/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Component, onWillStart, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const MODEL = "gn.inventory.adjustment";

export class GnInventoryAdjustment extends Component {
    static template = "gn_inventory_ajustment.InventoryAdjustment";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            loadingOptions: true,
            loading: false,
            applying: false,
            searched: false,
            error: null,
            options: { warehouses: [], locations: [], suppliers: [] },
            filters: {
                warehouse_id: 0,
                location_id: 0,
                supplier_id: 0,
                model_filter: "",
                code_filter: "",
                show_qty: true,
            },
            lines: [],
            // line_key -> valor capturado (string para permitir vacío)
            counted: {},
            addProduct: {
                open: false,
                term: "",
                results: [],
                productId: 0,
                locationId: 0,
                lotName: "",
                searching: false,
            },
        });
        this._productSearchTimer = null;

        onWillStart(async () => {
            try {
                this.state.options = await this.orm.call(MODEL, "get_filter_options", []);
            } catch (e) {
                this.state.error = e.data?.message || e.message;
            }
            this.state.loadingOptions = false;
        });
    }

    // ── Filtros ──

    getFilteredLocations() {
        const whId = this.state.filters.warehouse_id;
        if (!whId) {
            return this.state.options.locations;
        }
        return this.state.options.locations.filter((l) => l.warehouse_id === whId);
    }

    onWarehouseChange(ev) {
        const val = parseInt(ev.target.value, 10) || 0;
        this.state.filters.warehouse_id = val;
        const loc = this.state.options.locations.find(
            (l) => l.id === this.state.filters.location_id
        );
        if (val && loc && loc.warehouse_id !== val) {
            this.state.filters.location_id = 0;
        }
    }

    onLocationChange(ev) {
        this.state.filters.location_id = parseInt(ev.target.value, 10) || 0;
    }

    onSupplierChange(ev) {
        this.state.filters.supplier_id = parseInt(ev.target.value, 10) || 0;
    }

    onModelInput(ev) {
        this.state.filters.model_filter = ev.target.value;
    }

    onCodeInput(ev) {
        this.state.filters.code_filter = ev.target.value;
    }

    onShowQtyChange(ev) {
        this.state.filters.show_qty = ev.target.checked;
    }

    _filtersPayload() {
        const f = this.state.filters;
        return {
            warehouse_id: f.warehouse_id || false,
            location_id: f.location_id || false,
            supplier_id: f.supplier_id || false,
            model_filter: f.model_filter.trim() || false,
            code_filter: f.code_filter.trim() || false,
            show_qty: f.show_qty,
        };
    }

    // ── Búsqueda ──

    async onSearch() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.lines = await this.orm.call(MODEL, "get_lines", [this._filtersPayload()]);
            this.state.counted = {};
            this.state.searched = true;
        } catch (e) {
            this.state.error = e.data?.message || e.message;
        }
        this.state.loading = false;
    }

    // ── Captura de conteo ──

    onCountedInput(line, ev) {
        this.state.counted[line.line_key] = ev.target.value;
    }

    getCounted(line) {
        return this.state.counted[line.line_key] ?? "";
    }

    hasCounted(line) {
        const val = this.state.counted[line.line_key];
        return val !== undefined && val !== "" && !Number.isNaN(parseFloat(val));
    }

    getDiff(line) {
        if (!this.hasCounted(line)) {
            return null;
        }
        return parseFloat(this.state.counted[line.line_key]) - line.qty_on_hand;
    }

    getCountedLines() {
        return this.state.lines.filter((l) => this.hasCounted(l));
    }

    // ── Aplicar ajuste ──

    onApplyClick() {
        const countedLines = this.getCountedLines();
        if (!countedLines.length) {
            this.notification.add(
                _t("Capture al menos una cantidad contada para aplicar el ajuste."),
                { type: "warning" }
            );
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Aplicar ajuste de inventario"),
            body: _t(
                "Se aplicará el ajuste de inventario a %s línea(s) con cantidad contada. ¿Desea continuar?",
                countedLines.length
            ),
            confirmLabel: _t("Aplicar"),
            cancelLabel: _t("Cancelar"),
            confirm: () => this._applyAdjustment(countedLines),
            cancel: () => {},
        });
    }

    async _applyAdjustment(countedLines) {
        this.state.applying = true;
        try {
            const payload = countedLines.map((l) => ({
                quant_id: l.quant_id,
                product_id: l.product_id,
                location_id: l.location_id,
                lot_name: l.lot_name,
                counted_qty: parseFloat(this.state.counted[l.line_key]),
            }));
            const result = await this.orm.call(MODEL, "apply_adjustment", [payload]);
            if (result.conflict && result.action) {
                await this.actionService.doAction(result.action);
            } else {
                this.notification.add(
                    _t(
                        "Ajuste procesado en %s (%s línea(s)).",
                        result.inventory_name,
                        result.applied
                    ),
                    {
                        type: "success",
                        sticky: true,
                        buttons: result.action
                            ? [
                                  {
                                      name: _t("Ver evidencia"),
                                      primary: true,
                                      onClick: () => this.actionService.doAction(result.action),
                                  },
                              ]
                            : [],
                    }
                );
            }
            await this.onSearch();
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
        this.state.applying = false;
    }

    // ── Agregar producto sin existencia ──

    get selectedProduct() {
        return this.state.addProduct.results.find(
            (product) => product.id === this.state.addProduct.productId
        );
    }

    get needsLot() {
        const product = this.selectedProduct;
        return product && product.tracking !== "none";
    }

    openAddProduct() {
        const locations = this.getFilteredLocations();
        const current = this.state.filters.location_id;
        const locationId = locations.some((loc) => loc.id === current)
            ? current
            : locations[0]?.id || 0;
        this.state.addProduct.open = true;
        this.state.addProduct.term = "";
        this.state.addProduct.results = [];
        this.state.addProduct.productId = 0;
        this.state.addProduct.locationId = locationId;
        this.state.addProduct.lotName = "";
    }

    closeAddProduct() {
        this.state.addProduct.open = false;
    }

    onAddLocationChange(ev) {
        this.state.addProduct.locationId = parseInt(ev.target.value, 10) || 0;
    }

    onAddLotInput(ev) {
        this.state.addProduct.lotName = ev.target.value;
    }

    onProductSearchInput(ev) {
        const term = ev.target.value;
        this.state.addProduct.term = term;
        this.state.addProduct.productId = 0;
        clearTimeout(this._productSearchTimer);
        this._productSearchTimer = setTimeout(() => this._searchProducts(term), 250);
    }

    async _searchProducts(term) {
        this.state.addProduct.searching = true;
        try {
            this.state.addProduct.results = await this.orm.call(MODEL, "search_products", [term]);
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
        this.state.addProduct.searching = false;
    }

    selectProduct(product) {
        this.state.addProduct.productId = product.id;
        this.state.addProduct.term = product.name;
        if (product.tracking === "none") {
            this.state.addProduct.lotName = "";
        }
    }

    async confirmAddProduct() {
        const draft = this.state.addProduct;
        if (!draft.productId) {
            this.notification.add(_t("Seleccione un producto."), { type: "warning" });
            return;
        }
        if (!draft.locationId) {
            this.notification.add(_t("Seleccione una ubicación."), { type: "warning" });
            return;
        }
        try {
            const line = await this.orm.call(MODEL, "prepare_manual_line", [
                draft.productId,
                draft.locationId,
                draft.lotName,
            ]);
            if (this.state.lines.some((item) => item.line_key === line.line_key)) {
                this.notification.add(
                    _t("Ese producto ya está en el listado. Capture el conteo en esa línea."),
                    { type: "warning" }
                );
                this.closeAddProduct();
                return;
            }
            this.state.lines.push(line);
            this.state.searched = true;
            this.closeAddProduct();
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    // ── Impresión ──

    async printReport(fmt) {
        try {
            const action = await this.orm.call(MODEL, "print_report", [
                this._filtersPayload(),
                fmt,
            ]);
            if (action) {
                await this.actionService.doAction(action);
            }
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }

    // ── Helpers de formato ──

    fmt2(n) {
        if (n === undefined || n === null || Number.isNaN(n)) {
            return "0.00";
        }
        return Number(n).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

registry.category("actions").add("gn_inventory_ajustment.inventory_adjustment", GnInventoryAdjustment);
