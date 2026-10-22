# -*- coding: utf-8 -*-
from odoo import fields, models


class ResBranch(models.Model):
    _inherit = "res.branch"

    purchase_analytic_distribution = fields.Json(
        string="Distribución Analítica (Compras)",
        help="Distribución analítica que se aplicará por defecto a las líneas "
             "de producto de las facturas de proveedor de esta sucursal. Solo "
             "rellena líneas sin analítica propia y NO es obligatoria: puede "
             "borrarse en cualquier línea y la factura podrá validarse igual.",
    )
    # Campo auxiliar requerido por el widget ``analytic_distribution``.
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )
