from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    d_product_brand_id = fields.Many2one(
        'd.product.brand',
        string='Brand', help="Brand for this product, this information mostly use for seo Purpose (in schema of product)"
    )
