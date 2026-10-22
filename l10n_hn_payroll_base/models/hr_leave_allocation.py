# -*- coding: utf-8 -*-
"""Timeline CE para asignaciones de vacaciones (`hr.leave.allocation`)."""

from datetime import timedelta

from odoo import api, fields, models

from .hr_holidays_timeline_support import (
    tl_badge_from_type_name,
    tl_color_from_leave_type_name,
    tl_day_totals_from_blocks,
    tl_employee_sidebar_hours,
    tl_nonwork_half_masks,
)


class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    @api.model
    def hn_payroll_base_timeline_data(self, date_start, date_end, department_id=False):
        """Igual contrato que en ``hr.leave`` (medios días, no laborable, horas barra)."""
        self.check_access("read")
        Employee = self.env["hr.employee"].sudo(False)

        start_d = fields.Date.from_string(date_start)
        end_d = fields.Date.from_string(date_end)
        if end_d < start_d:
            start_d, end_d = end_d, start_d

        overlap_domain = [
            ("date_from", "<=", end_d),
            "|",
            ("date_to", "=", False),
            ("date_to", ">=", start_d),
            ("state", "not in", ["refuse"]),
        ]
        allocations = self.search(overlap_domain, order="employee_id, date_from, id")

        emp_ids = set(allocations.mapped("employee_id").ids)
        if department_id:
            in_dept = Employee.search(
                [
                    ("active", "=", True),
                    ("department_id", "=", int(department_id)),
                ]
            )
            emp_ids.update(in_dept.ids)

        employees = Employee.browse(sorted(emp_ids))
        companies = self.env.companies
        employees = employees.filtered(
            lambda e: not e.company_id or e.company_id in companies
        )

        day_list = []
        cur = start_d
        while cur <= end_d:
            day_list.append(fields.Date.to_string(cur))
            cur += timedelta(days=1)

        day_count = len(day_list)
        nonwork_by_emp = tl_nonwork_half_masks(self.env, employees, day_list)

        emp_rows = []
        for emp in employees:
            emp_all = allocations.filtered(lambda a, eid=emp.id: a.employee_id.id == eid)
            days_sum = sum(emp_all.mapped("number_of_days")) or 0.0
            hours_sum = sum(emp_all.mapped("number_of_hours_display")) or 0.0
            hours_label = tl_employee_sidebar_hours(emp)
            note = hours_label
            if not note and days_sum:
                note = "%.1f d" % days_sum
            if not note and hours_sum:
                note = "%.0fh" % hours_sum
            emp_rows.append(
                {
                    "id": emp.id,
                    "name": emp.name,
                    "sidebar_hours": hours_label or "",
                    "sidebar_note": note or "",
                    "period_hours": round(hours_sum, 2),
                    "nonwork": nonwork_by_emp.get(emp.id, [False] * (2 * day_count)),
                }
            )

        blocks = []
        for rec in allocations:
            if rec.employee_id.id not in employees.ids:
                continue
            d0 = rec.date_from
            d1 = rec.date_to or end_d
            if not d0:
                continue
            if d1 and d0 > d1:
                d0, d1 = d1, d0
            clip_lo = max(d0, start_d)
            clip_hi = min(d1 if d1 else end_d, end_d)
            if clip_lo > clip_hi:
                continue
            di0 = (clip_lo - start_d).days
            di1 = (clip_hi - start_d).days
            i0 = di0 * 2
            i1 = di1 * 2 + 1
            ltype = rec.holiday_status_id
            type_name = ltype.name or ""
            badge = tl_badge_from_type_name(type_name)
            ndays = (clip_hi - clip_lo).days + 1
            blocks.append(
                {
                    "id": rec.id,
                    "employee_id": rec.employee_id.id,
                    "type_name": type_name,
                    "badge": badge,
                    "days_in_view": ndays,
                    "state": rec.state,
                    "can_approve": bool(rec.can_approve),
                    "can_validate": bool(rec.can_validate),
                    "can_refuse": bool(rec.can_refuse),
                    "color": tl_color_from_leave_type_name(
                        type_name, ltype.color if ltype else 0
                    ),
                    "grid_from": i0,
                    "grid_to": i1,
                    "label": "+%s %dd" % (badge, ndays),
                    "kind": "allocation",
                    "res_model": "hr.leave.allocation",
                    "res_id": rec.id,
                }
            )

        n_slots = 2 * day_count
        totals_half = [0] * n_slots
        for si in range(n_slots):
            em_on = set()
            for b in blocks:
                if b["grid_from"] <= si <= b["grid_to"]:
                    em_on.add(b["employee_id"])
            totals_half[si] = len(em_on)

        day_totals = tl_day_totals_from_blocks(blocks, day_count, 2)

        return {
            "days": day_list,
            "slot_count": n_slots,
            "slots_per_day": 2,
            "employees": sorted(emp_rows, key=lambda r: (r["name"] or "").lower()),
            "blocks": blocks,
            "totals": totals_half,
            "day_totals": day_totals,
        }
