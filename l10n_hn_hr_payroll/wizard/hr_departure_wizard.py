# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    departure_specific_reason_id = fields.Many2one(
        'l10n.hn.hr.departure.specific.reason',
        string='Motivo específico',
        help='Motivo detallado de la baja según catálogo de la empresa.',
    )

    include_in_current_payroll = fields.Boolean(
        string='Incluir en nómina de la quincena en curso',
        default=False,
        help='Si el empleado se da de baja a mitad de quincena, marque para incluirlo en la '
             'nómina del período en curso. Solo aplica cuando la fecha de baja cae dentro del período.',
    )
    apply_offboarding_plan = fields.Boolean(
        string='Aplicar plan de offboarding',
        default=True,
        help='Si está marcado y existe un plan de actividad de offboarding configurado para empleados, '
             'se programarán las actividades automáticamente al registrar la baja.',
    )

    def action_register_departure(self):
        # Escribir el flag ANTES de archivar para que el empleado lo tenga al quedar inactivo
        self.employee_ids.write({
            'include_in_current_payroll': self.include_in_current_payroll,
        })
        # Igual que hr.departure.wizard (active_versions): la versión vigente antes
        # del archivado es la que recibe motivo/fecha de baja; escribir ahí el motivo
        # específico evita inconsistencias con version_id/context tras archivar.
        departure_versions = self.employee_ids.mapped('version_id')
        result = super().action_register_departure()
        spec = self.departure_specific_reason_id
        departure_versions.write({
            'departure_specific_reason_id': spec.id if spec else False,
        })

        # Aplicar plan de offboarding si está habilitado
        if self.apply_offboarding_plan and self.employee_ids:
            self._apply_offboarding_plan()

        return result

    def _apply_offboarding_plan(self):
        """Busca un plan de offboarding y lo aplica a los empleados archivados."""
        plan = self.env['mail.activity.plan'].sudo().search([
            ('res_model', '=', 'hr.employee'),
            ('active', '=', True),
            ('template_ids', '!=', False),
            '|',
            ('name', 'ilike', 'offboard'),
            ('name', 'ilike', 'baja'),
        ], limit=1)
        if not plan:
            return

        plan_date = self.departure_date or fields.Date.today()
        for employee in self.employee_ids:
            try:
                scheduler = self.env['mail.activity.schedule'].create({
                    'res_model': 'hr.employee',
                    'res_ids': str([employee.id]),
                    'plan_id': plan.id,
                    'plan_date': plan_date,
                    'plan_on_demand_user_id': self.env.user.id,
                })
                scheduler.action_schedule_plan()
            except Exception as e:
                _logger.warning(
                    'No se pudo aplicar el plan de offboarding "%s" al empleado %s: %s',
                    plan.name, employee.display_name, e
                )
