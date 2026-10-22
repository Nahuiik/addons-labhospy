# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _gn_collective_vacation_initial_adjustment(self):
        """Días a descontar del saldo mostrado en vacaciones colectivas (carga inicial, etc.)."""
        self.ensure_one()
        return 0.0
