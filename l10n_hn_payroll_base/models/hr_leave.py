# -*- coding: utf-8 -*-
"""Extensión Time Off: datos agregados para la vista planificadora CE (sin Enterprise)."""

from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .hr_holidays_timeline_support import (
    tl_badge_from_type_name,
    tl_color_from_leave_type_name,
    tl_day_totals_from_blocks,
    tl_employee_sidebar_hours,
    tl_expand_nonwork_half_to_hour,
    tl_grid_to_write_values_leave,
    tl_leave_slot_indices,
    tl_nonwork_half_masks,
    tl_slots_per_day,
)


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.model
    def hn_payroll_base_timeline_data(
        self, date_start, date_end, department_id=False, slot_mode="half"
    ):
        """Devuelve días, ranuras, empleados y bloques de ausencia.

        ``slot_mode``: ``half`` (2 ranuras/día) u ``hour`` (24 ranuras/día derivadas de AM/PM).

        JSON-RPC: ``date_start``, ``date_end`` ``YYYY-MM-DD``, ``department_id`` opcional,
        ``slot_mode`` opcional.
        """
        self.check_access("read")
        if slot_mode not in ("half", "hour"):
            slot_mode = "half"
        Employee = self.env["hr.employee"].sudo(False)

        start_d = fields.Date.from_string(date_start)
        end_d = fields.Date.from_string(date_end)
        if end_d < start_d:
            start_d, end_d = end_d, start_d

        user_tz_name = self.env.user.tz or self.env.company.partner_id.tz or "UTC"
        tz = pytz.timezone(user_tz_name)

        range_start_dt = tz.localize(datetime.combine(start_d, time.min))
        range_end_dt = tz.localize(datetime.combine(end_d, time.max))

        domain = [
            (
                "date_from",
                "<=",
                range_end_dt.astimezone(pytz.UTC).replace(tzinfo=None),
            ),
            (
                "date_to",
                ">=",
                range_start_dt.astimezone(pytz.UTC).replace(tzinfo=None),
            ),
            ("state", "not in", ["cancel"]),
        ]
        leaves = self.search(domain, order="employee_id, date_from, id")

        def local_day_bounds(dt_val):
            if not dt_val:
                return None
            if dt_val.tzinfo is None:
                dt_val = pytz.UTC.localize(dt_val)
            local = dt_val.astimezone(tz)
            return local.date()

        emp_ids = set(leaves.mapped("employee_id").ids)
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
        nonwork_half = tl_nonwork_half_masks(self.env, employees, day_list)

        sp = tl_slots_per_day(slot_mode)
        emp_rows = []
        for emp in employees:
            period_hours = sum(
                leaves.filtered(lambda l, eid=emp.id: l.employee_id.id == eid).mapped(
                    "number_of_hours"
                )
            )
            hours_label = tl_employee_sidebar_hours(emp)
            note = hours_label
            if not note and emp.allocation_remaining_display:
                note = "%s d" % (emp.allocation_remaining_display.strip(),)
            if not note and period_hours:
                note = "%.0fh" % period_hours
            mask = nonwork_half.get(emp.id, [False] * (2 * day_count))
            if slot_mode == "hour":
                mask = tl_expand_nonwork_half_to_hour(mask)
            emp_rows.append(
                {
                    "id": emp.id,
                    "name": emp.name,
                    "sidebar_hours": hours_label or "",
                    "sidebar_note": note or "",
                    "period_hours": round(period_hours, 2),
                    "nonwork": mask,
                }
            )

        blocks = []
        for lv in leaves:
            if lv.employee_id.id not in employees.ids:
                continue
            d0 = local_day_bounds(lv.date_from)
            d1 = local_day_bounds(lv.date_to)
            if not d0 or not d1:
                continue
            if d0 > d1:
                d0, d1 = d1, d0
            clip_lo = max(d0, start_d)
            clip_hi = min(d1, end_d)
            if clip_lo > clip_hi:
                continue
            i0, i1 = tl_leave_slot_indices(
                lv.date_from, lv.date_to, start_d, end_d, day_count, tz, slot_mode
            )
            ltype = lv.holiday_status_id
            type_name = ltype.name or ""
            badge = tl_badge_from_type_name(type_name)
            ndays = max(
                1,
                int(round(lv.number_of_days or 0)) or (clip_hi - clip_lo).days + 1,
            )
            blocks.append(
                {
                    "id": lv.id,
                    "employee_id": lv.employee_id.id,
                    "type_name": type_name,
                    "badge": badge,
                    "days_in_view": ndays,
                    "state": lv.state,
                    "can_approve": bool(lv.can_approve),
                    "can_validate": bool(lv.can_validate),
                    "can_refuse": bool(lv.can_refuse),
                    "may_drag": lv.state in ("confirm", "validate1"),
                    "color": tl_color_from_leave_type_name(type_name, lv.color),
                    "grid_from": i0,
                    "grid_to": i1,
                    "label": "%s %dd" % (badge, ndays),
                    "kind": "leave",
                    "res_model": "hr.leave",
                    "res_id": lv.id,
                }
            )

        n_slots = sp * day_count
        totals = [0] * n_slots
        for si in range(n_slots):
            em_on = set()
            for b in blocks:
                if b["grid_from"] <= si <= b["grid_to"]:
                    em_on.add(b["employee_id"])
            totals[si] = len(em_on)

        day_totals = tl_day_totals_from_blocks(blocks, day_count, sp)

        return {
            "user_tz": user_tz_name,
            "days": day_list,
            "slot_mode": slot_mode,
            "slots_per_day": sp,
            "slot_count": n_slots,
            "employees": sorted(emp_rows, key=lambda r: (r["name"] or "").lower()),
            "blocks": blocks,
            "totals": totals,
            "day_totals": day_totals,
        }

    @api.model
    def hn_payroll_base_timeline_reschedule_leave(
        self,
        leave_id,
        date_start,
        date_end,
        new_grid_from,
        new_grid_to,
        slot_mode="half",
    ):
        """Reposiciona una ausencia dentro de la ventana visible (índices inclusivos de ranura)."""
        leave = self.browse(int(leave_id))
        leave.check_access("write")
        if not leave.exists():
            raise UserError(self.env._("The time off record was not found."))
        if leave.state in ("cancel", "refuse"):
            raise UserError(
                self.env._("This time off cannot be rescheduled in its current state.")
            )
        if slot_mode not in ("half", "hour"):
            slot_mode = "half"
        start_d = fields.Date.from_string(date_start)
        end_d = fields.Date.from_string(date_end)
        if end_d < start_d:
            start_d, end_d = end_d, start_d
        day_count = (end_d - start_d).days + 1
        user_tz_name = self.env.user.tz or self.env.company.partner_id.tz or "UTC"
        tz = pytz.timezone(user_tz_name)
        vals = tl_grid_to_write_values_leave(
            self.env,
            leave,
            start_d,
            day_count,
            new_grid_from,
            new_grid_to,
            slot_mode,
            tz,
        )
        try:
            leave.write(vals)
        except ValidationError:
            raise
        except UserError:
            raise
        except Exception as err:
            raise UserError(str(err)) from err
        return {"ok": True}
