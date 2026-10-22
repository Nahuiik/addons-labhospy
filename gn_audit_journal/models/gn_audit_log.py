# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import html_escape


class GnAuditLog(models.Model):
    _name = "gn.audit.log"
    _description = "Bitácora de auditoría de diarios y secuencias"
    _order = "log_date desc, id desc"
    _rec_name = "title"

    log_date = fields.Datetime(
        string="Fecha", default=fields.Datetime.now, readonly=True, index=True,
    )
    user_id = fields.Many2one(
        "res.users", string="Usuario",
        default=lambda self: self.env.user, readonly=True, index=True,
    )
    operation = fields.Selection(
        [
            ("seq_create", "Secuencia creada"),
            ("seq_write", "Secuencia modificada"),
            ("seq_unlink", "Secuencia eliminada"),
            ("journal_config", "Configuración del diario"),
        ],
        string="Operación", required=True, readonly=True, index=True,
    )
    journal_id = fields.Many2one(
        "account.journal", string="Diario",
        ondelete="set null", readonly=True, index=True,
    )
    sequence_id = fields.Many2one(
        "ir.sequence", string="Secuencia",
        ondelete="set null", readonly=True,
    )
    sequence_name = fields.Char(string="Nombre de secuencia", readonly=True)
    move_type = fields.Char(string="Tipo de transacción", readonly=True)
    title = fields.Char(string="Resumen", readonly=True)
    description = fields.Html(string="Detalle", readonly=True, sanitize=False)
    company_id = fields.Many2one(
        "res.company", string="Compañía",
        default=lambda self: self.env.company, readonly=True, index=True,
    )

    @api.model
    def _gn_create_log(self, journal=None, operation="seq_write", title="",
                       lines=None, sequence_id=False, sequence_name=False,
                       move_type=False, post_chatter=True):
        """Crea un registro de bitácora y, opcionalmente, una nota en el chatter.

        Se invoca normalmente con sudo() desde los modelos auditados; env.user
        (el autor real del cambio) se conserva para la autoría.
        """
        lines = lines or []
        body = Markup("<p><strong>%s</strong></p><ul>%s</ul>") % (
            html_escape(title),
            Markup("").join(Markup("<li>%s</li>") % Markup(line) for line in lines),
        )
        log = self.create({
            "operation": operation,
            "journal_id": journal.id if journal else False,
            "sequence_id": sequence_id or False,
            "sequence_name": sequence_name or False,
            "move_type": move_type or False,
            "title": title or False,
            "description": body,
            "company_id": (
                journal.company_id.id
                if journal and journal.company_id
                else self.env.company.id
            ),
        })
        if post_chatter and journal:
            journal.message_post(
                body=body,
                subtype_xmlid="mail.mt_note",
                message_type="notification",
            )
        return log

    def _gn_audit_log_label(self):
        return _("Bitácora de auditoría")
