# Copyright © 2022 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    descripcion = fields.Char(string='Descripción', translate=True)
    
    cc_proveedor = fields.Char(
        string='CC Proveedor',
        help='Codigo Color Proveedor'
    )


