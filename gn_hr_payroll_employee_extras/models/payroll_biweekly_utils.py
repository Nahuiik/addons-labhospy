# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3
"""Utilidades de calendario quincenal (1–15 y 16–fin de mes) compartidas por localizaciones HN/SV."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Tuple, Union

PeriodNumber = Union[str, int]


def normalize_period_number(period_number: PeriodNumber) -> str:
    """Devuelve '1' o '2' como str (consistente con Selection Odoo)."""
    return str(period_number)


def biweekly_date_range(year: int, month: int, period_number: PeriodNumber) -> Tuple[date, date]:
    """Rango inclusivo primera/segunda quincena del mes."""
    pn = normalize_period_number(period_number)
    if pn == "1":
        return date(year, month, 1), date(year, month, 15)
    last = monthrange(year, month)[1]
    return date(year, month, 16), date(year, month, last)


def period_number_from_day(day: int) -> str:
    """Inferir quincena a partir del día del mes (1..31)."""
    return "1" if day <= 15 else "2"


def biweekly_start_from_today(today: date) -> date:
    """Inicio de quincena que contiene `today` si no hay período explícito."""
    y, m, d = today.year, today.month, today.day
    if d <= 15:
        return date(y, m, 1)
    return date(y, m, 16)


def biweekly_end_from_start(start: date) -> date:
    """Fin de quincena dado el primer día de esa quincena en el mes."""
    y, m, d = start.year, start.month, start.day
    if d <= 15:
        return date(y, m, 15)
    last = monthrange(y, m)[1]
    return date(y, m, last)


def spanish_month_name(month: int) -> str:
    """Nombre del mes en minúsculas (español), para etiquetas de período."""
    month_names = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }
    return month_names.get(month, "")
