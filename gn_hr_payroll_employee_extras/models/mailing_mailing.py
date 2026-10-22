# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class MailingMailing(models.Model):
    _inherit = "mailing.mailing"

    gn_hr_transactional = fields.Boolean(
        string="Envío transaccional nómina/RRHH",
        default=False,
        copy=False,
        help="Correos generados desde plantillas de nómina/RRHH (no campañas de marketing). "
        "Usado para reglas de acceso y para omitir cabeceras tipo listas de distribución.",
    )
