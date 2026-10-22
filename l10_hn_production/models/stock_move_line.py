from odoo import api, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.lot_id._hn_init_container_content()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "lot_id" in vals:
            self.lot_id._hn_init_container_content()
        return res
