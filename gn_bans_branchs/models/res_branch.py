# -*- coding: utf-8 -*-
from odoo import fields, models


class ResBranch(models.Model):
    _inherit = "res.branch"

    bank_analytic_distribution = fields.Json(
        string="Distribución Analítica (Tesorería)",
        help="Distribución analítica que se aplicará por defecto a las líneas "
             "de los documentos de tesorería (débito/crédito) de esta sucursal. "
             "Solo rellena líneas sin analítica propia; puede borrarse en "
             "cualquier línea y no es obligatoria.",
    )
    # Campo auxiliar requerido por el widget ``analytic_distribution``.
    # Si otro módulo ya lo define, Odoo fusiona la definición (mismo nombre/tipo).
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
