from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    gn_labhospy_supplier_id = fields.Many2one(
        related='product_tmpl_id.gn_labhospy_supplier_id',
        string='Proveedor (LabHosPy)',
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        related='product_tmpl_id.gn_labhospy_catalog_code',
        string='Código de Catálogo',
        readonly=True,
    )
