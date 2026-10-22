# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import api, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    @api.model_create_multi
    def create(self, vals_list):
        if 'overtime_deductible' not in self._fields:
            return super().create(vals_list)
        for vals in vals_list:
            vals['overtime_deductible'] = False
        return super().create(vals_list)

    def write(self, vals):
        if 'overtime_deductible' not in self._fields:
            return super().write(vals)
        if 'overtime_deductible' in vals:
            vals = dict(vals)
            vals['overtime_deductible'] = False
        return super().write(vals)
