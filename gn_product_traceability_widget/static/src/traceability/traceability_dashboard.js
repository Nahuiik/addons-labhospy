/** @odoo-module **/
/* gn_product_traceability_widget dashboard client action */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService, useOwnedDialogs } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { user } from "@web/core/user";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { TraceabilityFlowMap } from "./flow_map";
import { highlightParts, fieldIsHighlighted } from "./highlight_utils";

const SERVICE = "product.traceability.service";

function emptyPayload() {
    return {
        needs_product: true,
        product: null,
        events: [],
        pending_moves: [],
        kpis: [],
        current_locations: [],
        flow_graph: { nodes: [], edges: [], branches: [] },
        pagination: { page: 1, page_size: 50, total: 0, has_more: false },
    };
}

function defaultFilterOptions() {
    return {
        warehouses: [],
        locations: [],
        lots: [],
        products: [],
        movement_types: [],
        states: [],
        page_size_options: [50, 100],
    };
}

function defaultFilters(params = {}) {
    return {
        product_id: params.product_id || false,
        product_tmpl_id: params.product_tmpl_id || false,
        lot_id: params.lot_id || false,
        company_id: user.activeCompany?.id || false,
        warehouse_id: false,
        location_id: false,
        operation_type_id: false,
        movement_type: false,
        state: "done",
        date_from: false,
        date_to: false,
        search: "",
        document: params.document || "",
        include_internal: true,
        include_adjustments: true,
        include_cancelled: false,
        include_pending: false,
        order: "asc",
        view: "timeline",
    };
}

export class ProductTraceabilityDashboard extends Component {
    static template = "gn_product_traceability_widget.ProductTraceabilityDashboard";
    static components = { Layout, TraceabilityFlowMap };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.addDialog = useOwnedDialogs();
        this.scrollRoot = useRef("scrollRoot");

        const params = this.props.action?.params || {};
        this.state = useState({
            loading: true,
            refreshing: false,
            error: null,
            payload: null,
            filterOptions: null,
            filters: defaultFilters(params),
            page: 1,
            pageSize: 50,
            viewMode: params.view || "timeline",
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await this.refresh({ silent: true });
        });
    }

    get display() {
        return { controlPanel: {} };
    }

    get rootClassName() {
        return "gn-traceability-root";
    }

    get payload() {
        return this.state.payload;
    }

    get product() {
        return this.payload?.product;
    }

    get needsProduct() {
        return Boolean(this.payload?.needs_product);
    }

    get hasProduct() {
        return Boolean(this.product);
    }

    get searchTerm() {
        return this.state.filters.search || "";
    }

    get isEmpty() {
        if (!this.payload) {
            return false;
        }
        return !(this.payload.events?.length) && !(this.payload.pending_moves?.length);
    }

    get events() {
        return this.payload?.events || [];
    }

    get flowGraph() {
        return this.payload?.flow_graph || { nodes: [], edges: [], branches: [] };
    }

    get hasPayload() {
        return this.hasProduct;
    }

    get showEvents() {
        return this.hasProduct && !this.isEmpty;
    }

    get showCosts() {
        return Boolean(this.payload?.meta?.can_show_costs);
    }

    kpiDisplayValue(kpi) {
        if (kpi.value_fmt) {
            return kpi.value_fmt;
        }
        const suffix = kpi.uom ? ` ${kpi.uom}` : "";
        return `${kpi.value}${suffix}`;
    }

    async loadFilterOptions() {
        const ctx = {
            product_id: this.state.filters.product_id,
            product_tmpl_id: this.state.filters.product_tmpl_id,
            lot_id: this.state.filters.lot_id,
        };
        try {
            this.state.filterOptions = await this.orm.call(SERVICE, "get_filter_options", [ctx]);
        } catch (err) {
            this.state.filterOptions = defaultFilterOptions();
            this.notification.add(err.message || _t("No se pudieron cargar los filtros."), { type: "warning" });
        }
    }

    async refresh({ silent = false } = {}) {
        if (!silent) {
            this.state.refreshing = true;
        } else {
            this.state.loading = true;
        }
        this.state.error = null;
        try {
            const filters = { ...this.state.filters, view: this.state.viewMode };
            const data = await this.orm.call(SERVICE, "get_product_traceability", [], {
                filters,
                page: this.state.page,
                page_size: this.state.pageSize,
                order: filters.order,
            });
            this.state.payload = data;
        } catch (err) {
            this.state.error = err.message || _t("Error al cargar la trazabilidad.");
            this.state.payload = this.state.payload?.product ? this.state.payload : emptyPayload();
        } finally {
            this.state.loading = false;
            this.state.refreshing = false;
        }
    }

    async onApplyFilters() {
        this.state.page = 1;
        await this.refresh();
    }

    async onClearFilters() {
        const keep = {
            product_id: this.state.filters.product_id,
            product_tmpl_id: this.state.filters.product_tmpl_id,
            lot_id: this.state.filters.lot_id,
        };
        this.state.filters = defaultFilters(keep);
        this.state.page = 1;
        await this.refresh();
    }

    async onLoadMore() {
        this.state.page += 1;
        this.state.refreshing = true;
        try {
            const filters = { ...this.state.filters, view: this.state.viewMode };
            const data = await this.orm.call(SERVICE, "get_product_traceability", [], {
                filters,
                page: this.state.page,
                page_size: this.state.pageSize,
                order: filters.order,
            });
            if (this.state.payload && data.events?.length) {
                this.state.payload.events = [...this.state.payload.events, ...data.events];
                this.state.payload.pagination = data.pagination;
                this.state.payload.flow_graph = data.flow_graph;
            }
        } catch (err) {
            this.notification.add(err.message, { type: "danger" });
        } finally {
            this.state.refreshing = false;
        }
    }

    setViewMode(mode) {
        if (!mode || this.state.viewMode === mode) {
            return;
        }
        this.state.viewMode = mode;
        this.state.filters = { ...this.state.filters, view: mode };
        requestAnimationFrame(() => {
            const panel = document.getElementById("gn_traceability_view_panel");
            const scroller = this.scrollRoot.el;
            if (!panel || !scroller) {
                return;
            }
            const panelTop = panel.getBoundingClientRect().top;
            const scrollerTop = scroller.getBoundingClientRect().top;
            scroller.scrollTo({
                top: scroller.scrollTop + panelTop - scrollerTop - 8,
                behavior: "smooth",
            });
        });
    }

    onFilterChange(field, ev) {
        const el = ev.target;
        if (el.type === "checkbox") {
            this.state.filters[field] = el.checked;
        } else if (el.type === "number") {
            this.state.filters[field] = el.value ? parseInt(el.value, 10) : false;
        } else {
            this.state.filters[field] = el.value || false;
        }
    }

    async openRecord(model, resId) {
        if (!model || !resId) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onFlowNodeClick(node) {
        if (node.kind === "event") {
            const moveId = parseInt(node.id.replace("ev-", ""), 10);
            const event = this.payload?.events?.find((e) => e.id === moveId);
            if (event?.picking_id) {
                this.openRecord("stock.picking", event.picking_id);
            }
            return;
        }
        if (node.kind === "location") {
            const locId = parseInt(node.id.replace("loc-", ""), 10);
            this.openRecord("stock.location", locId);
        }
    }

    async applyProductSelection(productId) {
        if (!productId) {
            return;
        }
        const [product] = await this.orm.read("product.product", [productId], ["product_tmpl_id"]);
        this.state.filters.product_id = productId;
        const tmpl = product?.product_tmpl_id;
        this.state.filters.product_tmpl_id = Array.isArray(tmpl) ? tmpl[0] : tmpl || false;
        this.state.filters.lot_id = false;
        this.state.page = 1;
        await this.loadFilterOptions();
        await this.refresh();
    }

    async onSelectProduct(ev) {
        const productId = parseInt(ev.target.value, 10);
        if (!productId) {
            return;
        }
        await this.applyProductSelection(productId);
    }

    async onSearchProduct(ev) {
        const term = ev.target.value || "";
        if (term.length < 2) {
            return;
        }
        const products = await this.orm.call(SERVICE, "search_products", [term, 20]);
        if (this.state.filterOptions) {
            this.state.filterOptions.products = products;
        }
    }

    openProductList() {
        this.addDialog(SelectCreateDialog, {
            title: _t("Seleccionar producto"),
            resModel: "product.product",
            domain: [["is_storable", "=", true]],
            multiSelect: false,
            noCreate: true,
            onSelected: (resIds) => this.applyProductSelection(resIds[0]),
        });
    }

    async openStockMoves() {
        const domain = [["product_id", "=", this.state.filters.product_id]];
        if (this.state.filters.lot_id) {
            domain.push(["lot_id", "=", this.state.filters.lot_id]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Stock Moves"),
            res_model: "stock.move.line",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    async exportPdf() {
        const productId = this.state.filters.product_id;
        await this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "gn_product_traceability_widget.traceability_pdf",
            data: { filters: this.state.filters },
        }, { additionalContext: { active_ids: productId ? [productId] : [] } });
    }

    async exportExcel() {
        const productId = this.state.filters.product_id;
        await this.action.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: "gn_traceability.traceability_xlsx",
            data: { filters: this.state.filters },
        }, { additionalContext: { active_ids: productId ? [productId] : [] } });
    }

    toggleOrder() {
        this.state.filters.order = this.state.filters.order === "asc" ? "desc" : "asc";
        this.onApplyFilters();
    }

    kpiClass(tone) {
        return `gn_traceability_kpi gn_traceability_kpi--${tone || "neutral"}`;
    }

    eventClass(event) {
        let cls = `gn_traceability_event gn_traceability_event--${event.tone}`;
        if (event.highlight) {
            cls += " gn_traceability_event--highlight";
        }
        return cls;
    }

    hlParts(text) {
        return highlightParts(text, this.searchTerm);
    }

    fieldHighlighted(event, fieldName) {
        return fieldIsHighlighted(event, fieldName);
    }

    cellClass(event, fieldName) {
        return this.fieldHighlighted(event, fieldName) ? "gn_traceability_highlight-cell" : "";
    }
}

registry.category("actions").add("gn_product_traceability_dashboard", ProductTraceabilityDashboard);
