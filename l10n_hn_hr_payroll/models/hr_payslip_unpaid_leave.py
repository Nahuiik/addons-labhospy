# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models

_L10N_HN_UNPAID_WORK_ENTRY_CODE = "LEAVE90"


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_hn_unpaid_work_entry_type_ids(self):
        """Ids de entradas «Sin pagar» según estructura (fallback LEAVE90 estándar)."""
        self.ensure_one()
        struct = self.struct_id
        if struct and struct.unpaid_work_entry_type_ids:
            return set(struct.unpaid_work_entry_type_ids.ids)
        wet = self.env.ref(
            "hr_work_entry.work_entry_type_unpaid_leave", raise_if_not_found=False,
        )
        return {wet.id} if wet else set()

    def _l10n_hn_is_unpaid_work_entry_type(self, work_entry_type):
        """True si la entrada es Sin pagar (LEAVE90 o en unpaid_work_entry_type_ids)."""
        if not work_entry_type:
            return False
        if work_entry_type.code == _L10N_HN_UNPAID_WORK_ENTRY_CODE:
            return True
        return work_entry_type.id in self._l10n_hn_unpaid_work_entry_type_ids()

    def _l10n_hn_leave_type_applies_unpaid_deduction(self, leave_type):
        """Descuenta cualquier ausencia cuyo tipo usa entrada de trabajo Sin pagar.

        Vacaciones Anuales (HN) con «Sin pagar» se tratan igual que permiso sin goce:
        no hay tratamiento especial de «vacación pagada» si el tipo está configurado sin goce.
        """
        if not leave_type:
            return False
        if leave_type.unpaid:
            return True
        wet = leave_type.work_entry_type_id
        return bool(wet and self._l10n_hn_is_unpaid_work_entry_type(wet))

    def _l10n_hn_unpaid_leave_days_from_worked_days(self):
        """Días sin goce desde líneas de días trabajados del recibo."""
        self.ensure_one()
        if not self.struct_id or not self.struct_id.use_worked_day_lines:
            return 0.0
        days = 0.0
        for wd in self.worked_days_line_ids:
            if self._l10n_hn_is_unpaid_work_entry_type(wd.work_entry_type_id):
                days += abs(wd.number_of_days or 0)
        return days

    def _l10n_hn_unpaid_leave_days_from_leaves(self):
        """Suma días de todas las ausencias aprobadas con tipo Sin pagar en el periodo."""
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return 0.0
        period_end = fields.Datetime.to_datetime(self.date_to).replace(
            hour=23, minute=59, second=59,
        )
        period_start = fields.Datetime.to_datetime(self.date_from)
        leaves = self.env["hr.leave"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "in", ("validate", "validate1")),
            ("date_from", "<=", period_end),
            ("date_to", ">=", period_start),
        ])
        total = 0.0
        for leave in leaves:
            if not self._l10n_hn_leave_type_applies_unpaid_deduction(leave.holiday_status_id):
                continue
            total += self._l10n_hn_unpaid_leave_days_in_period(leave)
        return total

    def _l10n_hn_unpaid_leave_days_in_period(self, leave):
        """Días de una ausencia deducible que caen en el periodo del recibo."""
        self.ensure_one()
        leave_start = leave.request_date_from
        if not leave_start and leave.date_from:
            leave_start = leave.date_from.date()
        leave_end = leave.request_date_to
        if not leave_end and leave.date_to:
            leave_end = leave.date_to.date()
        if not leave_start or not leave_end:
            return float(leave.number_of_days or 0)
        if leave_start >= self.date_from and leave_end <= self.date_to:
            return float(leave.number_of_days or 0)
        overlap_start = max(leave_start, self.date_from)
        overlap_end = min(leave_end, self.date_to)
        if overlap_start > overlap_end:
            return 0.0
        total_leave_days = float(leave.number_of_days or 0)
        if total_leave_days <= 0:
            return 0.0
        full_span = (leave_end - leave_start).days + 1
        overlap_span = (overlap_end - overlap_start).days + 1
        if full_span <= 0:
            return total_leave_days
        return round(total_leave_days * overlap_span / full_span, 5)

    def _l10n_hn_unpaid_leave_days(self):
        """Días a descontar: máximo entre WD y suma de ausencias Sin pagar aprobadas."""
        self.ensure_one()
        days_wd = self._l10n_hn_unpaid_leave_days_from_worked_days()
        days_leave = self._l10n_hn_unpaid_leave_days_from_leaves()
        return max(days_wd, days_leave)

    def _l10n_hn_unpaid_leave_daily_rate(self, version=None):
        """Valor día Honduras = salario mensual / 30."""
        self.ensure_one()
        employee = self.employee_id
        ver = version or self.version_id or (employee.current_version_id if employee else False)
        wage_m = (ver.wage if ver else 0.0) or (employee.wage if employee else 0.0)
        return wage_m / 30.0 if wage_m else 0.0

    def _l10n_hn_compute_unpaid_leave_amount(self, version=None, employee=None):
        """Monto deducción UNPAID_LEAVE (negativo). Usado por regla salarial."""
        self.ensure_one()
        days = self._l10n_hn_unpaid_leave_days()
        daily = self._l10n_hn_unpaid_leave_daily_rate(version)
        if not days or not daily:
            return 0.0
        return -round(daily * days, 2)
