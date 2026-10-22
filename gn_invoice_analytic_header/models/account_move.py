# -*- coding: utf-8 -*-
from odoo import api, fields, models

# La analítica de cabecera aplica SOLO a facturas de proveedor. En las
# facturas de cliente la analítica ya se asigna automáticamente desde el
# diario de venta (módulo gn_analytic_invoice), por lo que aquí no se ofrece.
_VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_analytic_distribution = fields.Json(
        string="Analítica (cabecera)",
        copy=False,
        help="Solo facturas de proveedor. Distribución analítica que, al "
             "editarse, se vuelca a todas las líneas de producto. Es solo una "
             "ayuda de captura: la analítica NO es obligatoria, puede borrarse "
             "en cualquier línea y la factura podrá validarse igualmente.",
    )
    # Campo auxiliar requerido por el widget ``analytic_distribution``.
    # Se define con el mismo nombre/tipo que en otros módulos, por lo que Odoo
    # fusiona la definición si ya existe (no genera conflicto).
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )

    def _product_lines_for_header_analytic(self):
        """Líneas de producto candidatas a recibir la analítica de cabecera."""
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )

    @api.onchange("invoice_analytic_distribution")
    def _onchange_invoice_analytic_distribution(self):
        """Volcar la analítica de cabecera a las líneas de producto.

        Es una acción explícita del usuario sobre el campo de cabecera, por lo
        que se aplica a todas las líneas de producto presentes en ese momento.

        Importante: la propagación ocurre SOLO aquí (al editar la cabecera).
        No se reaplica al guardar ni al tocar las líneas, de modo que si el
        usuario borra la analítica de una línea, esta permanece vacía y la
        factura puede validarse con normalidad (la analítica no es obligatoria).
        """
        if self.move_type not in _VENDOR_BILL_TYPES:
            return
        distribution = self.invoice_analytic_distribution or False
        if not distribution:
            return
        for line in self._product_lines_for_header_analytic():
            line.analytic_distribution = distribution

    @api.onchange("branch_id")
    def _onchange_branch_id_purchase_analytic(self):
        """Al elegir sucursal en una factura de proveedor, sugerir su
        analítica de compras en las líneas de producto que estén vacías.

        Solo rellena líneas sin analítica propia (no pisa lo capturado a mano
        ni la analítica de cabecera) y nunca es obligatoria.
        """
        if self.move_type not in _VENDOR_BILL_TYPES:
            return
        branch = self.branch_id
        distribution = branch.purchase_analytic_distribution if branch else False
        if not distribution:
            return
        for line in self._product_lines_for_header_analytic():
            if not line.analytic_distribution:
                line.analytic_distribution = distribution
