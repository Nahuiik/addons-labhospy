# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    gn_pv_percent = fields.Float(
        string='% P.V.',
        digits='Product Price',
        default=0.0,
        help='Porcentaje de utilidad sobre el costo unitario de la línea para calcular el precio de venta.',
    )
    gn_sale_price = fields.Float(
        string='P.V.',
        compute='_compute_gn_sale_price',
        digits='Product Price',
        help='Precio de venta calculado: costo + (costo × % / 100).',
    )

    @api.depends('price_unit', 'gn_pv_percent')
    def _compute_gn_sale_price(self):
        for line in self:
            base = line.price_unit or 0.0
            pct = line.gn_pv_percent or 0.0
            line.gn_sale_price = base * (1.0 + pct / 100.0)

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        vals = super()._prepare_stock_move_vals(
            picking, price_unit, product_uom_qty, product_uom
        )
        if self.order_id.gn_update_sale_price and not self.display_type:
            vals['gn_pv_percent'] = self.gn_pv_percent
            vals['gn_sale_price'] = self.gn_sale_price
        else:
            vals['gn_pv_percent'] = 0.0
            vals['gn_sale_price'] = 0.0
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered(lambda l: not l.display_type)._gn_sync_pv_to_moves()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'gn_pv_percent', 'price_unit'} & set(vals):
            self.filtered(lambda l: not l.display_type)._gn_sync_pv_to_moves()
        return res

    def _gn_sync_pv_to_moves(self):
        for line in self:
            moves = line.move_ids.filtered(
                lambda m: m.state not in ('cancel', 'done')
                and m.product_id == line.product_id
            )
            if line.order_id.gn_update_sale_price:
                moves.write({
                    'gn_pv_percent': line.gn_pv_percent,
                    'gn_sale_price': line.gn_sale_price,
                })
            else:
                moves.write({'gn_pv_percent': 0.0, 'gn_sale_price': 0.0})
