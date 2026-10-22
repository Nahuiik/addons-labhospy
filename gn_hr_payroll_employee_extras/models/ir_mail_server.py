# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import api, models


class IrMailServer(models.Model):
    _inherit = "ir.mail_server"

    @api.model
    def gn_hr_outgoing_smtp_configured(self) -> bool:
        """Indica si hay al menos un servidor de correo **saliente** activo.

        Los avisos automáticos del ecosistema RRHH/nómina GN que usan
        ``send_mail_payroll_tracked`` o notificaciones por correo dependen de esto
        para no generar correos cuando no hay SMTP configurado.
        """
        return bool(self.sudo().search([("active", "=", True)], limit=1))
