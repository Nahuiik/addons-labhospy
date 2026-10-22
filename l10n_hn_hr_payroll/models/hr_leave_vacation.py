# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import base64
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class HrLeave(models.Model):
    _inherit = 'hr.leave'
    _mailing_enabled = True

    hn_constancia_signed = fields.Boolean(
        'Constancia firmada',
        default=False,
        help='Indica si el empleado firmó la constancia de vacaciones',
    )
    hn_sign_date = fields.Date('Fecha de firma constancia')
    hn_signer_name = fields.Char('Nombre firmante')
    hn_signer_id_number = fields.Char('No. identidad firmante')
    hn_signature = fields.Binary('Firma constancia', attachment=False)
    hn_constancia_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Constancia PDF adjunta',
    )
    hn_late_approval_reason = fields.Text(
        'Motivo excepción aprobación tardía',
        help='Obligatorio si se aprueba con menos de los días mínimos configurados (HR Manager)',
    )
    hn_paid_in_advance = fields.Boolean(
        'Pago anticipado registrado',
        default=False,
    )
    hn_paid_date = fields.Date('Fecha de pago')
    hn_paid_amount = fields.Float('Monto pagado')
    hn_payment_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Comprobante de pago',
    )
    hn_substitute_employee_id = fields.Many2one(
        'hr.employee',
        string='Delegado / Suplente',
        help='Empleado que cubre durante la ausencia. Si tiene usuario de Odoo, '
             'podrá aprobar esta solicitud cuando el aprobador habitual esté ausente.',
    )
    hn_substitute_notes = fields.Text('Instrucciones para el suplente')
    hn_vacation_daily_rate = fields.Float(
        compute='_compute_hn_vacation_amount',
        string='Tasa diaria vacaciones',
    )
    hn_vacation_total_amount = fields.Float(
        compute='_compute_hn_vacation_amount',
        string='Monto total vacaciones',
    )
    hn_can_reintegro = fields.Boolean(
        compute='_compute_hn_can_reintegro',
        help='True si las vacaciones están en curso y se puede procesar reintegro',
    )
    hn_advance_days = fields.Float(
        'Días anticipados',
        compute='_compute_hn_advance_days',
        store=True,
        help='Días solicitados que superan el saldo disponible. Requieren aprobación de RRHH.',
    )
    hn_advance_approved = fields.Boolean(
        'Anticipo aprobado',
        default=False,
        help='RRHH aprobó el uso de días anticipados (no ganados aún)',
    )
    hn_advance_approved_by = fields.Many2one(
        'res.users',
        string='Anticipo aprobado por',
    )
    gn_allow_before_anniversary_vacation = fields.Boolean(
        string='Excepción: permitir inicio antes del aniversario',
        default=False,
        groups='hr_holidays.group_hr_holidays_manager',
        help='Solo Responsable de Ausencias. Activar únicamente si se autoriza explícitamente '
             'esta solicitud fuera de la regla de aniversario del tipo de vacaciones.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._gn_sanitize_anniversary_exception_flag_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._gn_sanitize_anniversary_exception_flag_vals(vals)
        return super().write(vals)

    def _gn_sanitize_anniversary_exception_flag_vals(self, vals):
        """Evita que portal/sudo u otros usuarios fuera de RRHH activen la excepción por RPC."""
        if not vals.get('gn_allow_before_anniversary_vacation'):
            return
        if self.env.context.get('gn_allow_anniversary_vacation_override'):
            return
        user = self.env['hr.leave']._gn_leave_security_user()
        if user.has_group('hr_holidays.group_hr_holidays_manager'):
            return
        vals['gn_allow_before_anniversary_vacation'] = False

    @api.model
    def _gn_leave_security_user(self):
        """Usuario contra el que aplicar reglas de portal (create con sudo). Ver gn_leave_real_uid en portal."""
        uid = self.env.context.get('gn_leave_real_uid')
        if uid:
            return self.env['res.users'].browse(uid)
        return self.env.user

    @api.model
    def _gn_normalize_leave_request_start_date(self, request_start):
        if not request_start:
            return None
        if isinstance(request_start, datetime):
            return request_start.date()
        return request_start

    @api.model
    def _gn_assert_anniversary_vacation_start(self, employee, leave_type, request_start, leave=None):
        """Si aplica tipo principal de vacaciones + bloqueo por aniversario y el empleado no tiene excepción, valida la fecha."""
        request_start = self._gn_normalize_leave_request_start_date(request_start)
        if (
            not employee
            or not leave_type
            or not request_start
            or not leave_type.gn_vacation_is_primary
            or not leave_type.gn_vacation_block_before_anniversary
        ):
            return
        if employee.hn_override_anniversary_vacation_block:
            return
        if self.env.context.get('gn_allow_anniversary_vacation_override'):
            return
        if leave is not None and leave.gn_allow_before_anniversary_vacation:
            return
        if not employee.sudo().contract_date_start:
            raise ValidationError(_(
                'El empleado %(name)s debe tener fecha de inicio de contrato para validar el aniversario laboral.',
                name=employee.display_name,
            ))
        min_d = employee.sudo()._hn_min_vacation_start_for_anniversary_rule(request_start)
        if min_d and request_start < min_d:
            raise ValidationError(_(
                'Para el tipo «%(leave)s» no puede iniciar vacaciones antes del %(date)s (aniversario laboral).',
                leave=leave_type.display_name,
                date=fields.Date.to_string(min_d),
            ))

    @api.constrains(
        'request_date_from',
        'date_from',
        'employee_id',
        'holiday_status_id',
        'gn_allow_before_anniversary_vacation',
    )
    def _check_gn_anniversary_vacation_start(self):
        for leave in self:
            if not leave.gn_vacation_is_primary:
                continue
            start = leave.request_date_from or leave.date_from
            start = self.env['hr.leave']._gn_normalize_leave_request_start_date(start)
            self.env['hr.leave']._gn_assert_anniversary_vacation_start(
                leave.employee_id,
                leave.holiday_status_id,
                start,
                leave=leave,
            )

    @api.constrains(
        'holiday_status_id',
        'employee_id',
        'number_of_days',
        'request_date_from',
        'date_from',
        'state',
    )
    def _check_gn_primary_vacation_positive_allocation_balance(self):
        """Refuerzo para tipos principal sin saldo negativo: Odoo puede omitir error si virtual_excess_data queda vacío."""
        for leave in self:
            lt = leave.holiday_status_id
            if (
                not lt
                or not leave.gn_vacation_is_primary
                or not lt.requires_allocation
                or lt.allows_negative
                or leave.state in ('cancel', 'refuse')
            ):
                continue
            if self.env.context.get('gn_allow_primary_vacation_over_allocation'):
                continue
            if self.env['hr.leave']._gn_leave_security_user().has_group('hr_holidays.group_hr_holidays_user'):
                continue
            if not leave.employee_id or not leave.number_of_days:
                continue
            date_from = leave.request_date_from
            if not date_from and leave.date_from:
                date_from = leave.date_from.date()
            if not date_from:
                continue
            alloc_rows = lt.with_context(
                ignored_leave_ids=leave.ids,
            ).get_allocation_data(leave.employee_id, date_from)
            entries = alloc_rows.get(leave.employee_id, [])
            info = next((e[1] for e in entries if e[3] == lt.id), None)
            if not info:
                continue
            remaining = info['virtual_remaining_leaves']
            if float_compare(leave.number_of_days, remaining, precision_digits=2) == 1:
                raise ValidationError(_(
                    'No tiene suficientes días disponibles para «%(leave)s»: solicita %(req)s y dispone de %(rem)s.',
                    leave=lt.display_name,
                    req=leave.number_of_days,
                    rem=remaining,
                ))

    @api.depends('number_of_days', 'virtual_remaining_leaves', 'gn_vacation_is_primary', 'employee_id', 'holiday_status_id')
    def _compute_hn_advance_days(self):
        for leave in self:
            if not leave.gn_vacation_is_primary:
                leave.hn_advance_days = 0
            elif leave.number_of_days and leave.virtual_remaining_leaves is not None:
                leave.hn_advance_days = max(0, leave.number_of_days - leave.virtual_remaining_leaves)
            else:
                leave.hn_advance_days = 0

    @api.depends('employee_id', 'request_date_from', 'number_of_days')
    def _compute_hn_vacation_amount(self):
        for leave in self:
            if leave.gn_vacation_is_primary and leave.employee_id and leave.number_of_days:
                leave.hn_vacation_daily_rate = leave.employee_id._hn_vacation_daily_rate(
                    leave.request_date_from or leave.date_from
                )
                leave.hn_vacation_total_amount = leave.hn_vacation_daily_rate * leave.number_of_days
            else:
                leave.hn_vacation_daily_rate = leave.hn_vacation_total_amount = 0

    @api.depends('state', 'request_date_from', 'request_date_to', 'gn_vacation_is_primary')
    def _compute_hn_can_reintegro(self):
        today = date.today()
        for leave in self:
            leave.hn_can_reintegro = (
                leave.gn_vacation_is_primary
                and leave.state == 'validate'
                and leave.request_date_from
                and leave.request_date_to
                and leave.request_date_from <= today <= leave.request_date_to
            )

    def _has_hn_approval_delegation(self):
        """True si el usuario actual es el delegado/suplente (y tiene user_id) en este leave."""
        self.ensure_one()
        if not self.gn_vacation_is_primary or not self.hn_substitute_employee_id:
            return False
        return self.hn_substitute_employee_id.user_id == self.env.user

    def action_approve(self, check_state=True):
        """Validar reglas de aprobación: menos de X días solo puede RR.HH. (si está activa)."""
        hn_leaves = self.filtered('gn_vacation_is_primary')
        if hn_leaves:
            enforce = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_hn_hr_payroll.enforce_min_days_approval', 'true'
            ).lower() == 'true'
            if enforce:
                min_days = int(self.env['ir.config_parameter'].sudo().get_param(
                    'l10n_hn_hr_payroll.min_days_before_approval', '10'
                ) or 10)
                today = date.today()
                is_hr_manager = self.env.user.has_group('hr_holidays.group_hr_holidays_manager')
                for leave in hn_leaves:
                    date_from = leave.request_date_from
                    if date_from:
                        days_before = (date_from - today).days
                        if days_before < min_days:
                            if not is_hr_manager:
                                raise UserError(
                                    _('Las solicitudes de vacaciones (tipo principal) deben aprobarse con al menos %(min)s días de anticipación. '
                                      'Solo el responsable de RR.HH. puede aprobar con menos días.')
                                    % {'min': min_days}
                                )
        # Warning de solapamiento por departamento (no bloquea) - búsqueda batch
        max_pct = float(self.env['ir.config_parameter'].sudo().get_param(
            'l10n_hn_hr_payroll.max_overlap_pct', '30'
        ) or 0)
        if max_pct > 0:
            leaves_with_dept = hn_leaves.filtered(
                lambda l: l.employee_id and l.employee_id.department_id
            )
            if leaves_with_dept:
                # Total empleados por departamento (una query por dept único)
                total_by_dept = {}
                for dept in leaves_with_dept.mapped('employee_id.department_id'):
                    if dept.id not in total_by_dept:
                        total_by_dept[dept.id] = self.env['hr.employee'].search_count([
                            ('department_id', '=', dept.id),
                            ('active', '=', True),
                        ])
                # Overlapping leaves por departamento (una query por rango de fechas único)
                for leave in leaves_with_dept:
                    dept = leave.employee_id.department_id
                    total_emp = total_by_dept.get(dept.id, 0)
                    if total_emp <= 0:
                        continue
                    overlapping = self.search([
                        ('gn_vacation_is_primary', '=', True),
                        ('state', '=', 'validate'),
                        ('employee_id.department_id', '=', dept.id),
                        ('id', '!=', leave.id),
                        ('request_date_from', '<=', leave.request_date_to),
                        ('request_date_to', '>=', leave.request_date_from),
                    ])
                    total_ausentes = len(overlapping) + 1
                    pct = (total_ausentes / total_emp) * 100
                    if pct > max_pct:
                        leave.message_post(
                            body=f'<p><b>Atención:</b> {total_ausentes} de {total_emp} empleados del departamento '
                            f'{dept.name} estarán ausentes en este período ({pct:.0f}%). '
                            f'El límite configurado es {max_pct:.0f}%.</p>',
                        )
        result = super().action_approve(check_state=check_state)
        # Notificación por email si está activada
        send_email = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_hn_hr_payroll.send_email_on_approve', 'False'
        ) == 'True'
        if send_email:
            validated = self.filtered(lambda l: l.state == 'validate' and l.gn_vacation_is_primary)
            for leave in validated:
                leave._send_hn_approval_email()
        return result

    def _send_hn_approval_email(self):
        """Envía email al empleado cuando se aprueban sus vacaciones (tipo principal)."""
        self.ensure_one()
        if not self.env['ir.mail_server'].gn_hr_outgoing_smtp_configured():
            return
        if not self.employee_id.user_id or not self.employee_id.user_id.email:
            return
        self.message_notify(
            body=f'Sus vacaciones han sido aprobadas. Período: {self.request_date_from} al {self.request_date_to}. Días: {self.number_of_days}.',
            partner_ids=self.employee_id.user_id.partner_id.ids,
            subject='Vacaciones aprobadas',
        )

    @api.model
    def _cron_hn_vacation_reminder(self):
        """Cron diario: recordatorios y alertas para ausencias de tipo principal de vacaciones.
        - Recordatorio 10 días antes
        - Pago pendiente (5 días antes)
        """
        today = date.today()

        # 1) Recordatorio 10 días antes del inicio
        tpl_10day = self.env.ref(
            'l10n_hn_hr_payroll.mail_template_hn_10day_reminder', raise_if_not_found=False
        )
        if tpl_10day:
            target_date = today + timedelta(days=10)
            leaves_10 = self.search([
                ('gn_vacation_is_primary', '=', True),
                ('state', '=', 'validate'),
                ('request_date_from', '=', target_date),
            ])
            for leave in leaves_10:
                try:
                    tpl_10day.send_mail_payroll_tracked(leave.id, force_send=True)
                except Exception:
                    pass

        # 2) Pago pendiente: 5 días antes del inicio y sin pago registrado
        tpl_payment = self.env.ref(
            'l10n_hn_hr_payroll.mail_template_hn_payment_pending', raise_if_not_found=False
        )
        if tpl_payment:
            payment_target = today + timedelta(days=5)
            leaves_pay = self.search([
                ('gn_vacation_is_primary', '=', True),
                ('state', '=', 'validate'),
                ('request_date_from', '=', payment_target),
                ('hn_paid_in_advance', '=', False),
            ])
            for leave in leaves_pay:
                try:
                    tpl_payment.send_mail_payroll_tracked(leave.id, force_send=True)
                except Exception:
                    pass

        # 3) Recordatorio configurable (parámetro reminder_days_before)
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'l10n_hn_hr_payroll.reminder_days_before', '0'
        ))
        if days > 0 and days != 10:
            if self.env['ir.mail_server'].gn_hr_outgoing_smtp_configured():
                custom_target = today + timedelta(days=days)
                leaves_custom = self.search([
                    ('gn_vacation_is_primary', '=', True),
                    ('state', '=', 'validate'),
                    ('request_date_from', '=', custom_target),
                ])
                for leave in leaves_custom:
                    if leave.employee_id.user_id and leave.employee_id.user_id.email:
                        leave.message_notify(
                            body=f'Recordatorio: Sus vacaciones inician en {days} días ({leave.request_date_from} al {leave.request_date_to}).',
                            partner_ids=leave.employee_id.user_id.partner_id.ids,
                            subject='Recordatorio: Inicio de vacaciones',
                        )

    def _gn_finalize_collective_vacation(self, wizard):
        """Extiende el cierre masivo: anticipo aprobado y constancia PDF si aplica."""
        self.ensure_one()
        leave = self
        if (
            leave.gn_vacation_is_primary
            and leave.hn_advance_days
            and leave.hn_advance_days > 0
            and not leave.hn_advance_approved
            and wizard.env.user.has_group('hr_holidays.group_hr_holidays_manager')
        ):
            leave.write({
                'hn_advance_approved': True,
                'hn_advance_approved_by': wizard.env.user.id,
            })
            leave.message_post(
                body=_(
                    '<p>Anticipo de %(days)s días aprobado automáticamente en vacaciones colectivas '
                    'por %(user)s.</p>'
                )
                % {'days': f'{leave.hn_advance_days:.1f}', 'user': wizard.env.user.name},
                **leave.env['hr.leave']._gn_collective_vacation_notification_suppress_kw(),
            )
        if not leave.holiday_status_id.gn_vacation_is_primary:
            return
        if leave.env.context.get('gn_collective_vacation_skip_report_pdf'):
            return
        report = self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_constancia', raise_if_not_found=False)
        if not report:
            return
        try:
            rendered = self.env['ir.actions.report']._render_qweb_pdf(
                report.report_name, res_ids=[leave.id]
            )
            pdf_content = rendered[0]
            if pdf_content:
                fname = f'Constancia_{leave.employee_id.name or "empleado"}_{leave.id}.pdf'
                self.env['ir.attachment'].create({
                    'name': fname,
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'hr.leave',
                    'res_id': leave.id,
                    'mimetype': 'application/pdf',
                })
        except Exception:
            pass

    def action_hn_approve_advance(self):
        """Aprobar días anticipados (requiere HR Manager)."""
        self.ensure_one()
        if not self.gn_vacation_is_primary or not self.hn_advance_days or self.hn_advance_days <= 0:
            return {'type': 'ir.actions.act_window_close'}
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
            raise UserError(_('Solo el responsable de RRHH puede aprobar días anticipados.'))
        self.write({
            'hn_advance_approved': True,
            'hn_advance_approved_by': self.env.user.id,
        })
        self.message_post(
            body=f'<p>Anticipo de {self.hn_advance_days:.1f} días aprobado por {self.env.user.name}.</p>',
        )
        return {'type': 'ir.actions.act_window_close'}

    def action_hn_constancia_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registrar constancia firmada',
            'res_model': 'hn.constancia.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_id': self.id},
        }

    def action_hn_reintegro_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reintegro por urgencia',
            'res_model': 'hn.reintegro.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_id': self.id},
        }

    def action_hn_payment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registrar pago anticipado',
            'res_model': 'hn.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_id': self.id},
        }

    def _get_hn_vacation_document_type(self, code):
        """Obtiene el tipo de documento de vacaciones por código (constancia, solicitud, preaviso)."""
        return self.env['hn.vacation.document.type'].search(
            [('code', '=', code), ('active', '=', True)], limit=1
        )

    def _hn_solicitud_lugar_y_fecha_text(self):
        self.ensure_one()
        from odoo.tools import format_date
        today = fields.Date.context_today(self)
        comp = self.employee_id.company_id if self.employee_id else self.env.company
        if not comp:
            return format_date(self.env, today)
        partner = comp.partner_id
        loc = (partner.city or (partner.state_id.name if partner.state_id else '') or comp.name or '').strip()
        dtxt = format_date(self.env, today)
        return f'{loc}, {dtxt}' if loc else dtxt

    def _hn_solicitud_reintegracion_date_display(self):
        self.ensure_one()
        if not self.request_date_to:
            return ''
        from odoo.tools import format_date
        return format_date(self.env, self.request_date_to + timedelta(days=1))

    def _hn_solicitud_puesto_area_text(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return ''
        bits = []
        if emp.job_id and emp.job_id.name:
            bits.append(emp.job_id.name)
        if emp.department_id and emp.department_id.name:
            bits.append(emp.department_id.name)
        return ' / '.join(bits)

    def action_print_constancia(self):
        self.ensure_one()
        return self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_constancia').report_action(self)

    def action_print_solicitud(self):
        self.ensure_one()
        return self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_solicitud').report_action(self)

    def action_print_preaviso(self):
        self.ensure_one()
        return self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_preaviso').report_action(self)

    def action_send_preaviso_email(self):
        """Envía el preaviso por email al empleado con PDF adjunto."""
        self.ensure_one()
        template = self.env.ref('l10n_hn_hr_payroll.mail_template_hn_approved', raise_if_not_found=False)
        if not template or not self.employee_id:
            return {'type': 'ir.actions.act_window_close'}
        partner = (self.employee_id.user_id or self.employee_id).partner_id
        if not partner or not partner.email:
            return {'type': 'ir.actions.act_window_close'}
        attachment_ids = []
        report = self.env.ref('l10n_hn_hr_payroll.action_report_hn_vacation_preaviso', raise_if_not_found=False)
        if report:
            try:
                rendered = self.env['ir.actions.report']._render_qweb_pdf(
                    report.report_name, res_ids=[self.id]
                )
                pdf_content = rendered[0]
                if pdf_content:
                    att = self.env['ir.attachment'].create({
                        'name': f'Preaviso_{self.employee_id.name}_{self.id}.pdf',
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content),
                        'res_model': 'hr.leave',
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids = [att.id]
            except Exception:
                pass
        template.with_context(attachment_ids=attachment_ids).send_mail_payroll_tracked(
            self.id, force_send=True, email_values={'attachment_ids': [(6, 0, attachment_ids)]}
        )
        return {'type': 'ir.actions.act_window_close'}

    def _get_next_states_by_state(self):
        """Extiende para delegación: el delegado tiene los mismos estados que el manager."""
        result = super()._get_next_states_by_state()
        if not self.gn_vacation_is_primary:
            return result
        is_delegatee = self._has_hn_approval_delegation()
        if is_delegatee:
            is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
            is_time_off_manager = self.employee_id.leave_manager_id == self.env.user
            if not is_officer and not is_time_off_manager:
                validation_type = self.validation_type
                if validation_type != 'hr':
                    result['confirm'].add('refuse')
                    result['validate'].add('refuse')
                if validation_type == 'both':
                    result['confirm'].add('validate1')
                    result['validate1'].add('refuse')
                elif validation_type == 'manager':
                    result['confirm'].add('validate')
                    result['refuse'].add('validate')
                elif validation_type == 'hr':
                    result['confirm'].update({'validate', 'refuse'})
                    result['validate1'].update({'confirm', 'validate', 'refuse'})
                    result['validate'].update({'confirm', 'refuse'})
                    result['refuse'].update({'confirm', 'validate'})
                    result['cancel'].update({'confirm', 'validate', 'refuse'})
        return result

    def _check_approval_update(self, state, raise_if_not_possible=True):
        """Extiende para delegación: el delegado puede aprobar como el manager."""
        if self.env.is_superuser():
            return True
        for holiday in self:
            if holiday.gn_vacation_is_primary and holiday._has_hn_approval_delegation():
                is_time_off_manager = holiday.employee_id.leave_manager_id == self.env.user
                is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
                if not is_time_off_manager and not is_officer:
                    dict_all = holiday._get_next_states_by_state()
                    if state in dict_all.get(holiday.state, {}):
                        try:
                            holiday.check_access('write')
                        except UserError:
                            if raise_if_not_possible:
                                raise
                            return False
                        continue
        return super()._check_approval_update(state, raise_if_not_possible=raise_if_not_possible)
