# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    gn_update_sale_price = fields.Boolean(
        string='Actualiza P.V.',
        default=False,
        help='Si está activo, las líneas muestran % y P.V.; al validar la recepción se '
             'actualizan el costo y el precio de venta en la plantilla del producto.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'gn_update_sale_price' in vals:
            self.order_line.filtered(lambda l: not l.display_type)._gn_sync_pv_to_moves()
        return res
