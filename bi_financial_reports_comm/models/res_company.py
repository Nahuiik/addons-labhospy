# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bi_totals_below_sections = fields.Boolean(
        string="Totales bajo secciones",
        help=(
            "Muestra el total de cada sección debajo del desglose de cuentas "
            "en los informes financieros on-screen."
        ),
        default=True,
    )
