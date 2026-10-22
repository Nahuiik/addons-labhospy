from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    margin = fields.Monetary(
        string="Margin",
        compute="_compute_margin",
        store=True,
        groups=None,
    )
    margin_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_margin",
        store=True,
        aggregator="avg",
        groups=None,
    )

    def action_confirm(self):
        if not self.env.su and not self.env.user.has_group(
            "l10n_hn_stock.group_allow_confirm_sale_view_docs"
        ):
            raise UserError(_("You do not have the permission to confirm sales orders."))
        return super().action_confirm()



