# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_open_traceability(self):
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.product_id and m.product_id.is_storable)
        if not moves:
            raise UserError(_('La transferencia no contiene productos almacenables.'))
        product = moves[0].product_id
        lot_id = False
        lots = moves.move_line_ids.lot_id
        if len(lots) == 1:
            lot_id = lots.id
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_product_traceability_dashboard',
            'name': product.display_name,
            'params': {
                'product_id': product.id,
                'product_tmpl_id': product.product_tmpl_id.id,
                'lot_id': lot_id,
                'document': self.name,
            },
        }
