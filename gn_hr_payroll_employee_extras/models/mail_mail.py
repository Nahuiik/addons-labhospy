# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Misma lista que la regla del informe (domain en ir_rules / acción).
GN_HR_PAYROLL_MAIL_REPORT_MODELS = frozenset(
    {
        "calendar.event",
        "gn.employee.application",
        "gn.employee.complaint",
        "hr.applicant",
        "hr.contract",
        "hr.employee",
        "hr.leave",
        "hr.payslip",
        "hr.payslip.run",
        "hr.version",
        "res.users",
        "salary.advance",
        "survey.user_input",
    }
)


def _gn_mail_simulation_enabled(env):
    raw = env["ir.config_parameter"].sudo().get_param(
        "gn.mail.testing_simulate_send", "False"
    )
    return str(raw).lower() in ("1", "true", "yes")


class MailMail(models.Model):
    _inherit = "mail.mail"

    gn_mailing_trace_status = fields.Selection(
        selection=[
            ("outgoing", "Outgoing"),
            ("process", "Processing"),
            ("pending", "Sent"),
            ("sent", "Delivered"),
            ("open", "Opened"),
            ("reply", "Replied"),
            ("bounce", "Bounced"),
            ("error", "Exception"),
            ("cancel", "Cancelled"),
        ],
        string="Estado (envío / rastreo)",
        compute="_compute_gn_mailing_trace_fields",
        compute_sudo=True,
        readonly=True,
    )
    gn_mailing_open_datetime = fields.Datetime(
        string="Apertura (rastreo)",
        compute="_compute_gn_mailing_trace_fields",
        compute_sudo=True,
        readonly=True,
    )
    gn_mailing_trace_failure_type = fields.Selection(
        selection=[
            ("unknown", "Unknown error"),
            ("mail_bounce", "Bounce"),
            ("mail_spam", "Detected As Spam"),
            ("mail_email_invalid", "Invalid email address"),
            ("mail_email_missing", "Missing email address"),
            ("mail_from_invalid", "Invalid from address"),
            ("mail_from_missing", "Missing from address"),
            ("mail_smtp", "Connection failed (outgoing mail server problem)"),
            ("mail_bl", "Blacklisted Address"),
            ("mail_dup", "Duplicated Email"),
            ("mail_optout", "Opted Out"),
        ],
        string="Tipo fallo (rastreo)",
        compute="_compute_gn_mailing_trace_fields",
        compute_sudo=True,
        readonly=True,
    )
    gn_mailing_trace_failure_reason = fields.Text(
        string="Motivo fallo (rastreo)",
        compute="_compute_gn_mailing_trace_fields",
        compute_sudo=True,
        readonly=True,
    )

    @api.depends(
        "mailing_trace_ids.trace_status",
        "mailing_trace_ids.open_datetime",
        "mailing_trace_ids.failure_type",
        "mailing_trace_ids.failure_reason",
    )
    def _compute_gn_mailing_trace_fields(self):
        for mail in self:
            trace = mail.mailing_trace_ids[:1]
            if trace:
                mail.gn_mailing_trace_status = trace.trace_status
                mail.gn_mailing_open_datetime = trace.open_datetime
                mail.gn_mailing_trace_failure_type = trace.failure_type
                mail.gn_mailing_trace_failure_reason = trace.failure_reason
            else:
                mail.gn_mailing_trace_status = False
                mail.gn_mailing_open_datetime = False
                mail.gn_mailing_trace_failure_type = False
                mail.gn_mailing_trace_failure_reason = False

    def action_gn_preview_email(self):
        """Abre un diálogo con el HTML del correo (informe nómina/RRHH)."""
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Vista previa del correo"),
            "res_model": "gn.mail.mail.preview.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_mail_id": self.id},
        }

    def action_gn_retry_send_payroll_report(self):
        """Vuelve a poner en cola correos en error/cancelado (informe nómina/RRHH).

        Los usuarios del informe solo tienen lectura sobre mail.mail; el write va en sudo
        tras comprobar acceso de lectura y modelo permitido.
        """
        self.check_access("read")
        retryable = self.filtered(
            lambda m: m.state in ("exception", "cancel")
            and m.model in GN_HR_PAYROLL_MAIL_REPORT_MODELS
        )
        if not retryable:
            raise UserError(
                _(
                    "Solo se pueden reintentar correos en estado de error o cancelados "
                    "del ámbito nómina/RRHH."
                )
            )
        retryable.sudo().write(
            {"state": "outgoing", "failure_type": False, "failure_reason": False}
        )
        return True

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        """Si ``gn.mail.testing_simulate_send`` está activo, no usa SMTP.

        Marca ``mail.mail`` como enviado y ejecuta el posproceso (notificaciones,
        ``mailing.trace``, etc.) como si el envío hubiera sido correcto.
        """
        if _gn_mail_simulation_enabled(self.env):
            outgoing = self.filtered(lambda m: m.state == "outgoing")
            for mail in outgoing:
                mail._gn_simulate_successful_send()
                if auto_commit:
                    if post_send_callback:
                        post_send_callback([mail.id])
                    self.env.cr.commit()
            if post_send_callback:
                post_send_callback(self.ids)
            _logger.warning(
                "GN: simulación de correo sin SMTP (%s registro(s) mail.mail, ids=%s)",
                len(outgoing),
                outgoing.ids,
            )
            return True
        return super().send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            post_send_callback=post_send_callback,
        )

    def _gn_simulate_successful_send(self):
        """Replica destinatarios de éxito sin enviar por SMTP (solo pruebas)."""
        self.ensure_one()
        mail = self
        if mail.state != "outgoing":
            return
        doc_to_followers = None
        if mail.body_html and "/mail/unfollow" in mail.body_html:
            doc_to_followers = self.env["mail.followers"]._get_mail_doc_to_followers(
                mail.ids
            )
        email_list = mail._prepare_outgoing_list(
            mail_server=mail.mail_server_id,
            doc_to_followers=doc_to_followers,
        )
        success_pids = []
        success_emails = []
        for email_vals in email_list:
            data = dict(email_vals)
            processing_pid = data.pop("partner_id", None)
            if processing_pid:
                success_pids.append(processing_pid)
            else:
                success_emails.extend(data.get("email_to") or [])
        fake_mid = mail.message_id
        if not fake_mid:
            fake_mid = tools.mail.generate_tracking_message_id(
                "gn-mail-sim-%s" % mail.id
            )
        mail.write(
            {
                "state": "sent",
                "message_id": fake_mid,
                "failure_type": False,
                "failure_reason": False,
            }
        )
        mail._postprocess_sent_message(
            success_pids=success_pids,
            success_emails=success_emails,
            failure_reason=False,
            failure_type=None,
        )

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        res = super()._prepare_outgoing_list(
            mail_server=mail_server, doc_to_followers=doc_to_followers
        )
        transactional = self.mailing_id and getattr(
            self.mailing_id, "gn_hr_transactional", False
        )
        if not transactional:
            return res
        strip_keys = (
            "List-Unsubscribe",
            "List-Unsubscribe-Post",
            "Precedence",
            "X-Auto-Response-Suppress",
        )
        for email_values in res:
            headers = email_values.get("headers") or {}
            for key in strip_keys:
                headers.pop(key, None)
            email_values["headers"] = headers
        return res
