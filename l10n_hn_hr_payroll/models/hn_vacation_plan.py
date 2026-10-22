# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

"""Extensión HN del plan genérico (`gn_hr_vacation`): acciones acopladas a nómina/cron HN."""

from odoo import models


class GnHnVacationPlanHN(models.Model):
    _inherit = 'gn.hn.vacation.plan'

    def action_run_hn_vacation_allocations(self):
        """Ejecuta en serie los mismos procesos que los cron diarios de vacaciones HN.

        Afecta a todos los empleados elegibles (según contrato y planes asignados), no solo a
        los vinculados a este registro de plan.
        """
        self.ensure_one()
        Employee = self.env['hr.employee']
        Employee._cron_hn_vacation_annual_allocation()
        Employee._cron_hn_vacation_monthly_proportional()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Asignaciones de vacaciones',
                'message': (
                    'Se ejecutaron los procesos de vacaciones: asignaciones en aniversario para planes en modo '
                    'anual, temporales proporcionales si aplica, devengo del primer año (modo anual con '
                    'acumulación mensual opcional), y devengo mensual o diario según la configuración de cada plan.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
