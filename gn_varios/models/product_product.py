# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Explícitos para el cliente web en formularios de variante (evita "field is undefined").
    has_warranty = fields.Boolean(
        related='product_tmpl_id.has_warranty',
        readonly=False,
    )
    warranty_time_id = fields.Many2one(
        related='product_tmpl_id.warranty_time_id',
        readonly=False,
    )
    country_of_origin_id = fields.Many2one(
        related='product_tmpl_id.country_of_origin_id',
        readonly=False,
    )
