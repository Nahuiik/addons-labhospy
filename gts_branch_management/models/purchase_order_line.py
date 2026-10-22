from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_stock_moves(self, picking):
        moves_vals = super()._prepare_stock_moves(picking)
        branch_id = self.order_id.branch_id.id
        if branch_id:
            for vals in moves_vals:
                vals['branch_id'] = branch_id
        return moves_vals
