# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

import pytz

from odoo import api, fields, models, _
from odoo.tools.misc import clean_context


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    gn_vacation_is_primary = fields.Boolean(
        related='holiday_status_id.gn_vacation_is_primary',
        string='Vacaciones (tipo principal)',
    )

    @api.model
    def _gn_collective_vacation_notification_suppress_kw(self):
        """Si el contexto es de vacaciones colectivas silenciosas, message_post no notifica (sin correo)."""
        if self.env.context.get('gn_collective_vacation_no_mail'):
            return {
                'partner_ids': [],
                'notify_skip_followers': True,
                'subtype_xmlid': 'mail.mt_note',
            }
        return {}

    def _validate_leave_request(self):
        """Evita correos masivos: el estándar notifica al empleado vía message_post."""
        if self.env.context.get('gn_collective_vacation_no_mail'):
            holidays = self.filtered('employee_id')
            holidays._create_resource_leave()
            meeting_holidays = holidays.filtered(lambda l: l.holiday_status_id.create_calendar_meeting)
            meetings = self.env['calendar.event']
            if meeting_holidays:
                Meeting = self.env['calendar.event']
                Meeting.check_access('create')
                meeting_values_for_user_id = meeting_holidays._prepare_holidays_meeting_values()
                for user_id, meeting_values in meeting_values_for_user_id.items():
                    meetings += Meeting.with_user(user_id or self.env.uid).sudo().with_context(
                        clean_context({
                            **self.env.context,
                            **{
                                'allowed_company_ids': [],
                                'no_mail_to_attendees': True,
                                'calendar_no_videocall': True,
                                'active_model': self._name,
                            },
                        })
                    ).create(meeting_values)
            Holiday = self.env['hr.leave']
            for meeting in meetings:
                Holiday.browse(meeting.res_id).meeting_id = meeting
            extra_kw = self.env['hr.leave']._gn_collective_vacation_notification_suppress_kw()
            for holiday in holidays:
                user_tz = pytz.timezone(holiday.tz)
                utc_tz = pytz.utc.localize(holiday.date_from).astimezone(user_tz)
                holiday.message_post(
                    body=_(
                        'Your %(leave_type)s planned on %(date)s has been accepted',
                        leave_type=holiday.holiday_status_id.display_name,
                        date=utc_tz.replace(tzinfo=None),
                    ),
                    **extra_kw,
                )
            return
        return super()._validate_leave_request()

    def _gn_finalize_collective_vacation(self, wizard):
        """Extender en localizaciones (constancias, anticipos, etc.)."""
        self.ensure_one()
