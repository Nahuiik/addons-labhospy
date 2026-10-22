# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    def _reevaluate_leaves(self, time_domain_dict):
        # hr_holidays recalcula hr.leave al crear/editar festivos globales; en bases con
        # ausencias validadas puede fallar por saldos/asignaciones. La sync desde
        # hn.public.holiday / sv.public.holiday no debe reprocesar solicitudes.
        if self.env.context.get('l10n_skip_calendar_leave_reevaluate'):
            return
        return super()._reevaluate_leaves(time_domain_dict)

    hn_public_holiday_id = fields.Many2one(
        'hn.public.holiday',
        string='Festivo HN (origen)',
        ondelete='set null',
        index=True,
        help='Si está definido, este día festivo proviene de la tabla maestra de festivos Honduras.',
    )
