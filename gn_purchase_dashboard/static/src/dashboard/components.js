/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { debounce } from "@web/core/utils/timing";

const SECONDARY_FILTER_FIELDS = [
    "compare_mode", "date_from", "date_to", "vendor_id",
    "warehouse_id", "category_id", "po_state", "project_id", "tag_id",
];

export class PurchaseFilterBar extends Component {
    static template = "gn_purchase_dashboard.PurchaseFilterBar";
    static props = {
        filterOptions: Object,
        draftFilters: Object,
        labels: Object,
        applying: { type: Boolean, optional: true },
        expanded: { type: Boolean, optional: true },
        favorites: { type: Array, optional: true },
        favoritesOpen: { type: Boolean, optional: true },
        activeChips: { type: Array, optional: true },
        onSelect: Function,
        onApply: Function,
        onReset: Function,
        onToggleExpanded: { type: Function, optional: true },
        onSaveFavorite: { type: Function, optional: true },
        onApplyFavorite: { type: Function, optional: true },
        onRemoveFavorite: { type: Function, optional: true },
        onToggleFavorites: { type: Function, optional: true },
        onRemoveChip: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ showMore: false });
        this._debouncedApply = debounce(() => this.props.onApply(), 450);
    }

    toggleMore() {
        this.state.showMore = !this.state.showMore;
    }

    onToggleExpandedClick() {
        if (this.props.onToggleExpanded) this.props.onToggleExpanded();
    }

    onSaveFavoriteClick() {
        if (this.props.onSaveFavorite) this.props.onSaveFavorite();
    }

    onToggleFavoritesClick() {
        if (this.props.onToggleFavorites) this.props.onToggleFavorites();
    }

    onApplyFavoriteClick(fav) {
        if (this.props.onApplyFavorite) this.props.onApplyFavorite(fav);
    }

    onRemoveFavoriteClick(favId, ev) {
        ev?.stopPropagation();
        if (this.props.onRemoveFavorite) this.props.onRemoveFavorite(favId, ev);
    }

    onRemoveChipClick(field, ev) {
        ev?.stopPropagation();
        if (this.props.onRemoveChip) this.props.onRemoveChip(field);
    }

    get secondaryActiveCount() {
        const f = this.props.draftFilters;
        let n = 0;
        for (const field of SECONDARY_FILTER_FIELDS) {
            const val = f[field];
            if (!val) continue;
            if (field === "compare_mode" && val === "previous") continue;
            n += 1;
        }
        return n;
    }

    get activeFilterCount() {
        const f = this.props.draftFilters;
        let n = this.secondaryActiveCount;
        if (f.period && f.period !== "this_month") n += 1;
        if (f.branch_id) n += 1;
        if (f.buyer_id) n += 1;
        if (f.vendor_id) n += 1;
        return n;
    }

    get moreFiltersLabel() {
        const n = this.secondaryActiveCount;
        return n ? _t("Más filtros · %s", n) : _t("Más filtros");
    }

    get collapseLabel() {
        return this.props.expanded ? _t("Ocultar filtros") : _t("Filtros");
    }

    _intVal(ev) {
        return ev.target.value ? parseInt(ev.target.value, 10) : false;
    }

    _select(field, value, autoApply = false) {
        this.props.onSelect(field, value);
        if (autoApply) this._debouncedApply();
    }

    onPeriodChange(ev) { this._select("period", ev.target.value, true); }
    onCompareChange(ev) { this._select("compare_mode", ev.target.value); }
    onCompanyChange(ev) { this._select("company_id", this._intVal(ev), true); }
    onDateFromChange(ev) {
        this.props.onSelect("date_from", ev.target.value || false);
        this.props.onSelect("period", "custom");
    }
    onDateToChange(ev) {
        this.props.onSelect("date_to", ev.target.value || false);
        this.props.onSelect("period", "custom");
    }
    onBranchChange(ev) { this._select("branch_id", this._intVal(ev)); }
    onBuyerChange(ev) { this._select("buyer_id", this._intVal(ev)); }
    onVendorChange(ev) { this._select("vendor_id", this._intVal(ev)); }
    onWarehouseChange(ev) { this._select("warehouse_id", this._intVal(ev)); }
    onCategoryChange(ev) { this._select("category_id", this._intVal(ev)); }
    onProjectChange(ev) { this._select("project_id", this._intVal(ev)); }
    onTagChange(ev) { this._select("tag_id", this._intVal(ev)); }
    onPoStateChange(ev) { this._select("po_state", ev.target.value || false); }
}
