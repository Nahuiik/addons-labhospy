from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    lot_ids = fields.Many2many(
        "stock.lot",
        compute="_compute_lot_ids",
        string="Lots / Serials",
        help="Lotes vinculados a la línea de factura.",
    )

    @api.depends("sale_line_ids.lot_ids", "purchase_line_id.lot_ids")
    def _compute_lot_ids(self):
        for line in self:
            lots = line.sale_line_ids.mapped("lot_ids")
            if line.purchase_line_id:
                lots |= line.purchase_line_id.lot_ids
            line.lot_ids = lots

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
