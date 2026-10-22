# -*- coding: utf-8 -*-

from odoo import models

from .helpers import ensure_inventory_privilege


class StockForecastedProductProduct(models.AbstractModel):
    _inherit = "stock.forecasted_product_product"

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(product_template_ids=product_template_ids, product_ids=product_ids)
        res["can_update_qty"] = ensure_inventory_privilege(self.env)
        return res


class StockForecastedProductTemplate(models.AbstractModel):
    _inherit = "stock.forecasted_product_template"

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(product_template_ids=product_template_ids, product_ids=product_ids)
        res["can_update_qty"] = ensure_inventory_privilege(self.env)
        return res
