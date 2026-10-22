# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

import calendar
from datetime import datetime, timedelta

from pytz import UTC, timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain

COLLECTIVE_LEAVE_BATCH_FLUSH = 30
COLLECTIVE_LEAVE_COMMIT_EVERY = 25


class GnCollectiveVacationPreviewLine(models.TransientModel):
    _name = 'gn.collective.vacation.preview.line'
    _description = 'Vista previa vacaciones colectivas'

    wizard_id = fields.Many2one('gn.collective.vacation.wizard', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee')
    current_balance = fields.Float('Saldo actual')
    days_requested = fields.Float('Días solicitados')
    resulting_balance = fields.Float('Saldo resultante')
    status = fields.Selection([
        ('ok', 'OK'),
        ('advance', 'Anticipo (saldo insuficiente)'),
        ('no_balance', 'Sin saldo'),
        ('no_allocation', 'Sin asignación'),
    ], string='Estado')


class GnCollectiveVacationWizard(models.TransientModel):
    _name = 'gn.collective.vacation.wizard'
    _inherit = ['hr.mixin']
    _description = 'Vacaciones colectivas'

    def _get_employee_domain(self):
        cid = self.company_id.id if self.company_id else self.env.company.id
        domain = Domain([('company_id', '=', cid)])
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            domain &= Domain(['|', ('leave_manager_id', '=', self.env.user.id), ('user_id', '=', self.env.user.id)])
        return domain

    name = fields.Char(
        string='Descripción',
        default='Vacaciones colectivas',
    )
    holiday_status_id = fields.Many2one(
        'hr.leave.type',
        string='Tipo de ausencia',
        required=True,
        domain="[('gn_vacation_is_primary', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    allocation_mode = fields.Selection([
        ('employee', 'Por empleado'),
        ('company', 'Toda la compañía'),
        ('department', 'Por departamento'),
        ('category', 'Por etiqueta'),
    ], string='Modo', required=True, default='employee',
       help='Toda la compañía: todos los empleados de la compañía seleccionada. '
            'Por departamento: elija departamentos o deje vacío para incluir a toda la compañía.')
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        domain=lambda self: self._get_employee_domain(),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
    )
    department_id = fields.Many2one('hr.department')
    department_ids = fields.Many2many(
        'hr.department',
        'gn_collective_vacation_wizard_dept_rel',
        string='Departamentos',
        help='Seleccione departamentos. Vacío = toda la compañía elegida arriba.',
    )
    category_id = fields.Many2one('hr.employee.category', string='Etiqueta')
    date_from = fields.Date('Fecha inicio', required=True)
    date_to = fields.Date('Fecha fin', required=True)
    reason = fields.Text('Motivo', help='Ej.: Cierre fin de año, Semana Santa')
    discount_from_balance = fields.Boolean(
        'Descontar del saldo de vacaciones',
        default=True,
        help='Si está activo, la vista previa muestra el saldo y empleados en anticipo. '
             'La generación intenta crear la ausencia con asignación vigente; '
             'déficit o anticipo lo aplica la validación de Odoo y las reglas del tipo de ausencia.',
    )
    only_employed_in_vacation_period = fields.Boolean(
        string='Solo quien ya tenía contrato en el período',
        default=True,
        help='Excluye empleados que para las fechas de la vacación colectiva no tenían aún contrato '
             'vigente o ya no tenían relación (útil al cargar vacaciones de fechas pasadas).',
    )
    exclude_zero_balance_in_start_month = fields.Boolean(
        string='Excluir sin saldo en el mes de inicio',
        default=True,
        help='Si está activo y el tipo es vacación principal, no incluye empleados cuyo saldo remanente '
             'de asignaciones de vacaciones (período laboral que solapa el mes de la fecha inicio) '
             'sea cero.',
    )
    preview_line_ids = fields.One2many(
        'gn.collective.vacation.preview.line',
        'wizard_id',
        string='Vista previa',
    )

    def _get_employees_from_allocation_mode(self):
        self.ensure_one()
        if self.allocation_mode == 'employee':
            employees = self.employee_ids or self.env['hr.employee'].search(self._get_employee_domain())
        elif self.allocation_mode == 'category':
            employees = self.category_id.employee_ids.filtered(
                lambda e: e.company_id == self.company_id
            )
        elif self.allocation_mode == 'company':
            employees = self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])
        elif self.allocation_mode == 'department':
            dept_ids = self.department_ids.ids if self.department_ids else []
            if not dept_ids and self.department_id:
                dept_ids = [self.department_id.id]
            if dept_ids:
                employees = self.env['hr.employee'].search([
                    ('department_id', 'in', dept_ids),
                    ('company_id', '=', self.company_id.id),
                ])
            else:
                employees = self.env['hr.employee'].search([
                    ('company_id', '=', self.company_id.id),
                ])
        else:
            employees = self.env['hr.employee']
        employees = self._filter_employees_contract_overlap(employees)
        return self._filter_employees_primary_vacation_balance_month(employees)

    def _get_primary_vacation_balance_for_start_month(self, employee):
        self.ensure_one()
        ref = self.date_from
        if not ref:
            return 0.0
        month_start = ref.replace(day=1)
        last_d = calendar.monthrange(ref.year, ref.month)[1]
        month_end = ref.replace(day=last_d)
        dom = [
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('gn_vacation_is_primary', '=', True),
        ]
        if self.holiday_status_id:
            dom.append(('holiday_status_id', '=', self.holiday_status_id.id))
        allocations = self.env['hr.leave.allocation'].sudo().search(dom)
        total = 0.0
        for a in allocations:
            if a._gn_collective_vacation_period_overlaps_month(month_start, month_end):
                total += (a.number_of_days or 0.0) - (a.leaves_taken or 0.0)
        return total

    def _filter_employees_primary_vacation_balance_month(self, employees):
        self.ensure_one()
        if (
            not self.exclude_zero_balance_in_start_month
            or not self.date_from
            or not employees
            or not self.holiday_status_id
            or not self.holiday_status_id.gn_vacation_is_primary
        ):
            return employees
        kept = self.env['hr.employee']
        for emp in employees:
            if self._get_primary_vacation_balance_for_start_month(emp) > 1e-9:
                kept |= emp
        return kept

    def _filter_employees_contract_overlap(self, employees):
        self.ensure_one()
        if (
            not self.only_employed_in_vacation_period
            or not self.date_from
            or not self.date_to
            or not employees
        ):
            return employees
        date_f, date_t = self.date_from, self.date_to
        kept = self.env['hr.employee']
        for emp in employees:
            overlap = emp._get_versions_with_contract_overlap_with_period(date_f, date_t)
            if overlap:
                kept |= emp
        return kept

    def _prepare_leave_values(self, employees, date_from_tz, date_to_tz):
        self.ensure_one()
        work_days_data = employees.sudo()._get_work_days_data_batch(date_from_tz, date_to_tz)
        validated = self.env.user.has_group('hr_holidays.group_hr_holidays_user') or self.holiday_status_id.leave_validation_type == 'no_validation'
        return [{
            'name': self.name,
            'holiday_status_id': self.holiday_status_id.id,
            'date_from': date_from_tz,
            'date_to': date_to_tz,
            'request_date_from': self.date_from,
            'request_date_to': self.date_to,
            'number_of_days': work_days_data[employee.id]['days'],
            'employee_id': employee.id,
            'state': 'validate' if validated else 'confirm',
        } for employee in employees if work_days_data[employee.id]['days']]

    def _get_primary_vacation_balance(self, employee):
        allocations = self.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('gn_vacation_is_primary', '=', True),
        ])
        initial = employee._gn_collective_vacation_initial_adjustment()
        return sum(a.number_of_days - a.leaves_taken for a in allocations) - initial

    def _balance_covers_request(self, balance, days_requested):
        self.ensure_one()
        lt = self.holiday_status_id
        if days_requested <= 1e-9:
            return True
        if balance + 1e-9 >= days_requested:
            return True
        if lt and lt.allows_negative and lt.max_allowed_negative:
            return (days_requested - balance) <= float(lt.max_allowed_negative) + 1e-9
        return False

    def _has_primary_vacation_allocation(self, employee, holiday_status_id=None):
        emp_ids = employee.ids
        if not emp_ids:
            return False
        status = holiday_status_id or self.holiday_status_id
        Allocation = self.env['hr.leave.allocation'].sudo()
        if status:
            if Allocation.search_count([
                ('employee_id', 'in', emp_ids),
                ('state', '=', 'validate'),
                ('holiday_status_id', '=', status.id),
            ]):
                return True
        return bool(Allocation.search_count([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'validate'),
            ('gn_vacation_is_primary', '=', True),
        ]))

    def _collective_leave_create_context(self):
        return {
            'tracking_disable': True,
            'mail_activity_automation_skip': True,
            'leave_fast_create': True,
            'no_calendar_sync': True,
            'leave_skip_state_check': True,
            'leave_compute_date_from_to': True,
            'gn_collective_vacation_skip_report_pdf': True,
            # RRHH masivo: puede incluir fechas fuera de la regla de aniversario por decisión explícita.
            'gn_allow_anniversary_vacation_override': True,
            # No enviar correos por cada línea (message_post / seguidores del chatter).
            'gn_collective_vacation_no_mail': True,
        }

    def _format_collective_leave_error(self, exc):
        if isinstance(exc, (UserError, ValidationError, AccessError)):
            return exc.args[0] if exc.args else str(exc)
        return str(exc)

    def _post_reason_on_leave(self, leave):
        if self.reason:
            leave.message_post(
                body=f'<p>Vacación colectiva — {self.reason}</p>',
                message_type='notification',
                **self.env['hr.leave']._gn_collective_vacation_notification_suppress_kw(),
            )

    def _finalize_single_collective_leave(self, leave):
        self.ensure_one()
        self._post_reason_on_leave(leave)
        leave._gn_finalize_collective_vacation(self)

    def _open_collective_vacation_result(self, line_commands, report_title=None, report_note=None):
        self.ensure_one()
        title = report_title if report_title is not None else (self.name or _('Vacaciones colectivas'))
        if report_note is None:
            report_note = _(
                'Tipo: %(t)s · Fechas: %(df)s → %(dt)s',
                t=self.holiday_status_id.display_name if self.holiday_status_id else '',
                df=self.date_from or '',
                dt=self.date_to or '',
            )
        wiz = self.env['gn.collective.vacation.result.wizard'].create({
            'name': title,
            'source_wizard_note': report_note,
            'line_ids': line_commands,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resultado vacaciones colectivas'),
            'res_model': 'gn.collective.vacation.result.wizard',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_preview(self):
        self.ensure_one()
        employees = self._get_employees_from_allocation_mode()
        if not employees:
            raise UserError(_('No hay empleados.'))
        tz = timezone(self.company_id.resource_calendar_id.tz or self.env.user.tz or 'UTC')
        date_from_tz = tz.localize(datetime.combine(self.date_from, datetime.min.time())).astimezone(UTC).replace(tzinfo=None)
        date_to_tz = tz.localize(datetime.combine(self.date_to, datetime.max.time())).astimezone(UTC).replace(tzinfo=None)
        work_days_data = employees.sudo()._get_work_days_data_batch(date_from_tz, date_to_tz)
        lines = []
        for emp in employees:
            days = work_days_data.get(emp.id, {}).get('days', 0) or 0
            if days <= 0:
                continue
            has_allocation = self._has_primary_vacation_allocation(emp) if self.holiday_status_id.gn_vacation_is_primary else True
            if not has_allocation:
                status = 'no_allocation'
                balance = 0.0
            else:
                balance = self._get_primary_vacation_balance(emp) if self.discount_from_balance else 999
                if not self.discount_from_balance:
                    status = 'ok'
                elif self._balance_covers_request(balance, days):
                    status = 'ok'
                elif self.holiday_status_id.gn_vacation_is_primary:
                    status = 'advance'
                else:
                    status = 'no_balance'
            lines.append((0, 0, {
                'employee_id': emp.id,
                'current_balance': balance,
                'days_requested': days,
                'resulting_balance': balance - days if (self.discount_from_balance and has_allocation) else balance,
                'status': status,
            }))
        self.preview_line_ids = [(5, 0, 0)] + lines
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_generate(self):
        self.ensure_one()
        employees = self._get_employees_from_allocation_mode()
        if not employees:
            raise UserError(_('No hay empleados para generar las solicitudes.'))

        tz = timezone(self.company_id.resource_calendar_id.tz or self.env.user.tz or 'UTC')
        date_from_tz = tz.localize(datetime.combine(self.date_from, datetime.min.time())).astimezone(UTC).replace(tzinfo=None)
        date_to_tz = tz.localize(datetime.combine(self.date_to, datetime.max.time())).astimezone(UTC).replace(tzinfo=None)

        conflicting = self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
            leave_fast_create=True,
        ).search([
            ('date_from', '<=', date_to_tz),
            ('date_to', '>', date_from_tz),
            ('state', 'not in', ['cancel', 'refuse']),
            ('employee_id', 'in', employees.ids),
        ])
        if conflicting:
            hourly = conflicting.filtered(lambda l: l.leave_type_request_unit == 'hour')
            if hourly:
                raise UserError(
                    _('Algunos empleados tienen solicitudes por horas que se solapan. '
                      'No se puede ajustar automáticamente.')
                )
            one_day = conflicting.filtered(lambda l: l.request_date_from == l.request_date_to)
            one_day.action_refuse()
            (conflicting - one_day)._split_leaves(self.date_from, self.date_to + timedelta(days=1))

        vals_list = self._prepare_leave_values(employees, date_from_tz, date_to_tz)
        pre_exclusions = []
        if self.discount_from_balance and self.holiday_status_id.gn_vacation_is_primary:
            filtered_vals = []
            for v in vals_list:
                emp = self.env['hr.employee'].browse(v['employee_id'])
                days = v['number_of_days']
                if not self._has_primary_vacation_allocation(emp):
                    pre_exclusions.append({
                        'employee_id': emp.id,
                        'number_of_days': days,
                        'error_message': _('Sin asignación de vacaciones validada.'),
                    })
                    continue
                filtered_vals.append(v)
            vals_list = filtered_vals

        line_commands = [
            (0, 0, {
                'employee_id': row['employee_id'],
                'state': 'error',
                'number_of_days': row['number_of_days'],
                'error_message': row['error_message'],
            })
            for row in pre_exclusions
        ]

        if not vals_list and not line_commands:
            raise UserError(_('No hay empleados elegibles o no hay días laborables en el período.'))

        report_title = self.name or _('Vacaciones colectivas')
        report_note = _(
            'Tipo: %(t)s · Fechas: %(df)s → %(dt)s',
            t=self.holiday_status_id.display_name if self.holiday_status_id else '',
            df=self.date_from or '',
            dt=self.date_to or '',
        )
        wizard_id = self.id
        wizard = self

        ctx = self._collective_leave_create_context()
        Leave = wizard.env['hr.leave'].with_context(**ctx)
        for idx, vals in enumerate(vals_list):
            emp = wizard.env['hr.employee'].browse(vals['employee_id'])
            try:
                with wizard.env.cr.savepoint(flush=True):
                    leave = Leave.create([vals])
                    leave._validate_leave_request()
                    wizard._finalize_single_collective_leave(leave)
                    line_commands.append((0, 0, {
                        'employee_id': emp.id,
                        'state': 'ok',
                        'leave_id': leave.id,
                        'number_of_days': vals.get('number_of_days'),
                    }))
            except Exception as err:
                line_commands.append((0, 0, {
                    'employee_id': emp.id,
                    'state': 'error',
                    'number_of_days': vals.get('number_of_days'),
                    'error_message': wizard._format_collective_leave_error(err),
                }))
            if COLLECTIVE_LEAVE_BATCH_FLUSH and (idx + 1) % COLLECTIVE_LEAVE_BATCH_FLUSH == 0:
                wizard.env.flush_all()
            if (
                COLLECTIVE_LEAVE_COMMIT_EVERY
                and (idx + 1) % COLLECTIVE_LEAVE_COMMIT_EVERY == 0
                and (idx + 1) < len(vals_list)
            ):
                wizard.env.flush_all()
                wizard.env.cr.commit()
                wizard.env.clear()
                wizard = wizard.env['gn.collective.vacation.wizard'].browse(wizard_id)
                Leave = wizard.env['hr.leave'].with_context(**wizard._collective_leave_create_context())

        return wizard._open_collective_vacation_result(
            line_commands, report_title=report_title, report_note=report_note,
        )

    @api.onchange('employee_ids', 'holiday_status_id')
    def _onchange_employee_ids_warning(self):
        if not self.employee_ids or not self.holiday_status_id or not self.holiday_status_id.gn_vacation_is_primary:
            return
        employees_to_check = [e for e in self.employee_ids if e.ids]
        without_allocation = [e for e in employees_to_check if not self._has_primary_vacation_allocation(e)]
        if without_allocation:
            names = ', '.join(e.name for e in without_allocation[:5])
            if len(without_allocation) > 5:
                names += f' y {len(without_allocation) - 5} más'
            return {
                'warning': {
                    'title': _('Empleados sin asignación'),
                    'message': _(
                        'Los siguientes empleados no tienen asignación de vacaciones: %(names)s. '
                        'Genere asignaciones primero o no se les descontará del saldo.',
                        names=names,
                    ),
                },
            }

    @api.constrains('allocation_mode')
    def _check_allocation_mode(self):
        is_manager = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
        for record in self:
            if record.allocation_mode != 'employee' and not is_manager:
                raise AccessError(_('Solo puede usar el modo «Por empleado» como responsable de tiempo libre.'))
