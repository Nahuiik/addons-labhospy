# -*- coding: utf-8 -*-
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends("order_id.partner_id", "product_id")
    def _compute_analytic_distribution(self):
        """Sin reparto analitico automatico desde modelos de distribucion en ventas.

        El estandar de Odoo rellena analytic_distribution desde
        account.analytic.distribution.model (mismo criterio que compras), lo que
        en cotizaciones/pedidos muestra centros pensados para proveedor.
        Aqui solo se deja vacio; el usuario puede indicar analitica manualmente si la necesita.
        """
        for line in self:
            if line.display_type:
                continue
            line.analytic_distribution = False
