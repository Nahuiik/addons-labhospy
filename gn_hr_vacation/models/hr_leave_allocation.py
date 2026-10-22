# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    gn_vacation_is_primary = fields.Boolean(
        related='holiday_status_id.gn_vacation_is_primary',
        string='Vacaciones (tipo principal)',
    )

    def _gn_collective_vacation_period_bounds(self):
        """(inicio, fin) del período laboral asociado al derecho, o (False, False) si no aplica."""
        self.ensure_one()
        return (False, False)

    def _gn_collective_vacation_period_overlaps_month(self, month_start, month_end):
        self.ensure_one()
        ps, pe = self._gn_collective_vacation_period_bounds()
        if not ps:
            return True
        if pe:
            return ps <= month_end and pe >= month_start
        return ps <= month_end
