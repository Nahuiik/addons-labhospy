# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

import logging

from odoo import _, fields, models, tools

_logger = logging.getLogger(__name__)


class MailTemplate(models.Model):
    _inherit = "mail.template"

    gn_hr_ecosystem = fields.Boolean(
        string="Plantilla ecosistema nómina/RRHH GN",
        default=False,
        copy=False,
        help="Si está marcado, la plantilla aparece en Empleados → Configuración → "
        "Plantillas correo (vista filtrada del ecosistema GN).",
    )

    def send_mail_payroll_tracked(
        self,
        res_id,
        force_send=False,
        raise_exception=False,
        email_values=None,
        email_layout_xmlid=False,
    ):
        """Igual que send_mail pero crea mailing.mailing + mailing.trace (Email Marketing)."""
        self.ensure_one()
        if not self.env["ir.mail_server"].gn_hr_outgoing_smtp_configured():
            _logger.info(
                "GN HR: omitido send_mail_payroll_tracked (sin SMTP saliente). "
                "plantilla=%s model=%s res_id=%s",
                self.id,
                self.model,
                res_id,
            )
            return False
        return self.with_context(gn_payroll_send_mailing_tracked=True).send_mail(
            res_id,
            force_send=force_send,
            raise_exception=raise_exception,
            email_values=email_values,
            email_layout_xmlid=email_layout_xmlid,
        )

    def send_mail(
        self,
        res_id,
        force_send=False,
        raise_exception=False,
        email_values=None,
        email_layout_xmlid=False,
    ):
        """Evita IndexError si el lote rastreado no crea correos (p. ej. sin SMTP)."""
        self.ensure_one()
        if self.env.context.get("gn_payroll_send_mailing_tracked"):
            mails = self.send_mail_batch(
                [res_id],
                force_send=force_send,
                raise_exception=raise_exception,
                email_values=email_values,
                email_layout_xmlid=email_layout_xmlid,
            )
            if not mails:
                return False
            return mails[0].id
        return super().send_mail(
            res_id,
            force_send=force_send,
            raise_exception=raise_exception,
            email_values=email_values,
            email_layout_xmlid=email_layout_xmlid,
        )

    def _gn_payroll_trace_email_from_values(self, values):
        email_to = (values.get("email_to") or "").strip()
        if email_to:
            first = email_to.split(",")[0].strip()
            normalized = tools.email_normalize(first, strict=False)
            return normalized or first
        partner_commands = values.get("recipient_ids") or []
        partner_ids = [c[1] for c in partner_commands if len(c) >= 2 and c[0] == 4]
        if partner_ids:
            partners = self.env["res.partner"].sudo().browse(partner_ids)
            for partner in partners:
                raw = partner.email or ""
                normalized = tools.email_normalize(raw, strict=False)
                if normalized or raw:
                    return normalized or raw.strip()
        return ""

    def _gn_payroll_attach_mailing_trace(self, record, values, record_ir_model):
        self.ensure_one()
        now = fields.Datetime.now()
        subject = (values.get("subject") or "").strip() or _("Correo nómina/RRHH")
        mailing = self.env["mailing.mailing"].sudo().create(
            {
                "subject": subject,
                "mailing_model_id": record_ir_model.id,
                "mailing_domain": str([("id", "in", [record.id])]),
                "state": "done",
                "sent_date": now,
                "schedule_type": "now",
                "use_exclusion_list": False,
                "gn_hr_transactional": True,
            }
        )
        msg_vals = {
            "model": values.get("model") or self.model,
            "res_id": values.get("res_id") or record.id,
            "reply_to_force_new": values.get("reply_to_force_new", False),
        }
        message_id = self.env["mail.message"]._get_message_id(msg_vals)
        values["message_id"] = message_id
        values["references"] = message_id
        trace_vals = {
            "email": self._gn_payroll_trace_email_from_values(values),
            "mass_mailing_id": mailing.id,
            "message_id": message_id,
            "model": self.model,
            "res_id": record.id,
        }
        values["mailing_id"] = mailing.id
        values["mailing_trace_ids"] = [(0, 0, trace_vals)]

    def send_mail_batch(
        self,
        res_ids,
        force_send=False,
        raise_exception=False,
        email_values=None,
        email_layout_xmlid=False,
    ):
        if not self.env.context.get("gn_payroll_send_mailing_tracked"):
            return super().send_mail_batch(
                res_ids,
                force_send=force_send,
                raise_exception=raise_exception,
                email_values=email_values,
                email_layout_xmlid=email_layout_xmlid,
            )

        self.ensure_one()
        if not self.env["ir.mail_server"].gn_hr_outgoing_smtp_configured():
            _logger.info(
                "GN HR: omitido send_mail_batch rastreado (sin SMTP saliente). "
                "plantilla=%s model=%s res_ids=%s",
                self.id,
                self.model,
                res_ids,
            )
            return self.env["mail.mail"]
        self._send_check_access(res_ids)
        sending_email_layout_xmlid = email_layout_xmlid or self.email_layout_xmlid

        mails_sudo = self.env["mail.mail"].sudo()
        batch_size = (
            int(self.env["ir.config_parameter"].sudo().get_param("mail.batch_size"))
            or 50
        )
        RecordModel = self.env[self.model].with_prefetch(res_ids)
        record_ir_model = self.env["ir.model"]._get(self.model)

        for res_ids_chunk in tools.split_every(batch_size, res_ids):
            res_ids_values = self._generate_template(
                res_ids_chunk,
                (
                    "attachment_ids",
                    "auto_delete",
                    "body_html",
                    "email_cc",
                    "email_from",
                    "email_to",
                    "mail_server_id",
                    "model",
                    "partner_to",
                    "reply_to",
                    "report_template_ids",
                    "res_id",
                    "scheduled_date",
                    "subject",
                ),
            )

            records = RecordModel.browse(res_ids_chunk)
            attachments_list = []

            res_ids_langs, res_ids_companies = {}, {}
            if sending_email_layout_xmlid:
                if self.lang:
                    res_ids_langs = self._render_lang(res_ids_chunk)
                res_ids_companies = records._mail_get_companies(default=self.env.company)

            values_list = []
            for record in records:
                values = res_ids_values[record.id]
                values["recipient_ids"] = [
                    (4, pid) for pid in (values.get("partner_ids") or [])
                ]
                values["attachment_ids"] = [
                    (4, aid) for aid in (values.get("attachment_ids") or [])
                ]
                values.update(email_values or {})

                attachments_list.append(values.pop("attachments", []))

                if "email_from" in values and not values.get("email_from"):
                    values.pop("email_from")

                if not sending_email_layout_xmlid:
                    values["body"] = values["body_html"]
                else:
                    lang = res_ids_langs.get(record.id) or self.env.lang
                    company = res_ids_companies.get(record.id) or self.env.company
                    model_lang = record_ir_model.with_context(lang=lang)
                    self_lang = self.with_context(lang=lang)
                    record_lang = record.with_context(lang=lang)

                    values["body_html"] = self_lang._render_encapsulate(
                        sending_email_layout_xmlid,
                        values["body_html"],
                        add_context={
                            "company": company,
                            "model_description": model_lang.display_name,
                        },
                        context_record=record_lang,
                    )
                    values["body"] = values["body_html"]

                self._gn_payroll_attach_mailing_trace(record, values, record_ir_model)
                values_list.append(values)

            mails = self.env["mail.mail"].sudo().create(values_list)

            for mail, attachments in zip(mails, attachments_list):
                if attachments:
                    attachments_values = [
                        (
                            0,
                            0,
                            {
                                "name": name,
                                "datas": datas,
                                "type": "binary",
                                "res_model": "mail.message",
                                "res_id": mail.mail_message_id.id,
                            },
                        )
                        for (name, datas) in attachments
                    ]
                    mail.with_context(default_type=None).write(
                        {"attachment_ids": attachments_values}
                    )

            mails_sudo += mails

        if force_send:
            mails_sudo.send(raise_exception=raise_exception)
        return mails_sudo
