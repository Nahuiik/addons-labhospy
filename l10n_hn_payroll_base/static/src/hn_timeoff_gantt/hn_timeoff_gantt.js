/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HnTimeoffGanttRenderer } from "./hn_timeoff_gantt_renderer";
import {
    advancePivot,
    CAL_SCALE,
    describeWindow,
    resolveVisibleWindow,
    SLOT_MODE,
} from "./hn_timeoff_gantt_engine";

const { DateTime } = luxon;

/**
 * Vista Gantt propia (Community): recursos en filas, tiempo horizontal,
 * virtualización, escalas, selección y arrastre de ausencias.
 */
const EMPLOYEE_SORT = {
    NAME_ASC: "name_asc",
    NAME_DESC: "name_desc",
    LEAVES_DESC: "leaves_desc",
};

function escapeCsvField(val) {
    const s = val == null || val === false ? "" : String(val);
    if (/[",\n\r]/.test(s)) {
        return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
}

export class HnTimeoffGantt extends Component {
    static template = "l10n_hn_payroll_base.HnTimeoffGantt";
    static components = { HnTimeoffGanttRenderer };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("hnTlRoot");
        this.bodyScrollRef = useRef("bodyScroll");
        this._scrollTodayAfterLoad = false;
        const pivot = DateTime.local().startOf("day");
        const win = resolveVisibleWindow(CAL_SCALE.MONTH, pivot);
        this.state = useState({
            loading: true,
            error: null,
            mode: "leave",
            employeeSearch: "",
            maxDayTotal: 0,
            calendarScale: CAL_SCALE.MONTH,
            slotMode: SLOT_MODE.HALF,
            pivotDate: pivot,
            rangeStart: win.start,
            rangeEnd: win.end,
            days: [],
            slotCells: [],
            monthBands: [],
            employees: [],
            blocksByEmployee: {},
            totals: [],
            dayTotals: [],
            departments: [],
            departmentId: "",
            employeeSort: EMPLOYEE_SORT.NAME_ASC,
            showResourcePanel: true,
            payload: null,
            vScrollTop: 0,
            viewportHeight: 720,
            selection: null,
            selectionActive: null,
            drag: null,
        });

        this.employeeSortOptions = EMPLOYEE_SORT;

        onWillStart(async () => {
            await this.loadDepartments();
            await this.refresh();
        });

        onMounted(() => this._measureViewport());

        useExternalListener(window, "pointerup", this.onGlobalPointerUp.bind(this));
        useExternalListener(window, "pointercancel", this.onGlobalPointerUp.bind(this));
    }

    _measureViewport() {
        const el = this.bodyScrollRef.el;
        if (el) {
            this.state.viewportHeight = el.clientHeight || 720;
        }
    }

    get todayIso() {
        return DateTime.local().toFormat("yyyy-MM-dd");
    }

    get scales() {
        return CAL_SCALE;
    }

    get slotModes() {
        return SLOT_MODE;
    }

    get labelSortNameAsc() {
        return _t("Name A→Z");
    }
    get labelSortNameDesc() {
        return _t("Name Z→A");
    }
    get labelSortLeavesDesc() {
        return _t("Most time off in view");
    }
    get labelTogglePanel() {
        return _t("Resource panel");
    }
    get labelFullscreen() {
        return _t("Full screen");
    }
    get labelExportCsv() {
        return _t("Export CSV");
    }
    get placeholderSearchEmployees() {
        return _t("Search...");
    }

    onEmployeeSearchInput(ev) {
        this.state.employeeSearch = ev.target.value;
        const el = this.bodyScrollRef.el;
        if (el) {
            el.scrollTop = 0;
        }
        this.state.vScrollTop = 0;
    }

    rootClassNames() {
        const parts = ["o_hn_leave_tl", "d-flex", "flex-column", "h-100", "bg-view"];
        if (!this.state.showResourcePanel) {
            parts.push("o_hn_tl--minimal-side");
        }
        return parts.join(" ");
    }

    onEmployeeSortChange(ev) {
        this.state.employeeSort = ev.target.value;
        this._sortEmployees();
    }

    toggleResourcePanel() {
        this.state.showResourcePanel = !this.state.showResourcePanel;
    }

    async toggleFullscreen() {
        const el = this.rootRef.el;
        if (!el) {
            return;
        }
        try {
            if (document.fullscreenElement === el) {
                await document.exitFullscreen();
            } else {
                await el.requestFullscreen();
            }
        } catch {
            this.notification.add(_t("Fullscreen is not available in this browser."), {
                type: "warning",
            });
        }
    }

    exportPlanningCsv() {
        const slots = this.state.slotCells || [];
        const sep = ",";
        const headers = [
            "employee_name",
            "leave_type",
            "date_from",
            "date_to",
            "days_in_view",
            "state",
            "res_model",
            "res_id",
        ];
        const lines = [headers.join(sep)];
        for (const emp of this.state.employees) {
            for (const b of this._blocksFor(emp.id)) {
                const cf = slots[b.grid_from];
                const ct = slots[b.grid_to];
                const row = [
                    escapeCsvField(emp.name),
                    escapeCsvField(b.type_name),
                    escapeCsvField(cf && cf.iso),
                    escapeCsvField(ct && ct.iso),
                    escapeCsvField(b.days_in_view),
                    escapeCsvField(b.state),
                    escapeCsvField(b.res_model || "hr.leave"),
                    escapeCsvField(b.res_id),
                ];
                lines.push(row.join(sep));
            }
        }
        const blob = new Blob(["\ufeff", lines.join("\r\n")], {
            type: "text/csv;charset=utf-8;",
        });
        const a = document.createElement("a");
        const fname = `time_off_planning_${this.state.rangeStart.toFormat("yyyy-MM-dd")}_${this.state.rangeEnd.toFormat("yyyy-MM-dd")}.csv`;
        a.href = URL.createObjectURL(blob);
        a.download = fname;
        a.click();
        URL.revokeObjectURL(a.href);
        this.notification.add(_t("CSV export started."), { type: "info" });
    }

    scrollTimelineToToday() {
        const scrollEl = this.bodyScrollRef.el;
        const today = this.todayIso;
        const cells = this.state.slotCells;
        if (!scrollEl || !cells || !cells.length) {
            return;
        }
        let si = -1;
        for (let i = 0; i < cells.length; i++) {
            if (cells[i].iso === today) {
                si = i;
                break;
            }
        }
        if (si < 0) {
            this.notification.add(_t("Current date is outside the visible range."), {
                type: "warning",
            });
            return;
        }
        const n = Math.max(1, cells.length);
        const ratio = (si + 0.5) / n;
        const maxScroll = Math.max(0, scrollEl.scrollWidth - scrollEl.clientWidth);
        scrollEl.scrollLeft = Math.round(ratio * maxScroll);
    }

    _sortEmployees() {
        const emps = this.state.employees;
        if (!emps || emps.length < 2) {
            return;
        }
        const by = this.state.blocksByEmployee || {};
        const sort = this.state.employeeSort;
        const nameKey = (e) => (e.name || "").toLowerCase();
        const countLeaves = (e) => (by[e.id] || []).length;
        const sorted = [...emps];
        if (sort === EMPLOYEE_SORT.NAME_DESC) {
            sorted.sort((a, b) => nameKey(b).localeCompare(nameKey(a)));
        } else if (sort === EMPLOYEE_SORT.LEAVES_DESC) {
            sorted.sort((a, b) => {
                const d = countLeaves(b) - countLeaves(a);
                if (d !== 0) {
                    return d;
                }
                return nameKey(a).localeCompare(nameKey(b));
            });
        } else {
            sorted.sort((a, b) => nameKey(a).localeCompare(nameKey(b)));
        }
        this.state.employees = sorted;
    }

    get rendererProps() {
        return {
            state: this.state,
            todayIso: this.todayIso,
            daysColumnLabel: this.daysColumnLabel,
            totalRowLabel: this.totalRowLabel,
            showGridNav: this.state.showResourcePanel,
            rangeSummary: this.spanSummary(),
            todayLabel: this.todayLabel,
            labelFullscreen: this.labelFullscreen,
            onNavigateStep: this.navigateStep.bind(this),
            onJumpToday: this.jumpToToday.bind(this),
            onToggleFullscreen: this.toggleFullscreen.bind(this),
            labelOpenForm: this.labelOpenForm,
            labelApprove: this.labelApprove,
            labelValidate: this.labelValidate,
            labelRefuse: this.labelRefuse,
            onCellPointerDown: this.onCellPointerDown.bind(this),
            onCellPointerEnter: this.onCellPointerEnter.bind(this),
            onTrackCellDblClick: this.onTrackCellDblClick.bind(this),
            onPillPointerDown: this.onPillPointerDown.bind(this),
            onPillPointerMove: this.onPillPointerMove.bind(this),
            onPillPointerUp: this.onPillPointerUp.bind(this),
            openRecord: this.openRecord.bind(this),
            quickAction: this.quickAction.bind(this),
        };
    }

    _blocksFor(empId) {
        return this.state.blocksByEmployee[empId] || [];
    }

    async loadDepartments() {
        try {
            const rows = await this.orm.searchRead(
                "hr.department",
                [],
                ["id", "name"],
                { order: "name asc", limit: 400 },
            );
            this.state.departments = rows;
        } catch {
            this.state.departments = [];
        }
    }

    get loadingLabel() {
        return _t("Loading…");
    }
    get errorLoadLabel() {
        return _t("Could not load the planning data.");
    }
    get todayLabel() {
        return _t("Today");
    }
    get allDepartmentsLabel() {
        return _t("All departments");
    }
    get myTimeOffLabel() {
        return _t("My time off");
    }
    get myAllocationsLabel() {
        return _t("My allocations");
    }
    get totalRowLabel() {
        return _t("Total");
    }
    get daysColumnLabel() {
        return _t("Days");
    }
    get tabRequestsLabel() {
        return _t("Requests");
    }
    get tabAllocationsLabel() {
        return _t("Allocations");
    }
    get labelOpenForm() {
        return _t("Open");
    }
    get labelApprove() {
        return _t("Approve");
    }
    get labelValidate() {
        return _t("Validate");
    }
    get labelRefuse() {
        return _t("Refuse");
    }
    get labelCreateSelection() {
        return _t("New from selection");
    }
    get labelClearSelection() {
        return _t("Clear");
    }

    spanSummary() {
        return describeWindow(this.state.rangeStart, this.state.rangeEnd);
    }

    selectionBarText() {
        const s = this.state.selection;
        if (!s) {
            return "";
        }
        const a = Math.min(s.si0, s.si1);
        const b = Math.max(s.si0, s.si1);
        const ca = this.state.slotCells[a];
        const cb = this.state.slotCells[b];
        if (!ca || !cb) {
            return "";
        }
        const da = DateTime.fromFormat(ca.iso, "yyyy-MM-dd", { zone: "local" });
        const db = DateTime.fromFormat(cb.iso, "yyyy-MM-dd", { zone: "local" });
        return `${da.toFormat("dd/MM/yyyy")} -> ${db.toFormat("dd/MM/yyyy")}`;
    }

    async quickAction(block, method) {
        const model = block.res_model || "hr.leave";
        try {
            await this.orm.call(model, method, [[block.res_id]]);
            this.notification.add(_t("The record was updated."), { type: "success" });
            await this.refresh();
        } catch (e) {
            const msg =
                (e && e.data && e.data.message) ||
                (e && e.message) ||
                _t("The operation could not be completed.");
            this.notification.add(msg, { type: "danger" });
        }
    }

    _applyPivotWindow() {
        const w = resolveVisibleWindow(this.state.calendarScale, this.state.pivotDate);
        this.state.rangeStart = w.start;
        this.state.rangeEnd = w.end;
    }

    async setCalendarScale(scale) {
        void scale;
        if (this.state.calendarScale !== CAL_SCALE.MONTH) {
            this.state.calendarScale = CAL_SCALE.MONTH;
            if (this.state.slotMode === SLOT_MODE.HOUR) {
                this.state.slotMode = SLOT_MODE.HALF;
            }
            this._applyPivotWindow();
            await this.refresh();
        }
    }

    async setSlotMode(mode) {
        if (mode === SLOT_MODE.HOUR) {
            return;
        }
        if (this.state.slotMode === mode) {
            return;
        }
        this.state.slotMode = mode;
        await this.refresh();
    }

    async setMode(mode) {
        if (this.state.mode === mode) {
            return;
        }
        this.state.mode = mode;
        if (mode === "allocation") {
            this.state.slotMode = SLOT_MODE.HALF;
        }
        await this.refresh();
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        this.state.selection = null;
        this.state.selectionActive = null;
        this.state.drag = null;
        const ds = this.state.rangeStart.toFormat("yyyy-MM-dd");
        const de = this.state.rangeEnd.toFormat("yyyy-MM-dd");
        const dept = this.state.departmentId ? parseInt(this.state.departmentId, 10) : false;
        const model =
            this.state.mode === "allocation" ? "hr.leave.allocation" : "hr.leave";
        try {
            let data;
            if (model === "hr.leave") {
                data = await this.orm.call("hr.leave", "hn_payroll_base_timeline_data", [
                    ds,
                    de,
                    dept || false,
                    this.state.slotMode,
                ]);
            } else {
                data = await this.orm.call(model, "hn_payroll_base_timeline_data", [
                    ds,
                    de,
                    dept || false,
                ]);
            }
            this.state.payload = data;
            this.state.days = data.days || [];
            this.state.totals = data.totals || [];
            this.state.dayTotals = data.day_totals || [];
            this.state.employees = data.employees || [];
            this._rebuildSlotGrid();
            this._indexBlocks(data.blocks || []);
            this._sortEmployees();
        } catch (e) {
            this.state.error = e;
            this.state.days = [];
            this.state.employees = [];
            this.state.blocksByEmployee = {};
            this.state.totals = [];
            this.state.dayTotals = [];
            this.state.maxDayTotal = 0;
            this.state.slotCells = [];
            this.state.monthBands = [];
        } finally {
            this.state.loading = false;
            const doScroll = this._scrollTodayAfterLoad;
            this._scrollTodayAfterLoad = false;
            if (doScroll && !this.state.error) {
                requestAnimationFrame(() => this.scrollTimelineToToday());
            }
        }
    }

    _rebuildSlotGrid() {
        const totals = this.state.totals || [];
        const dayTotals = this.state.dayTotals || [];
        let maxDay = 0;
        for (const v of dayTotals) {
            const n = Number(v) || 0;
            if (n > maxDay) {
                maxDay = n;
            }
        }
        this.state.maxDayTotal = maxDay;

        const days = this.state.days || [];
        const sp =
            (this.state.payload && this.state.payload.slots_per_day) ||
            (this.state.slotMode === SLOT_MODE.HOUR ? 24 : 2);
        const slots = [];
        const monthBands = [];
        let curBand = null;
        const cal = this.state.calendarScale;
        for (let di = 0; di < days.length; di++) {
            const iso = days[di];
            const dt = DateTime.fromFormat(iso, "yyyy-MM-dd", { zone: "local" });
            const ymk = dt.toFormat("yyyy-MM");
            const label = dt.toFormat("LLLL yyyy");
            for (let u = 0; u < sp; u++) {
                const si = slots.length;
                if (!curBand || curBand.key !== ymk) {
                    if (curBand) {
                        monthBands.push(curBand);
                    }
                    curBand = { key: ymk, label, start: si, count: 0 };
                }
                curBand.count++;
                let dom = null;
                if (sp === 2) {
                    dom = u === 0 ? dt.day : null;
                } else if (cal === CAL_SCALE.DAY) {
                    dom = u;
                } else if (u % 4 === 0) {
                    dom = u;
                }
                slots.push({
                    iso,
                    unit: u,
                    dayIndex: di,
                    si,
                    dom,
                    weekday: dt.weekday,
                    isWeekend: dt.weekday >= 6,
                    total: totals[si] ?? 0,
                    dayTotal: u === 0 ? dayTotals[di] ?? 0 : null,
                });
            }
        }
        if (curBand) {
            monthBands.push(curBand);
        }
        this.state.slotCells = slots;
        this.state.monthBands = monthBands;
    }

    _indexBlocks(blocks) {
        const by = {};
        for (const b of blocks) {
            const eid = b.employee_id;
            if (!by[eid]) {
                by[eid] = [];
            }
            by[eid].push(b);
        }
        this.state.blocksByEmployee = by;
    }

    onDepartmentChange(ev) {
        this.state.departmentId = ev.target.value;
        this.refresh();
    }

    onBodyScroll(ev) {
        this.state.vScrollTop = ev.target.scrollTop;
    }

    async navigateStep(delta) {
        this.state.pivotDate = advancePivot(CAL_SCALE.MONTH, this.state.pivotDate, delta);
        this._applyPivotWindow();
        await this.refresh();
    }

    async jumpToToday() {
        this._scrollTodayAfterLoad = true;
        this.state.pivotDate = DateTime.local().startOf("day");
        this._applyPivotWindow();
        await this.refresh();
    }

    async openRecord(block) {
        const resModel = block.res_model || "hr.leave";
        const resId = block.res_id || block.id;
        if (!resId) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onCellPointerDown(ev, row, cell) {
        if (ev.button !== 0 || this.state.mode !== "leave") {
            return;
        }
        if (ev.target.closest(".o_hn_tl_pill")) {
            return;
        }
        this.state.selectionActive = {
            empId: row.id,
            si0: cell.si,
            si1: cell.si,
            pointerId: ev.pointerId,
        };
    }

    onCellPointerEnter(ev, row, cell) {
        const s = this.state.selectionActive;
        if (!s || s.empId !== row.id) {
            return;
        }
        s.si1 = cell.si;
    }

    onGlobalPointerUp() {
        const s = this.state.selectionActive;
        if (s) {
            this.state.selection = {
                empId: s.empId,
                si0: Math.min(s.si0, s.si1),
                si1: Math.max(s.si0, s.si1),
            };
            this.state.selectionActive = null;
        }
        const drag = this.state.drag;
        if (drag) {
            void this._finishDrag(drag);
        }
    }

    clearSelection() {
        this.state.selection = null;
        this.state.selectionActive = null;
    }

    async createFromSelection() {
        const s = this.state.selection;
        if (!s || this.state.mode !== "leave") {
            return;
        }
        const a = s.si0;
        const b = s.si1;
        const ca = this.state.slotCells[a];
        const cb = this.state.slotCells[b];
        if (!ca || !cb) {
            return;
        }
        const d0 = ca.iso <= cb.iso ? ca.iso : cb.iso;
        const d1 = ca.iso <= cb.iso ? cb.iso : ca.iso;
        try {
            await this.action.doAction("hr_holidays.hr_leave_action_new_request", {
                additionalContext: {
                    default_employee_id: s.empId,
                    default_request_date_from: d0,
                    default_request_date_to: d1,
                },
            });
        } catch {
            /* omitido */
        }
        this.clearSelection();
    }

    async onTrackCellDblClick(employeeId, isoDate) {
        if (!employeeId || !isoDate) {
            return;
        }
        try {
            if (this.state.mode === "leave") {
                await this.action.doAction("hr_holidays.hr_leave_action_new_request", {
                    additionalContext: {
                        default_employee_id: employeeId,
                        default_request_date_from: isoDate,
                        default_request_date_to: isoDate,
                    },
                });
            } else {
                await this.action.doAction("hr_holidays.hr_leave_allocation_action_form", {
                    additionalContext: {
                        default_employee_id: employeeId,
                        default_date_from: isoDate,
                        default_date_to: isoDate,
                    },
                });
            }
        } catch {
            /* omitido */
        }
    }

    onPillPointerDown(ev, block, row) {
        if (this.state.mode !== "leave" || !block.may_drag) {
            return;
        }
        this.state.selectionActive = null;
        ev.preventDefault();
        ev.stopPropagation();
        const track = ev.currentTarget.closest(".o_hn_leave_tl_track");
        const tw = track ? track.clientWidth : 1;
        const n = Math.max(1, this.state.slotCells.length);
        try {
            ev.currentTarget.setPointerCapture(ev.pointerId);
        } catch {
            /* omitido */
        }
        this.state.drag = {
            resId: block.res_id,
            empId: row.id,
            gf: block.grid_from,
            gt: block.grid_to,
            pointerId: ev.pointerId,
            startX: ev.clientX,
            trackWidth: tw,
            n,
            previewDelta: 0,
        };
    }

    onPillPointerMove(ev, block) {
        const d = this.state.drag;
        if (!d || d.resId !== block.res_id || ev.pointerId !== d.pointerId) {
            return;
        }
        const slotW = d.trackWidth / d.n;
        d.previewDelta = Math.round((ev.clientX - d.startX) / Math.max(1e-6, slotW));
    }

    onPillPointerUp(ev) {
        try {
            ev.currentTarget.releasePointerCapture(ev.pointerId);
        } catch {
            /* omitido */
        }
    }

    async _finishDrag(d) {
        if (!d) {
            return;
        }
        this.state.drag = null;
        const dur = d.gt - d.gf + 1;
        let ngf = d.gf + (d.previewDelta || 0);
        ngf = Math.max(0, Math.min(d.n - dur, ngf));
        const ngt = ngf + dur - 1;
        if (ngf === d.gf && ngt === d.gt) {
            return;
        }
        const ds = this.state.rangeStart.toFormat("yyyy-MM-dd");
        const de = this.state.rangeEnd.toFormat("yyyy-MM-dd");
        try {
            await this.orm.call(
                "hr.leave",
                "hn_payroll_base_timeline_reschedule_leave",
                [d.resId, ds, de, ngf, ngt, this.state.slotMode],
            );
            this.notification.add(_t("Time off updated."), { type: "success" });
            await this.refresh();
        } catch (e) {
            const msg =
                (e && e.data && e.data.message) ||
                (e && e.message) ||
                _t("Could not reschedule.");
            this.notification.add(msg, { type: "danger" });
            await this.refresh();
        }
    }

    async openMyRecords() {
        if (this.state.mode === "leave") {
            await this.action.doAction("hr_holidays.hr_leave_action_my");
        } else {
            await this.action.doAction("hr_holidays.hr_leave_allocation_action_my");
        }
    }
}

registry.category("actions").add("hn_holidays_timeline_ce", HnTimeoffGantt);

/** Alias histórico (mismo componente). */
export { HnTimeoffGantt as HnHolidaysTimelineCe };
