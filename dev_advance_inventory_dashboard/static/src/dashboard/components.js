/** @odoo-module **/

import { Component } from "@odoo/owl";

export class InvDashboardFilterBar extends Component {
    static template = "dev_advance_inventory_dashboard.InvDashboardFilterBar";
    static props = {
        draftFilters: Object,
        filterOptions: Object,
        labels: Object,
        onDraftChange: Function,
        onApply: Function,
        onReset: Function,
    };

    onSelect(field, ev) {
        const val = ev.target.value;
        const parsed = val ? parseInt(val, 10) : false;
        this.props.onDraftChange({ [field]: parsed });
    }

    onPeriodChange(ev) {
        this.props.onDraftChange({ period: ev.target.value });
    }

    onDateFromChange(ev) {
        this.props.onDraftChange({ period: "custom", date_from: ev.target.value || false });
    }

    onDateToChange(ev) {
        this.props.onDraftChange({ period: "custom", date_to: ev.target.value || false });
    }

    onLotChange(ev) {
        this.onSelect("lot_id", ev);
    }

    onWarehouseChange(ev) {
        this.onSelect("warehouse_id", ev);
    }

    onBranchChange(ev) {
        this.onSelect("branch_id", ev);
    }

    onLocationChange(ev) {
        this.onSelect("location_id", ev);
    }

    onCategoryChange(ev) {
        this.onSelect("category_id", ev);
    }

    onOperationTypeChange(ev) {
        this.onSelect("operation_type_id", ev);
    }

    onSupplierChange(ev) {
        this.onSelect("supplier_id", ev);
    }

    onCustomerChange(ev) {
        this.onSelect("customer_id", ev);
    }

    onResponsibleChange(ev) {
        this.onSelect("responsible_id", ev);
    }

    onCompanyChange(ev) {
        this.onSelect("company_id", ev);
    }

    onApplyClick() {
        this.props.onApply();
    }

    onResetClick() {
        this.props.onReset();
    }
}

export class InvDashboardLayoutEditor extends Component {
    static template = "dev_advance_inventory_dashboard.InvDashboardLayoutEditor";
    static props = {
        layouts: Array,
        activeLayoutId: [Number, Boolean],
        widgets: Array,
        labels: Object,
        onSave: Function,
        onReset: Function,
        onClose: Function,
        onToggleWidget: Function,
        onMoveWidget: Function,
        layoutPresets: { type: Array, optional: true },
        refreshMinutes: { type: Number, optional: true },
        onDragReorder: Function,
        onApplyPreset: Function,
        onRefreshChange: Function,
    };

    onWidgetToggle(widgetId) {
        this.props.onToggleWidget(widgetId);
    }

    onWidgetMove(widgetId, delta) {
        this.props.onMoveWidget(widgetId, delta);
    }

    onSaveClick() {
        this.props.onSave();
    }

    onResetLayoutClick() {
        this.props.onReset();
    }

    onCloseClick() {
        this.props.onClose();
    }

    onDragStart(ev, widgetId) {
        ev.dataTransfer.setData("text/plain", widgetId);
    }

    onDrop(ev, targetId) {
        ev.preventDefault();
        const sourceId = ev.dataTransfer.getData("text/plain");
        if (sourceId && sourceId !== targetId) {
            this.props.onDragReorder(sourceId, targetId);
        }
    }

    onDragOver(ev) {
        ev.preventDefault();
    }

    onPresetChange(ev) {
        const val = ev.target.value;
        if (val) this.props.onApplyPreset(val);
        ev.target.value = "";
    }

    onRefreshSelect(ev) {
        this.props.onRefreshChange(parseInt(ev.target.value, 10) || 0);
    }
}
