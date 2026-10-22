# -*- coding: utf-8 -*-
"""Utilidades compartidas para vistas planificadoras de Time Off (CE)."""

from datetime import datetime, time, timedelta

import pytz
from pytz import utc

from odoo import fields
from odoo.exceptions import UserError
from odoo.tools.date_utils import localized


def tl_color_from_index(color_index):
    """Paleta discreta alineada a índices de color habituales en Odoo (0–10)."""
    colors = [
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
    ]
    try:
        idx = int(color_index) % len(colors)
    except (TypeError, ValueError):
        idx = 0
    return colors[idx]


def tl_color_from_leave_type_name(type_name, color_index):
    """Colores tipo referencia Gantt (PTO naranja, enfermedad amarillo, compensatorio azul)."""
    if type_name:
        low = type_name.lower()
        if any(
            k in low
            for k in (
                "paid time",
                "pto",
                "vacation",
                "vacaciones",
                "annual leave",
                "anual",
                "vacacion",
            )
        ):
            return "#e67e22"
        if any(
            k in low
            for k in (
                "sick",
                "sto",
                "enfermedad",
                "incapacidad",
                "medical",
                "médica",
            )
        ):
            return "#f1c40f"
        if any(
            k in low
            for k in (
                "compensator",
                "cto",
                "time in lieu",
                "libre compens",
                "comp time",
            )
        ):
            return "#3498db"
    return tl_color_from_index(color_index)


def tl_day_totals_from_blocks(blocks, day_count, slots_per_day):
    """Por día civil: nº de empleados distintos con bloque intersectando ese día."""
    if day_count <= 0 or slots_per_day < 1:
        return []
    day_totals = [0] * day_count
    for di in range(day_count):
        em_on = set()
        for b in blocks:
            gf = int(b["grid_from"])
            gt = int(b["grid_to"])
            d0 = gf // slots_per_day
            d1 = gt // slots_per_day
            if d0 <= di <= d1:
                em_on.add(b["employee_id"])
        day_totals[di] = len(em_on)
    return day_totals


def tl_badge_from_type_name(leave_type_name):
    """Etiqueta corta tipo siglas a partir del nombre del tipo."""
    if not leave_type_name:
        return "TO"
    cleaned = "".join(c for c in leave_type_name.upper() if c.isalnum() or c.isspace())
    parts = [p for p in cleaned.split() if p]
    if len(parts) >= 2:
        return "".join(p[0] for p in parts[:4])[:4]
    return (parts[0][:3] if parts else "TO")[:4]


def tl_employee_sidebar_hours(employee):
    """Texto tipo «528h»: saldo en horas (días disponibles × horas por día del calendario)."""
    from odoo.addons.resource.models.utils import HOURS_PER_DAY

    cal = employee.resource_calendar_id or employee.company_id.resource_calendar_id
    hpd = float(cal.hours_per_day) if cal and cal.hours_per_day else float(HOURS_PER_DAY)
    raw = (employee.allocation_remaining_display or "").strip().replace(",", ".")
    try:
        days = float(raw or 0)
    except ValueError:
        days = 0.0
    hours = days * hpd
    if hours <= 0:
        return ""
    return "%.0fh" % round(hours)


def tl_nonwork_half_masks(env, employees, day_strings):
    """Por empleado, lista bool de longitud 2×len(day_strings): True = no laborable (celda rayada).

    Inspirado en la lógica de indisponibilidad del Gantt Enterprise (calendario de trabajo).
    """
    user_tz_name = env.user.tz or env.company.partner_id.tz or "UTC"
    tz_user = pytz.timezone(user_tz_name)
    result = {emp.id: [] for emp in employees}
    for emp in employees:
        cal = emp.resource_calendar_id or emp.company_id.resource_calendar_id
        res = emp.resource_id
        cal_tz = pytz.timezone(cal.tz) if cal and cal.tz else tz_user
        for ds in day_strings:
            d = fields.Date.from_string(ds)
            for t0, t1 in (
                (time(0, 0, 0), time(11, 59, 59)),
                (time(12, 0, 0), time(23, 59, 59)),
            ):
                if not cal or not res:
                    result[emp.id].append(d.weekday() >= 5)
                    continue
                start_local = cal_tz.localize(datetime.combine(d, t0))
                end_local = cal_tz.localize(datetime.combine(d, t1))
                start_utc = start_local.astimezone(utc)
                end_utc = end_local.astimezone(utc)
                work = cal._work_intervals_batch(
                    localized(start_utc),
                    localized(end_utc),
                    res,
                    tz=cal_tz,
                )
                result[emp.id].append(not bool(work[res.id]))
    return result


def tl_leave_half_indices(date_from, date_to, start_d, end_d, day_count, tz):
    """Índices inclusivos en una rejilla de medios días (0..2*day_count-1)."""

    def local_dt(dt_val):
        if not dt_val:
            return None
        if dt_val.tzinfo is None:
            dt_val = pytz.UTC.localize(dt_val)
        return dt_val.astimezone(tz)

    def clip_half_index(dt_val, is_end=False):
        loc = local_dt(dt_val)
        if not loc:
            return None
        d = loc.date()
        if d < start_d:
            return 0
        if d > end_d:
            return 2 * day_count - 1
        day_i = (d - start_d).days
        h = loc.hour + loc.minute / 60.0
        if is_end:
            half = 0 if h < 12 or (h == 12 and loc.minute == 0) else 1
        else:
            half = 0 if h < 12 else 1
        idx = day_i * 2 + half
        return max(0, min(2 * day_count - 1, idx))

    n = 2 * day_count
    i0 = clip_half_index(date_from, is_end=False)
    i1 = clip_half_index(date_to, is_end=True)
    if i0 is None:
        i0 = 0
    if i1 is None:
        i1 = n - 1
    if i0 > i1:
        i0, i1 = i1, i0
    return i0, i1


def tl_slots_per_day(slot_mode):
    """Número de ranuras por día: 2 (mañana/tarde) o 24 (horas artificiales para zoom)."""
    return 24 if slot_mode == "hour" else 2


def tl_expand_nonwork_half_to_hour(nonwork_half):
    """Duplica la máscara de medios días a 24 «horas» heredando AM/PM (MVP sin calendario horario fino)."""
    out = []
    for i in range(0, len(nonwork_half), 2):
        am = nonwork_half[i]
        pm = nonwork_half[i + 1] if i + 1 < len(nonwork_half) else am
        out.extend([am] * 12 + [pm] * 12)
    return out


def tl_leave_hour_indices(date_from, date_to, start_d, end_d, day_count, tz):
    """Índices inclusivos en rejilla de 24 ranuras por día (0..24*day_count-1)."""

    def local_dt(dt_val):
        if not dt_val:
            return None
        if dt_val.tzinfo is None:
            dt_val = pytz.UTC.localize(dt_val)
        return dt_val.astimezone(tz)

    n = 24 * day_count

    def clip_start(dt_val):
        loc = local_dt(dt_val)
        if not loc:
            return 0
        d = loc.date()
        if d < start_d:
            return 0
        if d > end_d:
            return n - 1
        di = (d - start_d).days
        return max(0, min(n - 1, di * 24 + loc.hour))

    def clip_end(dt_val):
        loc = local_dt(dt_val)
        if not loc:
            return n - 1
        d = loc.date()
        if d < start_d:
            return 0
        if d > end_d:
            return n - 1
        di = (d - start_d).days
        return max(0, min(n - 1, di * 24 + loc.hour))

    i0 = clip_start(date_from)
    i1 = clip_end(date_to)
    if i0 > i1:
        i0, i1 = i1, i0
    return i0, i1


def tl_leave_slot_indices(date_from, date_to, start_d, end_d, day_count, tz, slot_mode):
    if slot_mode == "hour":
        return tl_leave_hour_indices(date_from, date_to, start_d, end_d, day_count, tz)
    return tl_leave_half_indices(date_from, date_to, start_d, end_d, day_count, tz)


def tl_grid_to_write_values_leave(env, leave, start_d, day_count, i0, i1, slot_mode, tz):
    """Construye vals para ``hr.leave.write`` a partir de índices de ranura en la ventana visible."""
    sp = tl_slots_per_day(slot_mode)
    n = day_count * sp
    i0 = max(0, min(n - 1, int(i0)))
    i1 = max(0, min(n - 1, int(i1)))
    if i0 > i1:
        i0, i1 = i1, i0

    d0 = start_d + timedelta(days=i0 // sp)
    d1 = start_d + timedelta(days=i1 // sp)

    if slot_mode == "hour":
        if not leave.request_unit_hours:
            raise UserError(
                env._(
                    "Hour grid rescheduling only applies to time off types that use hours."
                )
            )
        if d0 != d1:
            raise UserError(
                env._(
                    "Hour grid move is limited to a single calendar day in this version."
                )
            )
        hf = float(i0 % 24)
        ht = float((i1 % 24) + 1)
        if ht > 24:
            ht = 24.0
        return {
            "request_date_from": d0,
            "request_date_to": d1,
            "request_hour_from": hf,
            "request_hour_to": ht,
        }

    # half-day / día completo por defecto
    if leave.request_unit_half:
        return {
            "request_date_from": d0,
            "request_date_to": d1,
            "request_date_from_period": "am" if (i0 % 2) == 0 else "pm",
            "request_date_to_period": "am" if (i1 % 2) == 0 else "pm",
        }

    return {
        "request_date_from": d0,
        "request_date_to": d1,
    }
