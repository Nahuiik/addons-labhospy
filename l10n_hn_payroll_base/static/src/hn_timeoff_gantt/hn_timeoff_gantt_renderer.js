/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { columnHintPx, VIRTUAL_ROW_PX } from "./hn_timeoff_gantt_engine";

/**
 * Renderer propio del Gantt de ausencias (solo presentación y geometría de rejilla).
 * La lógica de datos, RPC y toolbar vive en {@link HnTimeoffGantt}.
 */
export class HnTimeoffGanttRenderer extends Component {
    static template = "l10n_hn_payroll_base.HnTimeoffGanttRenderer";
    static components = { Avatar, Dropdown, DropdownItem };
    static props = {
        state: Object,
        todayIso: String,
        daysColumnLabel: String,
        totalRowLabel: String,
        showGridNav: { type: Boolean, optional: true },
        rangeSummary: { type: String, optional: true },
        todayLabel: { type: String, optional: true },
        labelFullscreen: { type: String, optional: true },
        onNavigateStep: { type: Function, optional: true },
        onJumpToday: { type: Function, optional: true },
        onToggleFullscreen: { type: Function, optional: true },
        labelOpenForm: String,
        labelApprove: String,
        labelValidate: String,
        labelRefuse: String,
        onCellPointerDown: Function,
        onCellPointerEnter: Function,
        onTrackCellDblClick: Function,
        onPillPointerDown: Function,
        onPillPointerMove: Function,
        onPillPointerUp: Function,
        openRecord: Function,
        quickAction: Function,
    };

    tableScaleClass() {
        const s = this.props.state;
        return `o_hn_tl-cal-${s.calendarScale} o_hn_tl-slot-${s.slotMode}`;
    }

    /**
     * Clase raíz + variables CSS para la rejilla horizontal.
     * `t-att-style` con objeto y gridTemplateColumns no siempre aplica en Odoo OWL:
     * sin columnas explícitas el grid queda en 1 columna y los días se apilan en vertical.
     */
    tableRootClass() {
        return `o_hn_leave_tl_table ${this.tableScaleClass()}`;
    }

    tableCssVarsStyle() {
        const s = this.props.state;
        const n = Math.max(1, s.slotCells.length);
        const w = columnHintPx(s.slotMode, s.calendarScale);
        const monthRowH = this.props.showGridNav ? "4.125rem" : "2.25rem";
        return `--hn-tl-cols:${n};--hn-tl-col-min:${w}px;--hn-tl-sticky-months-height:${monthRowH}`;
    }

    filteredEmployees() {
        const s = this.props.state;
        const q = (s.employeeSearch || "").trim().toLowerCase();
        const emps = s.employees || [];
        if (!q) {
            return emps;
        }
        return emps.filter((e) => (e.name || "").toLowerCase().includes(q));
    }

    rowWindow() {
        const s = this.props.state;
        const rh = VIRTUAL_ROW_PX;
        const st = s.vScrollTop;
        const vh = s.viewportHeight || 640;
        const rows = this.filteredEmployees();
        const buf = 8;
        const start = Math.max(0, Math.floor(st / rh) - buf);
        const end = Math.min(rows.length, Math.ceil((st + vh) / rh) + buf);
        return {
            start,
            end,
            topPad: start * rh,
            botPad: (rows.length - end) * rh,
        };
    }

    visibleEmployeeRows() {
        const { start, end } = this.rowWindow();
        return this.filteredEmployees().slice(start, end);
    }

    slotsPerDay() {
        const p = this.props.state.payload;
        const sp = p && p.slots_per_day;
        if (sp && sp > 0) {
            return sp;
        }
        return this.props.state.slotMode === "hour" ? 24 : 2;
    }

    dayTotalCellSpanStyle() {
        const sp = this.slotsPerDay();
        return `grid-column: span ${sp}`;
    }

    totalBarFillStyle(dayTotal) {
        const max = Math.max(1, this.props.state.maxDayTotal || 0);
        const n = Number(dayTotal) || 0;
        if (n <= 0) {
            return "height:0;min-height:0";
        }
        const h = Math.max(6, Math.round((n / max) * 36));
        return `height:${h}px`;
    }

    monthBandStyle(band) {
        return `flex: ${band.count} 1 0; min-width: 0`;
    }

    avatarProps(row) {
        return {
            resModel: "hr.employee.public",
            resId: row.id,
            displayName: "",
            noSpacing: true,
            canOpenPopover: false,
            cssClass: "o_hn_tl_avatar",
        };
    }

    nonworkAt(row, slotIndex) {
        const nw = row.nonwork;
        if (!nw || slotIndex < 0 || slotIndex >= nw.length) {
            return false;
        }
        return !!nw[slotIndex];
    }

    isTodayCell(cell) {
        return cell.iso === this.props.todayIso;
    }

    isSelectedCell(empId, si) {
        const s = this.props.state.selection;
        if (!s || s.empId !== empId) {
            return false;
        }
        const lo = Math.min(s.si0, s.si1);
        const hi = Math.max(s.si0, s.si1);
        return si >= lo && si <= hi;
    }

    isSelectingCell(empId, si) {
        const s = this.props.state.selectionActive;
        if (!s || s.empId !== empId) {
            return false;
        }
        const lo = Math.min(s.si0, s.si1);
        const hi = Math.max(s.si0, s.si1);
        return si >= lo && si <= hi;
    }

    blocksFor(empId) {
        const by = this.props.state.blocksByEmployee;
        return (by && by[empId]) || [];
    }

    showApproveInMenu(block) {
        return !!block.can_approve;
    }
    showValidateInMenu(block) {
        return !!(block.can_validate && !block.can_approve);
    }
    showRefuseInMenu(block) {
        return !!block.can_refuse;
    }

    pillClass(block, dragExtra = "") {
        const st = block.state || "";
        const stateCls = {
            confirm: "o_hn_tl_pill_pending",
            validate1: "o_hn_tl_pill_second",
            validate: "o_hn_tl_pill_ok",
            refuse: "o_hn_tl_pill_refused",
        }[st];
        const kindCls = block.kind === "allocation" ? "o_hn_tl_pill_alloc" : "";
        const dragCls = dragExtra || "";
        return `o_hn_tl_pill_btn ${stateCls || ""} ${kindCls} ${dragCls}`.trim();
    }

    pillAbsStyle(block, dragState) {
        const s = this.props.state;
        const n = Math.max(1, s.slotCells.length);
        let gf = block.grid_from;
        let gt = block.grid_to;
        if (
            dragState &&
            dragState.resId === block.res_id &&
            Number.isFinite(dragState.previewDelta)
        ) {
            const dur = gt - gf + 1;
            gf = Math.max(0, Math.min(n - dur, gf + dragState.previewDelta));
            gt = gf + dur - 1;
        }
        const left = (gf / n) * 100;
        const width = ((gt - gf + 1) / n) * 100;
        const bg = block.color || "#5499c7";
        return `position:absolute;top:6px;height:28px;left:${left}%;width:${width}%;min-width:2rem;background-color:${bg};`;
    }
}
