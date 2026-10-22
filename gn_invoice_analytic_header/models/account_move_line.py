# -*- coding: utf-8 -*-
from odoo import api, models

_VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange("product_id")
    def _onchange_product_id_branch_analytic(self):
        """Sugerir la analítica de la sucursal en líneas NUEVAS de facturas de
        proveedor.

        Solo actúa sobre líneas recién agregadas (``_origin`` vacío) y sin
        analítica propia, de modo que si el usuario borra la analítica de una
        línea existente, esta permanece vacía. La analítica no es obligatoria.
        """
        line = self
        move = line.move_id
        if not move or move.move_type not in _VENDOR_BILL_TYPES:
            return
        if line.display_type and line.display_type != "product":
            return
        if line._origin:
            return
        if line.analytic_distribution:
            return
        branch = move.branch_id
        distribution = branch.purchase_analytic_distribution if branch else False
        if distribution:
            line.analytic_distribution = distribution
