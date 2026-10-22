from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    readonly_price = fields.Boolean(string="readonly price", compute="_compute_readonly_price")

    def _compute_readonly_price(self):
        for product_id in self:
            product_id.readonly_price = self.env.user.has_groups("eg_lock_price.lock_sale_price_group")