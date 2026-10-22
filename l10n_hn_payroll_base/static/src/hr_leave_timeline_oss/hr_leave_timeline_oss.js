/** @odoo-module **/

/**
 * Laboratorio: integración OWL con frappe-gantt (MIT) y vis-timeline (Apache-2.0).
 * Las librerías se cargan en runtime (loadJS/loadCSS) para no hinchar el bundle.
 *
 * dhtmlxGantt y FullCalendar Scheduler no se redistribuyen: ver pestaña «Licencias».
 */

import { Component, onWillUnmount, status, useRef, useState } from "@odoo/owl";
import { loadCSS, loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

const COLOR_PALETTE = [
    "#5dade2",
    "#58d68d",
    "#f4d03f",
    "#eb984e",
    "#af7ac5",
    "#ec7063",
    "#48c9b0",
    "#5499c7",
    "#f5b041",
    "#bb8fce",
    "#85929e",
];

function colorFromOdooIndex(idx) {
    const n = Number.parseInt(idx, 10);
    return COLOR_PALETTE[Number.isFinite(n) ? Math.abs(n) % COLOR_PALETTE.length : 0];
}

function leaveLocalDateBounds(isoFrom, isoTo) {
    if (isoFrom == null || isoTo == null) {
        return null;
    }
    const a = DateTime.fromSQL(String(isoFrom).replace(" ", "T"), { zone: "utc" }).toLocal();
    const b = DateTime.fromSQL(String(isoTo).replace(" ", "T"), { zone: "utc" }).toLocal();
    if (!a.isValid || !b.isValid) {
        return null;
    }
    const start = a.toFormat("yyyy-MM-dd");
    const end = b.toFormat("yyyy-MM-dd");
    if (start > end) {
        return null;
    }
    return { start, end };
}

function progressFromState(st) {
    if (st === "validate") {
        return 100;
    }
    if (st === "validate1" || st === "confirm") {
        return 45;
    }
    return 20;
}

export class HrLeaveTimelineOss extends Component {
    static template = "l10n_hn_payroll_base.HrLeaveTimelineOss";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.frappeHostRef = useRef("frappeHost");
        this.visHostRef = useRef("visHost");
        this._gantt = null;
        this._timeline = null;
        this._frappeLoaded = false;
        this._visLoaded = false;

        const today = DateTime.local().toFormat("yyyy-MM-dd");
        const end = DateTime.local().plus({ weeks: 4 }).toFormat("yyyy-MM-dd");
        this.state = useState({
            engine: "frappe",
            rangeStart: today,
            rangeEnd: end,
            departmentId: "",
            departments: [],
            leaves: [],
            loading: false,
            error: false,
            errorMessage: "",
        });

        onWillUnmount(() => this.teardownCharts());

        this._boot();
    }

    async _boot() {
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
        await this.reload();
        await this.syncEngineMount();
    }

    teardownCharts() {
        if (this._timeline) {
            try {
                this._timeline.destroy();
            } catch {
                /* omitido */
            }
            this._timeline = null;
        }
        this._gantt = null;
        const fr = this.frappeHostRef.el;
        const vi = this.visHostRef.el;
        if (fr) {
            fr.innerHTML = "";
        }
        if (vi) {
            vi.innerHTML = "";
        }
    }

    async syncEngineMount() {
        this.teardownCharts();
        await new Promise((resolve) => requestAnimationFrame(() => resolve()));
        if (this.state.engine === "frappe") {
            await this.mountFrappe();
        } else if (this.state.engine === "vis") {
            await this.mountVis();
        }
    }

    async setEngine(name) {
        if (this.state.engine === name) {
            return;
        }
        this.state.engine = name;
        await this.syncEngineMount();
    }

    onDepartmentChange(ev) {
        this.state.departmentId = ev.target.value;
    }

    onRangeStartChange(ev) {
        this.state.rangeStart = ev.target.value;
    }

    onRangeEndChange(ev) {
        this.state.rangeEnd = ev.target.value;
    }

    async reload() {
        this.state.loading = true;
        this.state.error = false;
        this.state.errorMessage = "";
        const ds = this.state.rangeStart;
        const de = this.state.rangeEnd;
        const dept = this.state.departmentId ? parseInt(this.state.departmentId, 10) : false;
        let domain;
        if (dept) {
            domain = [
                "&",
                "&",
                "&",
                ["employee_id.department_id", "=", dept],
                ["state", "not in", ["cancel"]],
                ["date_from", "<=", `${de} 23:59:59`],
                ["date_to", ">=", `${ds} 00:00:00`],
            ];
        } else {
            domain = [
                "&",
                "&",
                ["state", "not in", ["cancel"]],
                ["date_from", "<=", `${de} 23:59:59`],
                ["date_to", ">=", `${ds} 00:00:00`],
            ];
        }
        try {
            this.state.leaves = await this.orm.searchRead(
                "hr.leave",
                domain,
                [
                    "id",
                    "employee_id",
                    "holiday_status_id",
                    "date_from",
                    "date_to",
                    "state",
                    "color",
                ],
                { order: "employee_id asc, date_from asc", limit: 800 },
            );
        } catch (e) {
            this.state.error = true;
            this.state.errorMessage =
                (e && e.data && e.data.message) ||
                (e && e.message) ||
                _t("Could not load data.");
            this.state.leaves = [];
        } finally {
            this.state.loading = false;
        }
        if (this.state.engine !== "readme") {
            await this.syncEngineMount();
        }
    }

    staticPathPrefix() {
        return "/l10n_hn_payroll_base/static/lib";
    }

    async ensureFrappe() {
        if (this._frappeLoaded) {
            return;
        }
        const p = this.staticPathPrefix();
        await loadCSS(`${p}/frappe-gantt/frappe-gantt.css`);
        await loadJS(`${p}/frappe-gantt/frappe-gantt.min.js`);
        this._frappeLoaded = true;
    }

    async ensureVis() {
        if (this._visLoaded) {
            return;
        }
        const p = this.staticPathPrefix();
        await loadCSS(`${p}/vis-timeline/vis-timeline-graph2d.css`);
        await loadJS(`${p}/vis-timeline/vis-timeline-graph2d.min.js`);
        this._visLoaded = true;
    }

    async mountFrappe() {
        await this.ensureFrappe();
        const host = this.frappeHostRef.el;
        if (!host || typeof window.Gantt === "undefined") {
            return;
        }
        host.innerHTML = "";
        const tasks = [];
        for (const lv of this.state.leaves) {
            const bounds = leaveLocalDateBounds(lv.date_from, lv.date_to);
            if (!bounds) {
                continue;
            }
            const { start, end } = bounds;
            const emp = lv.employee_id && lv.employee_id[1] ? lv.employee_id[1] : "?";
            const typ =
                lv.holiday_status_id && lv.holiday_status_id[1] ? lv.holiday_status_id[1] : "";
            tasks.push({
                id: String(lv.id),
                name: `${emp} · ${typ}`.trim(),
                start,
                end,
                progress: progressFromState(lv.state),
            });
        }

        let winStart = this.state.rangeStart;
        let winEnd = this.state.rangeEnd;
        if (winStart > winEnd) {
            [winStart, winEnd] = [winEnd, winStart];
        }
        /* Frappe Gantt: con 0 tareas no inicializa fechas y falla en start_of(null). */
        if (!tasks.length) {
            tasks.push({
                id: "__hn_tl_oss_empty__",
                name: _t("No time off in this range"),
                start: winStart,
                end: winEnd,
                progress: 0,
            });
        }

        const uid = `gantt-host-${Date.now()}`;
        host.id = uid;
        const Gantt = window.Gantt;
        this._gantt = new Gantt(`#${uid}`, tasks, {
            view_mode: "Month",
            bar_corner_radius: 4,
            padding: 16,
        });
        if (status(this) === "destroyed") {
            this.teardownCharts();
        }
    }

    async mountVis() {
        await this.ensureVis();
        const host = this.visHostRef.el;
        const vis = window.vis;
        if (!host || !vis || !vis.Timeline) {
            return;
        }
        host.innerHTML = "";

        const empMap = new Map();
        for (const lv of this.state.leaves) {
            if (lv.employee_id && lv.employee_id[0]) {
                empMap.set(lv.employee_id[0], lv.employee_id[1]);
            }
        }
        const groups = [...empMap.entries()].map(([id, name]) => ({
            id,
            content: name,
        }));
        if (!groups.length) {
            groups.push({ id: 0, content: _t("No rows") });
        }

        const items = [];
        for (const lv of this.state.leaves) {
            const eid = lv.employee_id && lv.employee_id[0] ? lv.employee_id[0] : 0;
            const typ =
                lv.holiday_status_id && lv.holiday_status_id[1] ? lv.holiday_status_id[1] : "";
            const bg = colorFromOdooIndex(lv.color);
            items.push({
                id: lv.id,
                group: eid,
                content: typ || String(lv.id),
                start: new Date(lv.date_from),
                end: new Date(lv.date_to),
                style: `background-color: ${bg}; border-color: ${bg}; color: #fff;`,
            });
        }

        const windowStart = DateTime.fromISO(this.state.rangeStart).startOf("day").toJSDate();
        const windowEnd = DateTime.fromISO(this.state.rangeEnd).endOf("day").toJSDate();

        this._timeline = new vis.Timeline(host, items, groups, {
            stack: false,
            orientation: "top",
            zoomMin: 1000 * 60 * 60 * 24,
            start: windowStart,
            end: windowEnd,
            groupOrder: "a",
        });
    }
}

registry.category("actions").add("hn_holidays_timeline_oss", HrLeaveTimelineOss);
