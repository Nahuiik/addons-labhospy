# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Incapacidad IHSS Honduras: días 1-3 patrono, día 4+ IHSS (por DÍAS CALENDARIO)
#
# Regla legal (Reglamento Incapacidad Temporal IHSS 2020): la incapacidad corre continua
# por calendario; el subsidio aplica por día completo incluyendo sábados, domingos y feriados.
# El "día 1..N" del caso se cuenta por calendario, aunque Odoo solo genere work entries
# en días con jornada laboral.

import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # Escalares para modifiers OWL (Many2one parcial en cliente no expone .country_id.code).
    l10n_hn_holiday_country_code = fields.Char(
        related='holiday_status_id.country_id.code',
        string='Código país (tipo ausencia)',
        readonly=True,
    )
    l10n_hn_holiday_is_ihss_incapacity = fields.Boolean(
        related='holiday_status_id.is_ihss_incapacity',
        string='Tipo es incapacidad IHSS',
        readonly=True,
    )

    # --- Campos IHSS Incapacidad (días calendario) ---
    hn_incap_case_key = fields.Char(
        string='Clave caso incapacidad',
        readonly=True,
        help='Identificador único del caso de incapacidad (para continuidad).',
    )
    hn_incap_day_index_start = fields.Integer(
        string='Día caso (inicio)',
        readonly=True,
        help='Índice del primer día calendario de esta leave dentro del caso (1-based).',
    )
    hn_incap_day_index_end = fields.Integer(
        string='Día caso (fin)',
        readonly=True,
        help='Índice del último día calendario de esta leave dentro del caso.',
    )
    hn_incap_calendar_days_total = fields.Integer(
        string='Días calendario total',
        readonly=True,
        help='Total de días calendario de la incapacidad en esta leave.',
    )
    hn_incap_calendar_days_patrono = fields.Integer(
        string='Días calendario (Patrono)',
        readonly=True,
        help='Días calendario que corresponden al tramo patrono (días 1-3 del caso).',
    )
    hn_incap_calendar_days_ihss = fields.Integer(
        string='Días calendario (IHSS)',
        readonly=True,
        help='Días calendario que corresponden al tramo IHSS (día 4+ del caso).',
    )
    l10n_hn_breastfeeding_hours_line_id = fields.Many2one(
        'hr.employee.breastfeeding_hours.line',
        string='Línea horas lactancia (origen)',
        copy=False,
        ondelete='set null',
        index=True,
        help='Si el permiso se generó desde el asistente de conversión horas → días.',
    )

    _l10n_hn_bf_line_unique = models.Constraint(
        'unique(l10n_hn_breastfeeding_hours_line_id)',
        'Ya existe un permiso de tiempo vinculado a esta línea de lactancia.',
    )

    def _compute_hn_incap_fields(self):
        """
        Calcula los campos de incapacidad IHSS para leaves con tipo is_ihss_incapacity.
        - Determina continuidad (mismo caso si la última incapacidad termina el día anterior).
        - day_index_start: 1 si nuevo caso, o last_end + 1 si continuación.
        - Itera por fechas calendario y clasifica cada día como patrono (<=3) o IHSS (>=4).
        """
        for leave in self:
            if not leave.holiday_status_id.is_ihss_incapacity:
                leave.hn_incap_case_key = False
                leave.hn_incap_day_index_start = 0
                leave.hn_incap_day_index_end = 0
                leave.hn_incap_calendar_days_total = 0
                leave.hn_incap_calendar_days_patrono = 0
                leave.hn_incap_calendar_days_ihss = 0
                continue

            date_from = fields.Date.to_date(leave.date_from)
            date_to = fields.Date.to_date(leave.date_to)
            if not date_from or not date_to or date_from > date_to:
                leave.hn_incap_day_index_start = 0
                leave.hn_incap_day_index_end = 0
                leave.hn_incap_calendar_days_total = 0
                leave.hn_incap_calendar_days_patrono = 0
                leave.hn_incap_calendar_days_ihss = 0
                continue

            # Buscar última incapacidad aprobada del mismo empleado y tipo que termine
            # exactamente el día anterior (sin hueco) => misma caso
            day_before_start = date_from - timedelta(days=1)
            last_incap = self.env['hr.leave'].sudo().search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id.is_ihss_incapacity', '=', True),
                ('id', '!=', leave.id),
                ('state', 'in', ('validate', 'validate1')),
                ('hn_incap_day_index_end', '>', 0),
            ], order='date_to desc', limit=1)

            day_index_start = 1
            case_key = str(uuid.uuid4())

            if last_incap:
                last_date_to = fields.Date.to_date(last_incap.date_to)
                if last_date_to == day_before_start:
                    # Continuación del mismo caso
                    day_index_start = last_incap.hn_incap_day_index_end + 1
                    case_key = last_incap.hn_incap_case_key or case_key

            leave.hn_incap_case_key = case_key
            leave.hn_incap_day_index_start = day_index_start

            # Iterar por fechas calendario
            days_patrono = 0
            days_ihss = 0
            current = date_from
            i = 0
            while current <= date_to:
                case_day = day_index_start + i
                if case_day <= 3:
                    days_patrono += 1
                else:
                    days_ihss += 1
                i += 1
                current += timedelta(days=1)

            leave.hn_incap_day_index_end = day_index_start + i - 1
            leave.hn_incap_calendar_days_total = i
            leave.hn_incap_calendar_days_patrono = days_patrono
            leave.hn_incap_calendar_days_ihss = days_ihss

    def get_case_day_index_for_date(self, calendar_date):
        """
        Retorna el case_day_index (1-based) para una fecha calendario.
        Usado al generar work entries: el tipo (Patrono vs IHSS) se decide por este índice.
        - Días 1-3 => Patrono
        - Días >= 4 => IHSS
        """
        self.ensure_one()
        if not self.holiday_status_id.is_ihss_incapacity or not self.hn_incap_day_index_start:
            return 0
        d = fields.Date.to_date(calendar_date)
        leave_from = fields.Date.to_date(self.date_from)
        if d < leave_from:
            return 0
        leave_to = fields.Date.to_date(self.date_to)
        if d > leave_to:
            return 0
        delta = (d - leave_from).days
        return self.hn_incap_day_index_start + delta

    def _check_hn_incap_no_overlap(self):
        """Prohibir traslapes de incapacidades IHSS del mismo empleado."""
        for leave in self:
            if not leave.holiday_status_id.is_ihss_incapacity:
                continue
            date_from = fields.Date.to_date(leave.date_from)
            date_to = fields.Date.to_date(leave.date_to)
            overlapping = self.env['hr.leave'].sudo().search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id.is_ihss_incapacity', '=', True),
                ('id', '!=', leave.id),
                ('state', 'in', ('validate', 'validate1', 'confirm', 'draft')),
                ('date_from', '<=', date_to),
                ('date_to', '>=', date_from),
            ], limit=1)
            if overlapping:
                raise ValidationError(_(
                    'No se permite traslape de incapacidades IHSS. '
                    'El empleado %(employee)s ya tiene una incapacidad aprobada/en curso '
                    'que se traslapa con este período: %(other)s.'
                ) % {
                    'employee': leave.employee_id.name,
                    'other': overlapping.display_name,
                })

    def _validate_leave_request(self):
        """Antes de validar: calcular campos IHSS y verificar no traslape."""
        # Solo para incapacidad IHSS
        incap_leaves = self.filtered(lambda l: l.holiday_status_id.is_ihss_incapacity)
        if incap_leaves:
            incap_leaves._compute_hn_incap_fields()
            incap_leaves._check_hn_incap_no_overlap()
        return super()._validate_leave_request()

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        # Recalcular si se crean en estado validado (poco común pero posible)
        for leave in leaves:
            if leave.holiday_status_id.is_ihss_incapacity and leave.state in ('validate', 'validate1'):
                leave._compute_hn_incap_fields()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        # Si cambian fechas o estado a validado, recalcular
        if any(k in vals for k in ('date_from', 'date_to', 'request_date_from', 'request_date_to', 'state')):
            for leave in self:
                if leave.holiday_status_id.is_ihss_incapacity and leave.state in ('validate', 'validate1'):
                    leave._compute_hn_incap_fields()
        return res
