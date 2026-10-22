# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

"""Evitar recalcular y escribir ``standard_price`` en traslados entre tiendas.

Los movimientos internos (origen → tránsito → destino) son transferencias internas:
no incorporan mercancía nueva ni la sacan de la compañía. Odoo puede invocar
``_update_standard_price`` tras validar (p. ej. tramo visto como entrada valorada
o por FIFO/lotes), provocando cambios de coste en ficha o diferencias por redondeo.

Al validar pickings generados por ``stock.inter.store.transfer`` se pasa el contexto
``l10n_hn_inter_store_transfer_skip_standard_price_update`` (ver
``_l10n_hn_ctx_traslado_chatter_costos``).
"""

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _update_standard_price(self, extra_value=None, extra_quantity=None):
        if self.env.context.get("l10n_hn_inter_store_transfer_skip_standard_price_update"):
            return
        return super()._update_standard_price(
            extra_value=extra_value, extra_quantity=extra_quantity
        )


class StockLot(models.Model):
    _inherit = "stock.lot"

    def _update_standard_price(self):
        if self.env.context.get("l10n_hn_inter_store_transfer_skip_standard_price_update"):
            return
        return super()._update_standard_price()
