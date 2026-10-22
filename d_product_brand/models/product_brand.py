from odoo import models, fields

class ProductBrand(models.Model):
    _name = 'd.product.brand'
    _description = 'Product Brand'

    name = fields.Char(
        string='Brand Name',
        required=True
    )
    description = fields.Text(
        string='Description'
    )
    logo = fields.Binary(
        string='Brand Logo'
    )
    website = fields.Char(
        string='Website',
        help="Official website of the brand"
    )
