# -*- coding: utf-8 -*-

from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    gn_labhospy_supplier_id = fields.Many2one(
        related='product_id.product_tmpl_id.gn_labhospy_supplier_id',
        string='Proveedor (LabHosPy)',
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        related='product_id.product_tmpl_id.gn_labhospy_catalog_code',
        string='Código de Catálogo',
        readonly=True,
    )
