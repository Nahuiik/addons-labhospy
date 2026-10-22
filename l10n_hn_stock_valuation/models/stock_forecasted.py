from odoo import models


def _can_update_quantities(env):
    """Return True if current user can update inventory quantities."""
    return env.user.has_group("l10n_hn_stock_valuation.group_view_inventory_button")


class StockForecastedProductProduct(models.AbstractModel):
    _inherit = "stock.forecasted_product_product"

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(
            product_template_ids=product_template_ids,
            product_ids=product_ids,
        )
        res["can_update_qty"] = _can_update_quantities(self.env)
        return res


class StockForecastedProductTemplate(models.AbstractModel):
    _inherit = "stock.forecasted_product_template"

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(
            product_template_ids=product_template_ids,
            product_ids=product_ids,
        )
        res["can_update_qty"] = _can_update_quantities(self.env)
        return res



