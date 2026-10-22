# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    def action_open_traceability(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_('El movimiento no tiene producto asociado.'))
        lot_id = False
        lots = self.move_line_ids.lot_id
        if len(lots) == 1:
            lot_id = lots.id
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_product_traceability_dashboard',
            'name': self.product_id.display_name,
            'params': {
                'product_id': self.product_id.id,
                'product_tmpl_id': self.product_id.product_tmpl_id.id,
                'lot_id': lot_id,
                'document': self.reference or self.origin or (self.picking_id.name if self.picking_id else ''),
            },
        }
