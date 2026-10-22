# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    gn_vacation_is_primary = fields.Boolean(
        string='Tipo principal de vacaciones anuales',
        default=False,
        help='Marca el tipo de ausencia usado como vacaciones anuales con gestión ampliada: '
             'asignaciones, reglas de saldo, documentos, aprobaciones y automatizaciones asociadas.',
    )
    # Vistas heredadas / Studio / xmlids antiguos de gn_hn_hr_vacation aún pueden usar este nombre.
    is_hn_vacation = fields.Boolean(
        related='gn_vacation_is_primary',
        readonly=False,
        string='Vacaciones HN (compat.)',
        help='Alias histórico del campo «Tipo principal de vacaciones anuales» (gn_vacation_is_primary).',
    )
    gn_vacation_block_before_anniversary = fields.Boolean(
        string='Impedir inicio antes del aniversario laboral',
        default=False,
        help='Si está activo, no puede iniciarse esta ausencia antes del aniversario laboral correspondiente '
             '(primer año completado o aniversario del año de la fecha solicitada). '
             'Excepciones explícitas: casilla en la solicitud (solo Responsable de Ausencias), '
             'contexto técnico gn_allow_anniversary_vacation_override (importaciones o procesos masivos), '
             'o «Omitir bloqueo por aniversario» en la ficha del empleado.',
    )
    hn_block_vacation_before_anniversary = fields.Boolean(
        related='gn_vacation_block_before_anniversary',
        readonly=False,
        string='Bloqueo antes aniversario (compat.)',
        help='Alias histórico de «Impedir inicio antes del aniversario laboral» (gn_vacation_block_before_anniversary).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('gn_vacation_is_primary'):
                vals['gn_vacation_block_before_anniversary'] = False
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('gn_vacation_is_primary') is False:
            vals = dict(vals)
            vals['gn_vacation_block_before_anniversary'] = False
        return super().write(vals)

    @api.constrains('allows_negative', 'max_allowed_negative', 'gn_vacation_is_primary')
    def _check_gn_vacation_negative_cap(self):
        for lt in self:
            if lt.gn_vacation_is_primary and lt.allows_negative and lt.max_allowed_negative <= 0:
                raise ValidationError(
                    _('Si activa «Permitir saldo negativo» en el tipo principal de vacaciones, debe indicar '
                      'un «Máximo déficit» mayor que 0 (días de anticipo permitidos).')
                )

    @api.model
    def gn_primary_vacation_leave_type(self, company=None):
        """Tipo principal de vacaciones para una compañía (multi-compañía / multi-país).

        Prioriza coincidencia de país (`country_id` del tipo = país de la compañía); si no hay país en la
        compañía, admite tipos sin país. Respeta alcance por `company_id` del tipo (global o misma compañía).
        """
        LeaveType = self.env["hr.leave.type"]
        company = company or self.env.company
        if not company:
            return LeaveType.search([("gn_vacation_is_primary", "=", True)], limit=1)

        comp_scope = [
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]
        country = company.country_id
        if country:
            lt = LeaveType.search(
                [("gn_vacation_is_primary", "=", True), ("country_id", "=", country.id)] + comp_scope,
                limit=1,
                order="id asc",
            )
            if lt:
                return lt

        return LeaveType.search(
            [("gn_vacation_is_primary", "=", True), ("country_id", "=", False)] + comp_scope,
            limit=1,
            order="id asc",
        )
