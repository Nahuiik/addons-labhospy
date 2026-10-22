from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    hn_production_material_transfer_id = fields.Many2one(
        "hn.production.material.transfer",
        string="Solicitud materiales producción",
        copy=False,
        readonly=True,
    )

    def _action_done(self):
        res = super()._action_done()
        transfers = self.env["hn.production.material.transfer"].search(
            [
                ("picking_id", "in", self.ids),
                ("state", "=", "approved"),
            ]
        )
        if transfers:
            transfers.with_context(hn_production_transfer_auto_write=True).write(
                {"state": "done"}
            )
        productions = transfers.production_id.filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        if productions:
            productions.action_assign()
        return res
