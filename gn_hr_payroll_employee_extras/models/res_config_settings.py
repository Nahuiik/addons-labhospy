# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gn_mail_testing_simulate_send = fields.Boolean(
        string="Simular envío de correo (sin SMTP)",
        config_parameter="gn.mail.testing_simulate_send",
        help="Solo para entornos de prueba: los correos salientes se marcan como enviados y se "
        "actualizan rastreos y notificaciones sin conectar al servidor de correo. "
        "Desactive en producción.",
    )
