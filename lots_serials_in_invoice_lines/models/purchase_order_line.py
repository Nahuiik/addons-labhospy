from odoo import api, fields, models, _


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    lot_ids = fields.Many2many(
        "stock.lot",
        compute="_compute_lot_ids",
        string="Lots / Serials",
        help="Lotes reservados en los movimientos relacionados.",
    )

    @api.depends("move_ids.lot_ids")
    def _compute_lot_ids(self):
        for line in self:
            line.lot_ids = line.move_ids.mapped("lot_ids")

    def action_view_lot_ids(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "target": "new",
            "name": _("Lots / Serials"),
            "view_mode": "tree",
            "view_id": self.env.ref("lots_serials_in_invoice_lines.stock_lot_custom_tree").id,
            "res_model": "stock.lot",
            "domain": [("id", "in", self.lot_ids.ids)],
        }
