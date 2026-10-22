# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "product.product"

    lot_seril_number = fields.One2many(
        "stock.lot", "product_id", string="Lots/Seril No."
    )
