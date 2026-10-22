/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const PAGE_SIZE = 80;
const MAX_DROPDOWN_ITEMS = 50;

export class GnStockKardexPreview extends Component {
    static template = "gn_stock_kardex.KardexPreview";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.searchInputRef = useRef("searchInput");
        
        this.state = useState({
            loading: true,
            data: null,
            error: null,
            // 'summary' = product list, 'detail' = single product kardex
            viewMode: "summary",
            activeIndex: 0,
            currentPage: 1,
            // Summary view state
            summarySearch: "",
            summaryPage: 1,
            selectedCategory: null,
            selectedLocationIds: [],
            locations: [],
            onlyNegative: false,
            groupBy: "none", // "none" | "category"
            collapsedGroups: {},
            // Summary sorting
            sortField: null,
            sortDir: "asc",
            // Detail product search
            searchTerm: "",
            dropdownOpen: false,
        });
        this.params = this._readParams();

        onWillStart(async () => {
            this.state.selectedLocationIds = [...(this.params.location_ids || [])];
            await this._loadLocations();
            await this.loadData();
        });

        onMounted(() => {
            this._onClickOutside = (ev) => {
                if (this.state.dropdownOpen) {
                    const el = this.searchInputRef.el;
                    if (el && !el.closest(".o_kx_search_wrap")?.contains(ev.target)) {
                        this.state.dropdownOpen = false;
                    }
                }
                
            };
            document.addEventListener("click", this._onClickOutside, true);
        });
    }

    destroy() {
        if (this._onClickOutside) {
            document.removeEventListener("click", this._onClickOutside, true);
        }
        super.destroy?.();
    }

    _readParams() {
        const ctx = this.props.action.context || {};
        return {
            company_id: ctx.kardex_company_id,
            branch_id: ctx.kardex_branch_id || false,
            branch_name: ctx.kardex_branch_name || '',
            warehouse_id: ctx.kardex_warehouse_id || false,
            warehouse_name: ctx.kardex_warehouse_name || '',
            location_ids: (() => {
                const ids = ctx.kardex_location_ids;
                if (ids && ids.length) {
                    return [...ids];
                }
                if (ctx.kardex_location_id) {
                    return [ctx.kardex_location_id];
                }
                return [];
            })(),
            product_ids: ctx.kardex_product_ids || [],
            date_from: ctx.kardex_date_from,
            date_to: ctx.kardex_date_to,
            initialView: ctx.kardex_view_mode || 'summary',
        };
    }

    // ── Summary view ──

    getCategories() {
        const sections = this.state.data?.sections || [];
        const withMovement = sections.filter((s) => s.lines.length > 1);
        const counts = {};
        for (const s of withMovement) {
            const cat = s.categ_name || "Sin categoría";
            counts[cat] = (counts[cat] || 0) + 1;
        }
        return Object.entries(counts)
            .map(([name, count]) => ({ name, count }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }

    onCategoryClick(catName) {
        if (this.state.selectedCategory === catName) {
            this.state.selectedCategory = null;
        } else {
            this.state.selectedCategory = catName;
        }
        this.state.summaryPage = 1;
    }

    async _loadLocations() {
        const companyId = this.params.company_id;
        if (!companyId) return;
        const domain = [['usage', 'in', ['internal', 'transit']], ['company_id', '=', companyId]];
        if (this.params.warehouse_id) {
            domain.push(['warehouse_id', '=', this.params.warehouse_id]);
        }
        const locs = await this.orm.searchRead(
            "stock.location", domain, ["id", "complete_name", "usage"],
            { order: "usage, complete_name", limit: 200 }
        );
        this.state.locations = locs.map(l => ({
            ...l,
            is_transit: l.usage === 'transit',
        }));
    }

    getLocationsToAdd() {
        return this.state.locations.filter((l) => !this.state.selectedLocationIds.includes(l.id));
    }

    getLocationById(locId) {
        return this.state.locations.find((l) => l.id === locId);
    }

    getSelectedLocationTags() {
        return this.state.selectedLocationIds.map((id) => {
            const loc = this.getLocationById(id);
            const name = loc ? loc.complete_name : "";
            return {
                id,
                short: this.truncateLoc(name),
                title: name,
                is_transit: loc ? loc.is_transit : false,
            };
        });
    }

    truncateLoc(name, maxLen = 28) {
        if (!name) return "";
        return name.length > maxLen ? `${name.slice(0, maxLen)}…` : name;
    }

    async onAddLocationSelect(ev) {
        const val = parseInt(ev.target.value, 10) || 0;
        ev.target.value = "";
        if (!val || this.state.selectedLocationIds.includes(val)) {
            return;
        }
        this.state.selectedLocationIds = [...this.state.selectedLocationIds, val];
        this.params.location_ids = [...this.state.selectedLocationIds];
        this.state.summaryPage = 1;
        this.state.currentPage = 1;
        await this.loadData();
    }

    async onRemoveLocationTag(locId) {
        this.state.selectedLocationIds = this.state.selectedLocationIds.filter((id) => id !== locId);
        this.params.location_ids = [...this.state.selectedLocationIds];
        this.state.summaryPage = 1;
        this.state.currentPage = 1;
        await this.loadData();
    }

    onNegativeFilterChange(ev) {
        this.state.onlyNegative = ev.target.checked;
        this.state.summaryPage = 1;
    }

    getSummaryFilteredSections() {
        const sections = this.state.data?.sections || [];
        let filtered = sections.filter((s) => s.lines.length > 1);
        if (this.state.selectedCategory) {
            filtered = filtered.filter((s) =>
                (s.categ_name || "Sin categoría") === this.state.selectedCategory
            );
        }
        const term = this.state.summarySearch.toLowerCase().trim();
        if (term) {
            filtered = filtered.filter((s) => s.product_name.toLowerCase().includes(term));
        }
        if (this.state.onlyNegative) {
            filtered = filtered.filter((s) => s.totals.final_qty < 0);
        }
        if (this.state.sortField) {
            const dir = this.state.sortDir === "asc" ? 1 : -1;
            const field = this.state.sortField;
            filtered = [...filtered].sort((a, b) => {
                let va, vb;
                if (field === "product_name") {
                    va = a.product_name || "";
                    vb = b.product_name || "";
                    return dir * va.localeCompare(vb);
                }
                const fieldMap = {
                    prev_qty: (s) => s.prev_balance.qty,
                    in_qty: (s) => s.totals.in_qty,
                    out_qty: (s) => s.totals.out_qty,
                    final_qty: (s) => s.totals.final_qty,
                    final_unit_cost: (s) => s.totals.final_unit_cost,
                    final_total: (s) => s.totals.final_total,
                };
                const getter = fieldMap[field];
                if (!getter) return 0;
                va = getter(a) || 0;
                vb = getter(b) || 0;
                return dir * (va - vb);
            });
        }
        return filtered;
    }

    getSummaryTotalPages() {
        return Math.max(1, Math.ceil(this.getSummaryFilteredSections().length / PAGE_SIZE));
    }

    getSummaryPageFrom() {
        const total = this.getSummaryFilteredSections().length;
        if (!total) return 0;
        return (this.state.summaryPage - 1) * PAGE_SIZE + 1;
    }

    getSummaryPageTo() {
        return Math.min(this.state.summaryPage * PAGE_SIZE, this.getSummaryFilteredSections().length);
    }

    getSummaryVisibleSections() {
        const all = this.getSummaryFilteredSections();
        const start = (this.state.summaryPage - 1) * PAGE_SIZE;
        return all.slice(start, start + PAGE_SIZE);
    }

    // Grouped view: returns [{categ, count, sections, totals}]
    getGroupedByCategory() {
        const filtered = this.getSummaryFilteredSections();
        const groups = {};
        for (const s of filtered) {
            const cat = s.categ_name || "Sin categoría";
            if (!groups[cat]) {
                groups[cat] = { categ: cat, sections: [], totals: { opening: 0, incoming: 0, outgoing: 0, closing_qty: 0, closing_total: 0 } };
            }
            groups[cat].sections.push(s);
            groups[cat].totals.opening += s.prev_balance.qty;
            groups[cat].totals.incoming += s.totals.in_qty;
            groups[cat].totals.outgoing += s.totals.out_qty;
            groups[cat].totals.closing_qty += s.totals.final_qty;
            groups[cat].totals.closing_total += s.totals.final_total;
        }
        return Object.values(groups).sort((a, b) => a.categ.localeCompare(b.categ));
    }

    isGroupCollapsed(categ) {
        return !!this.state.collapsedGroups[categ];
    }

    toggleGroup(categ) {
        if (this.state.collapsedGroups[categ]) {
            delete this.state.collapsedGroups[categ];
        } else {
            this.state.collapsedGroups[categ] = true;
        }
        // Force reactivity
        this.state.collapsedGroups = { ...this.state.collapsedGroups };
    }

    onGroupByChange(ev) {
        this.state.groupBy = ev.target.value;
        this.state.summaryPage = 1;
        this.state.collapsedGroups = {};
    }

    onSummarySearchInput(ev) {
        this.state.summarySearch = ev.target.value;
        this.state.summaryPage = 1;
    }

    onSortColumn(field) {
        if (this.state.sortField === field) {
            this.state.sortDir = this.state.sortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = field;
            this.state.sortDir = "asc";
        }
        this.state.summaryPage = 1;
    }

    getSortIcon(field) {
        if (this.state.sortField !== field) return "fa fa-sort text-muted";
        return this.state.sortDir === "asc" ? "fa fa-sort-asc" : "fa fa-sort-desc";
    }

    negClass(val) {
        return val < 0 ? " text-danger" : "";
    }

    summaryPrevPage() {
        if (this.state.summaryPage > 1) this.state.summaryPage--;
    }

    summaryNextPage() {
        if (this.state.summaryPage < this.getSummaryTotalPages()) this.state.summaryPage++;
    }

    openDetail(sec) {
        const sections = this.state.data?.sections || [];
        const idx = sections.indexOf(sec);
        if (idx >= 0) {
            this.state.activeIndex = idx;
            this.state.currentPage = 1;
            this.state.viewMode = "detail";
        }
    }

    backToSummary() {
        this.state.viewMode = "summary";
        this.state.dropdownOpen = false;
        this.state.searchTerm = "";
    }

    // ── Detail view ──

    getSection() {
        const sections = this.state.data?.sections || [];
        return sections[this.state.activeIndex] || null;
    }

    getAllLines() {
        const sec = this.getSection();
        return sec ? sec.lines : [];
    }

    getTotalLines() { return this.getAllLines().length; }

    getTotalPages() {
        return Math.max(1, Math.ceil(this.getTotalLines() / PAGE_SIZE));
    }

    getPageFrom() {
        if (!this.getTotalLines()) return 0;
        return (this.state.currentPage - 1) * PAGE_SIZE + 1;
    }

    getPageTo() {
        return Math.min(this.state.currentPage * PAGE_SIZE, this.getTotalLines());
    }

    getVisibleLines() {
        const all = this.getAllLines();
        const start = (this.state.currentPage - 1) * PAGE_SIZE;
        return all.slice(start, start + PAGE_SIZE);
    }

    prevPage() { if (this.state.currentPage > 1) this.state.currentPage--; }
    nextPage() { if (this.state.currentPage < this.getTotalPages()) this.state.currentPage++; }

    // ── Product search (detail view) ──

    getFilteredSections() {
        const sections = this.state.data?.sections || [];
        const term = this.state.searchTerm.toLowerCase().trim();
        if (!term) return sections.slice(0, MAX_DROPDOWN_ITEMS);
        return sections.filter((s) => s.product_name.toLowerCase().includes(term)).slice(0, MAX_DROPDOWN_ITEMS);
    }

    getActiveProductName() {
        const sec = this.getSection();
        return sec ? sec.product_name : "";
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        this.state.dropdownOpen = true;
    }

    onSearchFocus() {
        this.state.dropdownOpen = true;
        this.state.searchTerm = "";
    }

    onSearchKeydown(ev) {
        if (ev.key === "Escape") {
            this.state.dropdownOpen = false;
            ev.target.blur();
        } else if (ev.key === "Enter") {
            const items = this.getFilteredSections();
            if (items.length === 1) this.selectProduct(items[0]);
        }
    }

    selectProduct(sec) {
        const sections = this.state.data?.sections || [];
        const idx = sections.indexOf(sec);
        if (idx >= 0) {
            this.state.activeIndex = idx;
            this.state.currentPage = 1;
        }
        this.state.dropdownOpen = false;
        this.state.searchTerm = "";
    }

    // ── Date change (inline) ──

    async onDateChange(field, ev) {
        const val = ev.target.value;
        if (!val) return;
        this.params[field] = val;
        this.state.summaryPage = 1;
        this.state.currentPage = 1;
        await this.loadData();
    }

    // ── Data loading ──

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        const p = this.params;
        if (!p.company_id || !p.product_ids?.length) {
            this.state.error = _t("Faltan datos: use el asistente y presione «Vista Kardex».");
            this.state.loading = false;
            return;
        }
        try {
            const locIds = p.location_ids && p.location_ids.length ? p.location_ids : false;
            const data = await this.orm.call("gn.stock.kardex.wizard", "get_kardex_json", [
                p.company_id, p.product_ids, p.date_from, p.date_to,
                p.branch_id, p.warehouse_id, false, locIds,
            ]);
            this.state.data = data;
            this.state.viewMode = p.initialView;
            if (data.error) this.state.error = data.error;
        } catch (e) {
            console.error(e);
            this.state.error = e.message || String(e);
        }
        this.state.loading = false;
    }

    // ── Navigation ──

    async openRecord(resModel, resId) {
        if (!resModel || !resId) return;
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "new",
        });
    }

    onRefClick(ev, line) {
        ev.preventDefault();
        if (!line.ref_action) return;
        this.openRecord(line.ref_action.res_model, line.ref_action.res_id);
    }

    onProductClick(ev) {
        ev.preventDefault();
        const sec = this.getSection();
        if (sec) this.openRecord("product.product", sec.product_id);
    }

    async openWizard() {
        const p = this.params;
        const ctx = {
            default_company_id: p.company_id,
            default_date_from: p.date_from,
            default_date_to: p.date_to,
            default_product_ids: [[6, 0, p.product_ids]],
        };
        if (p.branch_id) ctx.default_branch_id = p.branch_id;
        if (p.warehouse_id) ctx.default_warehouse_id = p.warehouse_id;
        if (p.location_ids && p.location_ids.length === 1) {
            ctx.default_location_id = p.location_ids[0];
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Kardex (AVCO)"),
            res_model: "gn.stock.kardex.wizard",
            views: [[false, "form"]],
            target: "new",
            context: ctx,
        });
    }

    async _createWizard() {
        const p = this.params;
        const vals = {
            company_id: p.company_id,
            date_from: p.date_from,
            date_to: p.date_to,
            product_ids: [[6, 0, p.product_ids]],
        };
        if (p.branch_id) vals.branch_id = p.branch_id;
        if (p.warehouse_id) vals.warehouse_id = p.warehouse_id;
        if (p.location_ids && p.location_ids.length === 1) {
            vals.location_id = p.location_ids[0];
        }
        const ids = await this.orm.create("gn.stock.kardex.wizard", [vals]);
        return ids[0];
    }

    async exportPdf() {
        const wid = await this._createWizard();
        const method = this.state.viewMode === "summary" ? "action_print_summary_pdf" : "action_print_pdf";
        const action = await this.orm.call("gn.stock.kardex.wizard", method, [wid]);
        if (action) this.actionService.doAction(action);
    }

    async exportXlsx() {
        const wid = await this._createWizard();
        const method = this.state.viewMode === "summary" ? "action_print_summary_xlsx" : "action_print_xlsx";
        const action = await this.orm.call("gn.stock.kardex.wizard", method, [wid]);
        if (action) this.actionService.doAction(action);
    }

    fmt2(n) {
        if (n === undefined || n === null || Number.isNaN(n)) return "0.00";
        return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    fmt4(n) {
        if (n === undefined || n === null || Number.isNaN(n)) return "0.0000";
        return Number(n).toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    }
}

registry.category("actions").add("gn_stock_kardex_preview", GnStockKardexPreview);
