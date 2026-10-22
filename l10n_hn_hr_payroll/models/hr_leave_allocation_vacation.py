# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import api, fields, models


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    hn_vacation_period_start = fields.Date(
        'Inicio período laboral',
        help='Fecha de inicio del período laboral que genera este derecho',
    )
    hn_vacation_period_end = fields.Date(
        'Fin período laboral',
        help='Fecha de fin del período laboral',
    )
    hn_allow_accumulation = fields.Boolean(
        'Permitir acumulación',
        help='Excepción autorizada por HR Manager para acumular más de un período',
    )
    hn_accumulation_reason = fields.Text('Motivo acumulación')
    hn_accumulation_date = fields.Date('Fecha autorización acumulación')
    hn_accumulation_approved_by = fields.Many2one(
        'res.users',
        string='Autorizado por',
    )
    hn_is_monthly_proportional = fields.Boolean(
        'Acumulación mensual proporcional',
        default=False,
        help='Asignación generada por acumulación mensual (empleados con menos de 1 año)',
    )
    hn_vac_payroll_settled_days = fields.Float(
        string='Días liquidados nómina vacaciones',
        default=0.0,
        help='Días de esta asignación ya pagados en efectivo mediante una nómina con estructura de vacaciones HN. '
             'Al confirmar ese recibo se incrementa este valor (FIFO entre asignaciones). '
             'No confundir con “días gozados” (ausencias): cuando alguien toma vacaciones, eso consume el tiempo en '
             'nómina regular según vuestra configuración; aquí solo se controla cuánto del derecho ya se liquidó en '
             'la nómina especial de vacaciones (acumulado = días otorgados − este campo).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Si el plan permite apilar períodos (max_accumulation_periods distinto de 1),
        marcar hn_allow_accumulation automáticamente."""
        for vals in vals_list:
            if 'hn_allow_accumulation' not in vals and vals.get('employee_id') and vals.get('holiday_status_id'):
                leave_type = self.env['hr.leave.type'].browse(vals['holiday_status_id'])
                if leave_type.gn_vacation_is_primary:
                    emp = self.env['hr.employee'].browse(vals['employee_id'])
                    plan = emp.hn_vacation_plan_id or emp._get_default_hn_vacation_plan()
                    if plan and emp._hn_plan_allows_allocation_stack(plan):
                        vals['hn_allow_accumulation'] = True
        return super().create(vals_list)

    def _gn_collective_vacation_period_bounds(self):
        self.ensure_one()
        return (self.hn_vacation_period_start, self.hn_vacation_period_end)
