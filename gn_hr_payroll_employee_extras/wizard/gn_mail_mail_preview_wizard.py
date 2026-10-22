# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import api, fields, models


class GnMailMailPreviewWizard(models.TransientModel):
    _name = "gn.mail.mail.preview.wizard"
    _description = "Vista previa de correo saliente"

    mail_id = fields.Many2one(
        "mail.mail",
        string="Correo",
        required=True,
        readonly=True,
    )
    subject = fields.Char(related="mail_id.subject", readonly=True)
    email_from = fields.Char(related="mail_id.email_from", readonly=True)
    email_to = fields.Text(related="mail_id.email_to", readonly=True)
    body_preview = fields.Html(
        string="Contenido",
        compute="_compute_body_preview",
        sanitize=False,
        readonly=True,
    )

    @api.depends("mail_id.body_html")
    def _compute_body_preview(self):
        for wiz in self:
            wiz.body_preview = wiz.mail_id.body_html or ""
