# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    analytic_distribution = fields.Json(
        "Distribución Analítica por Defecto",
        help="Distribución analítica que se aplicará automáticamente a las "
             "líneas de producto de las facturas de cliente registradas en "
             "este diario (si la línea no tiene una propia).",
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
