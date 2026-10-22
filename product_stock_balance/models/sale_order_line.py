# -*- coding: utf-8 -*-

from odoo import api, fields, models


class sale_order_line(models.Model):
    """
    Overwrite to calc whether the stocks by locations widget should be shown
    """
    _inherit = "sale.order.line"

    @api.depends("product_type")
    def _compute_show_psb(self):
        """
        Compute method for show_psb
        """
        for line in self:
            line.show_psb = line.product_type and line.product_type != "service" or False

    show_psb = fields.Boolean(compute=_compute_show_psb)
