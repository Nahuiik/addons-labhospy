# -*- coding: utf-8 -*-

from odoo import api, models


class ProductReplenish(models.TransientModel):
    """
    Re-write to take user default warehouse
    """
    _inherit = "product.replenish"

    @api.model
    def default_get(self, fields):
        """
        Re-write to take user default warehouse
        """
        res = super(ProductReplenish, self).default_get(fields)
        if self.env.user.property_warehouse_id:
            res["warehouse_id"] = self.env.user.property_warehouse_id.id
        return res
