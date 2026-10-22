/** @odoo-module **/

import { Component } from "@odoo/owl";
import { WIDGET_LABELS, WIDGET_META } from "./widget_layout";

export class PurchaseWidgetShell extends Component {
    static template = "gn_purchase_dashboard.PurchaseWidgetShell";
    static props = {
        item: Object,
        editMode: { type: Boolean, optional: true },
        gridStyle: String,
        onDragStart: { type: Function, optional: true },
        onDragOver: { type: Function, optional: true },
        onDrop: { type: Function, optional: true },
        onResizeStart: { type: Function, optional: true },
        staggerIndex: { type: Number, optional: true },
        slots: { type: Object, optional: true },
    };

    get shellStyle() {
        const base = this.props.gridStyle || "";
        const idx = this.props.staggerIndex ?? 0;
        return `${base};--gn-pd-stagger-delay:${idx * 70}ms`;
    }

    get title() {
        const fn = WIDGET_LABELS[this.props.item?.id];
        return fn ? fn() : this.props.item?.id;
    }

    get meta() {
        return WIDGET_META[this.props.item?.id] || {};
    }

    get iconClass() {
        return `fa ${this.meta.icon || "fa-bar-chart"}`;
    }

    get description() {
        return this.meta.desc || "";
    }

    onDragStart(ev) {
        if (!this.props.editMode) {
            ev.preventDefault();
            return;
        }
        ev.dataTransfer.setData("text/widget-id", this.props.item.id);
        ev.dataTransfer.effectAllowed = "move";
        if (this.props.onDragStart) this.props.onDragStart(this.props.item.id);
    }

    onDragOver(ev) {
        if (!this.props.editMode) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
    }

    onDrop(ev) {
        if (!this.props.editMode) return;
        ev.preventDefault();
        const draggedId = ev.dataTransfer.getData("text/widget-id");
        if (draggedId && draggedId !== this.props.item.id && this.props.onDrop) {
            this.props.onDrop(draggedId, this.props.item.id);
        }
    }

    onResizeMouseDown(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (this.props.onResizeStart) {
            this.props.onResizeStart(this.props.item.id, ev);
        }
    }
}
