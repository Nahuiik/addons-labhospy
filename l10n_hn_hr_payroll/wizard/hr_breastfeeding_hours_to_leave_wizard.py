# -*- coding: utf-8 -*-
from datetime import datetime, time

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrBreastfeedingHoursToLeaveWizard(models.TransientModel):
    _name = 'hr.breastfeeding.hours.to.leave.wizard'
    _description = 'Convertir horas de lactancia a días de permiso pagado'

    breastfeeding_id = fields.Many2one(
        'hr.breastfeeding_hours',
        string='Registro de lactancia',
        required=True,
        ondelete='cascade',
    )
    line_ids = fields.Many2many(
        'hr.employee.breastfeeding_hours.line',
        'hr_bf_to_leave_wizard_line_rel',
        'wizard_id',
        'line_id',
        string='Líneas a convertir',
        required=True,
        domain="[('breastfeeding_id', '=', breastfeeding_id)]",
    )
    holiday_status_id = fields.Many2one(
        'hr.leave.type',
        string='Tipo de tiempo personal',
        required=True,
        domain="[('unpaid', '=', False), ('request_unit', '=', 'day')]",
        default=lambda self: self.env.ref(
            'l10n_hn_hr_payroll.leave_type_hn_breastfeeding_paid_days',
            raise_if_not_found=False,
        ),
    )
    hours_per_workday = fields.Float(
        string='Horas por jornada (referencia)',
        default=8.0,
        help='Solo informativo: equivale a dividir las horas legales entre esta jornada para mostrar días teóricos. '
             'La fecha fin del permiso se calcula con el calendario laboral repartiendo las horas efectivamente.',
    )
    info_summary = fields.Html(string='Resumen', compute='_compute_info_summary')

    @api.depends('line_ids', 'line_ids.total_hours', 'hours_per_workday')
    def _compute_info_summary(self):
        for wiz in self:
            parts = []
            hpd = wiz.hours_per_workday or 8.0
            for line in wiz.line_ids:
                th = float(line.total_hours or 0)
                days_th = th / hpd if hpd else 0.0
                parts.append(
                    '<li><strong>%s</strong>: %s h → ~%.2f días teóricos (÷ %s h/día)</li>'
                    % (line.employee_id.display_name, th, days_th, hpd)
                )
            wiz.info_summary = '<ul>%s</ul>' % ''.join(parts) if parts else ''

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        bid = self.env.context.get('default_breastfeeding_id')
        if not bid and self.env.context.get('active_model') == 'hr.breastfeeding.hours':
            bid = self.env.context.get('active_id')
        if bid:
            bf = self.env['hr.breastfeeding_hours'].browse(bid)
            res['breastfeeding_id'] = bf.id
            res['line_ids'] = [(6, 0, bf.line_ids.ids)]
        return res

    @api.onchange('breastfeeding_id')
    def _onchange_breastfeeding_id(self):
        if self.breastfeeding_id:
            self.line_ids = self.breastfeeding_id.line_ids

    def _request_dates_from_hours(self, employee, start_date, hours_float):
        """Calcula request_date_from / request_date_to repartiendo horas en el calendario laboral."""
        calendar = (
            employee.resource_calendar_id
            or employee.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        if not calendar:
            raise UserError(_('No hay calendario laboral para la empleada %s ni para la empresa.') % employee.display_name)
        tzname = employee.tz or employee.company_id.partner_id.tz or self.env.user.tz or 'UTC'
        tz = pytz.timezone(tzname)
        anchor = tz.localize(datetime.combine(start_date, time(7, 0, 0)))
        resource = employee.resource_id if employee.resource_id else None
        end_dt = calendar.plan_hours(float(hours_float), anchor, compute_leaves=False, resource=resource)
        if not end_dt:
            raise UserError(
                _('No se pudo calcular la fecha de fin del permiso para %s con %s horas.')
                % (employee.display_name, hours_float)
            )
        end_local = end_dt.astimezone(tz)
        return start_date, end_local.date()

    def action_create_leaves(self):
        self.ensure_one()
        if self.breastfeeding_id.state != 'draft':
            raise UserError(_('Solo puede usar este asistente con registros en borrador (no combine con validación de conceptos recurrentes).'))
        if not self.line_ids:
            raise UserError(_('Seleccione al menos una línea.'))
        if not self.holiday_status_id or self.holiday_status_id.unpaid:
            raise UserError(_('El tipo de tiempo personal debe ser con goce de sueldo (no marcado como no pagado).'))
        if self.holiday_status_id.request_unit != 'day':
            raise UserError(_('El tipo de tiempo personal debe estar en unidad «día».'))

        Leave = self.env['hr.leave']
        created = self.env['hr.leave']
        skipped = []
        for line in self.line_ids:
            if float(line.total_hours or 0) <= 0:
                raise UserError(
                    _('La empleada %s no tiene horas por ley mayores que cero.') % line.employee_id.display_name
                )
            dup = Leave.search([
                ('l10n_hn_breastfeeding_hours_line_id', '=', line.id),
                ('state', 'not in', ('refuse', 'cancel')),
            ], limit=1)
            if dup:
                skipped.append(line.employee_id.display_name)
                continue
            start = line.start_date or self.breastfeeding_id.date
            if not start:
                raise UserError(_('La línea de %s no tiene fecha de inicio.') % line.employee_id.display_name)
            date_from, date_to = self._request_dates_from_hours(
                line.employee_id, start, float(line.total_hours or 0)
            )
            if date_to < date_from:
                raise UserError(_('Rango de fechas inválido para %s.') % line.employee_id.display_name)
            note = _(
                'Lactancia: conversión de %(hours)s h legales desde registro «%(bf)s» (horas por ley / modalidad días pagados).'
            ) % {
                'hours': line.total_hours,
                'bf': self.breastfeeding_id.display_name,
            }
            created += Leave.create({
                'employee_id': line.employee_id.id,
                'holiday_status_id': self.holiday_status_id.id,
                'request_date_from': date_from,
                'request_date_to': date_to,
                'notes': note,
                'l10n_hn_breastfeeding_hours_line_id': line.id,
            })

        parts = [_('Permisos creados: %s') % len(created)]
        if skipped:
            parts.append(_('Omitidas (ya existía permiso vinculado): %s') % ', '.join(skipped))
        msg = ' '.join(parts)
        if not created and skipped:
            raise UserError(msg)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conversión a días de lactancia'),
                'message': msg,
                'type': 'success' if created else 'warning',
                'sticky': True,
            },
        }
