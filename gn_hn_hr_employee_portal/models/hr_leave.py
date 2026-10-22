# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    gn_portal_submitter_id = fields.Many2one(
        'res.users',
        string='Solicitante portal (jefe)',
        readonly=True,
        index=True,
        copy=False,
        help='Usuario portal que creó la solicitud en nombre del empleado. '
             'Se usa para notificar por correo al aprobar o rechazar.',
    )

    def write(self, vals):
        previous_states = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        if 'state' not in vals:
            return res
        for leave in self:
            if not leave.gn_portal_submitter_id:
                continue
            if leave.state == previous_states.get(leave.id):
                continue
            if leave.state not in ('validate', 'refuse'):
                continue
            if (
                leave.state == 'validate'
                and leave._gn_skip_portal_submitter_mail_use_hn_approve_flow()
            ):
                continue
            leave._gn_mail_notify_portal_submitter()
        return res

    def _gn_skip_portal_submitter_mail_use_hn_approve_flow(self):
        """Vacaciones tipo principal con correo HN al aprobar: el jefe lo recibe vía ``_send_hn_approval_email``."""
        self.ensure_one()
        if not getattr(self, 'gn_vacation_is_primary', False):
            return False
        return (
            self.env['ir.config_parameter']
            .sudo()
            .get_param('l10n_hn_hr_payroll.send_email_on_approve', 'False')
            == 'True'
        )

    def _send_hn_approval_email(self):
        """Notifica al colaborador y, si aplica, al jefe que solicitó por portal."""
        super()._send_hn_approval_email()
        self._gn_notify_portal_submitter_primary_vacation_approved()

    def _gn_notify_portal_submitter_primary_vacation_approved(self):
        """Correo al jefe portal por mail.mail (mismo criterio que el aviso al empleado)."""
        self.ensure_one()
        submitter = self.gn_portal_submitter_id
        if not submitter:
            return
        email_to = (submitter.email or '').strip()
        if not email_to and submitter.partner_id:
            email_to = (submitter.partner_id.email or '').strip()
        if not email_to:
            _logger.warning(
                'Vacaciones HN aprobadas: jefe portal sin correo (leave=%s, user=%s).',
                self.id,
                submitter.id,
            )
            return
        emp = self.employee_id
        if emp and emp.user_id and submitter.partner_id and emp.user_id.partner_id == submitter.partner_id:
            return
        subject = _('Vacaciones aprobadas — %(name)s') % {'name': emp.name if emp else ''}
        body_plain = _(
            'Las vacaciones que solicitó en el portal para %(name)s han sido aprobadas. '
            'Período: %(df)s al %(dt)s (%(days)s días).',
            name=emp.name if emp else '',
            df=self.request_date_from,
            dt=self.request_date_to,
            days=self.number_of_days,
        )
        body_html = (
            '<div style="font-family:sans-serif"><p>%s</p></div>'
            % html_escape(body_plain)
        )
        email_from = (
            self.company_id.email_formatted
            or self.env.user.email_formatted
            or self.env.ref('base.user_admin').sudo().email_formatted
        )
        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_from': email_from,
                'email_to': email_to,
                'model': 'hr.leave',
                'res_id': self.id,
            })
            mail.send()
        except Exception as e:
            _logger.warning(
                'No se pudo enviar correo vacaciones aprobadas al jefe portal (leave=%s): %s',
                self.id,
                e,
            )

    def _gn_mail_notify_portal_submitter(self):
        """Envía correo al jefe que solicitó la ausencia desde portal."""
        self.ensure_one()
        submitter = self.gn_portal_submitter_id
        if not submitter or not submitter.email:
            return
        employee_name = html_escape(self.employee_id.name or '')
        type_name = html_escape(self.holiday_status_id.name or '')
        if self.state == 'validate':
            subject = _('Ausencia aprobada (%s)') % (employee_name,)
            status_html = '<strong>%s</strong>' % html_escape(_('aprobada'))
        elif self.state == 'refuse':
            subject = _('Ausencia rechazada (%s)') % (employee_name,)
            status_html = '<strong>%s</strong>' % html_escape(_('rechazada'))
        else:
            return
        para = _(
            'La solicitud de ausencia que registró en el portal para el colaborador %(emp)s (%(typ)s) fue %(st)s.'
        ) % {
            'emp': employee_name,
            'typ': type_name,
            'st': status_html,
        }
        body = (
            '<div style="font-family:sans-serif">'
            '<p>%(hello)s %(mgr)s,</p>'
            '<p>%(para)s</p>'
            '<ul><li>%(li_start)s %(ds)s</li><li>%(li_end)s %(de)s</li></ul>'
            '<p style="color:#888;font-size:12px;">%(footer)s</p>'
            '</div>'
        ) % {
            'hello': html_escape(_('Hola')),
            'mgr': html_escape(submitter.name or ''),
            'para': para,
            'li_start': html_escape(_('Inicio:')),
            'ds': html_escape(str(self.request_date_from or '')),
            'li_end': html_escape(_('Fin:')),
            'de': html_escape(str(self.request_date_to or '')),
            'footer': html_escape(_('Mensaje automático — Portal del empleado')),
        }
        email_from = (
            self.company_id.email_formatted
            or self.env.user.email_formatted
            or self.env.ref('base.user_admin').sudo().email_formatted
        )
        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body,
                'email_from': email_from,
                'email_to': submitter.email,
                'model': 'hr.leave',
                'res_id': self.id,
            })
            mail.send()
        except Exception as e:
            _logger.warning(
                'No se pudo enviar correo portal jefe ausencia leave=%s: %s',
                self.id,
                e,
            )

    @api.model
    def gn_portal_preview_leave_restrictions(self, employee, leave_type, request_date_from, request_date_to=None, **kw):
        """Simula una solicitud en memoria y devuelve mensajes bloqueantes / avisos (portal).

        Usar con contexto ``gn_leave_real_uid`` para que las reglas HN respeten al usuario portal.
        """
        self = self.sudo()
        blocking = []
        warnings = []
        seen = set()

        def add_unique(target_list, msg):
            s = str(msg).strip()
            if not s or s in seen:
                return
            seen.add(s)
            target_list.append(s)

        if not employee.exists() or not leave_type.exists():
            add_unique(blocking, _('Datos incompletos para validar la solicitud.'))
            return {'blocking': blocking, 'warnings': warnings}

        request_date_to = request_date_to or request_date_from

        try:
            req_start = fields.Date.from_string(request_date_from)
        except (ValueError, TypeError):
            req_start = None
        if req_start:
            ann_check = getattr(self.env['hr.leave'], '_gn_assert_anniversary_vacation_start', None)
            if ann_check:
                try:
                    ann_check(employee, leave_type, req_start)
                except ValidationError as err:
                    add_unique(blocking, err)

        vals = {
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': request_date_from,
            'request_date_to': request_date_to,
        }
        if leave_type.request_unit == 'half_day':
            vals['request_date_from_period'] = kw.get('request_date_from_period', 'am')
            vals['request_date_to_period'] = kw.get('request_date_to_period', 'pm')
        elif leave_type.request_unit == 'hour':
            vals['request_hour_from'] = kw.get('request_hour_from')
            vals['request_hour_to'] = kw.get('request_hour_to')

        try:
            fake = self.with_context(
                default_employee_id=employee.id,
                employee_id=employee.id,
                default_request_date_from=request_date_from,
            ).new(vals)
            fake._compute_duration()
            fake._compute_leaves()
        except Exception as err:
            add_unique(blocking, err)
            return {'blocking': blocking, 'warnings': warnings}

        compute_dash = getattr(fake, '_compute_dashboard_warning_message', None)
        if compute_dash:
            try:
                compute_dash()
            except Exception:
                _logger.debug('dashboard_warning compute falló en preview portal', exc_info=True)
        if getattr(fake, 'dashboard_warning_message', None):
            add_unique(blocking, fake.dashboard_warning_message)

        check_date = getattr(fake, '_check_date', None)
        if check_date:
            try:
                check_date()
            except ValidationError as err:
                add_unique(blocking, err)

        check_validity = getattr(fake, '_check_validity', None)
        if check_validity:
            try:
                check_validity()
            except ValidationError as err:
                add_unique(blocking, err)

        for meth_name in ('_check_gn_anniversary_vacation_start', '_check_gn_primary_vacation_positive_allocation_balance'):
            meth = getattr(fake, meth_name, None)
            if not meth:
                continue
            try:
                meth()
            except ValidationError as err:
                add_unique(blocking, err)

        return {'blocking': blocking, 'warnings': warnings}
