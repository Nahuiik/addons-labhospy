# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"

    cr_restriction_on = fields.Selection(
        selection=[("product", "Product"), ("category", "Category")],
        string="Restriction On",
    )
    cr_product_template_ids = fields.Many2many(
        comodel_name="product.template", string="Products"
    )
    cr_product_category_ids = fields.Many2many(
        comodel_name="product.category", string="Product Category"
    )
