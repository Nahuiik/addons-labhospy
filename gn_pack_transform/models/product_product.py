# -*- coding: utf-8 -*-
from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_gn_pack_open_transform(self):
        self.ensure_one()
        return self.product_tmpl_id.action_gn_pack_open_transform()
