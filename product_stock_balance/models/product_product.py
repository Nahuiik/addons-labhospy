# -*- coding: utf-8 -*-

from odoo import api, fields, models


class product_product(models.Model):
    """
    Overwrite to add methods to calculate locations for this product
    """
    _inherit = "product.product"

    def _compute_qty_available_total(self):
        """
        Compute method for qty_available_total

        Methods:
         * _get_sbl_qty - of product.product
        """
        self = self.with_context(total_warehouse=True)
        qtys = self._get_sbl_qty()
        for product in self:
            qty_line = qtys.get(product.id)
            product.qty_available_total = qty_line.get("qty_available")
            product.virtual_available_total = qty_line.get("virtual_available")

    qty_available_total = fields.Float(
        "Total Quantity", compute=_compute_qty_available_total, digits="Product Unit of Measure",
    )
    virtual_available_total = fields.Float(
        "Total Forecast", compute=_compute_qty_available_total, digits="Product Unit of Measure",
    )

    def action_show_table_sbl(self):
        """
        The method to open the tbale of stocks by locations

        Returns:
         * action of opening the table form

        Extra info:
         * Expected singleton
        """
        action_id = self.sudo().env.ref("product_stock_balance.product_product_sbl_button_only_action").read()[0]
        action_id["res_id"] = self.id
        return action_id

    def action_prepare_xlsx_balance_product(self):
        """
        To trigger the method of template
        """
        res = self.product_tmpl_id.action_prepare_xlsx_balance()
        return res

    def action_prepare_xlsx_balance(self):
        """Expose template export action on product variants for view compatibility."""
        return self.action_prepare_xlsx_balance_product()

    def _get_domain_locations(self):
        """
        Overwrite core method to add check of user's default warehouse for quantity widgets.

        The goal is to show available quantities only for the default user warehouse
        while locations table show all stocks.
        """
        default_warehouse = self.env.user.property_warehouse_id
        ctx = self.env.context or {}
        has_explicit_location = any(
            key in ctx
            for key in ("warehouse_id", "search_warehouse", "warehouse", "location", "search_location", "total_warehouse")
        )
        if not has_explicit_location and default_warehouse:
            ctx_updates = {
                "warehouse_id": [default_warehouse.id],
                "warehouse": default_warehouse.id,
            }
            return super(product_product, self.with_context(**ctx_updates))._get_domain_locations()
        return super()._get_domain_locations()

    def _get_sbl_qty(self):
        """
        The method to get dict of various product qty

        Methods:
         * _compute_quantities_dict
        """
        ctx = self.env.context
        return self._compute_quantities_dict(
            ctx.get("lot_id"),
            ctx.get("owner_id"),
            ctx.get("package_id"),
            ctx.get("from_date"),
            ctx.get("to_date"),
        )
