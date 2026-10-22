# Copyright © 2022 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import fields, models


class ProductDataFeedBrand(models.Model):
    _name = "product.data.feed.brand"
    _description = 'Product Brands for Feeds'

    name = fields.Char(string='Nombre', translate=True)
    code = fields.Char(string='Código de Marca', required=False, index=True)

    _name_unique = models.Constraint(
        'unique (name)',
        'Product Brand Name must be unique.'
    )
    
    _code_unique = models.UniqueIndex(
        '(code) WHERE code IS NOT NULL',
        'El código de marca debe ser único.'
    )
