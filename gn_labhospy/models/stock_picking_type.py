# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    use_in_consume_product = fields.Boolean(
        string="Productos de consumo",
        default=False,
        help="Si está marcado, este tipo de operación podrá elegirse en el formulario "
        "Inventario → Productos de consumo (solo traslados internos).",
    )
