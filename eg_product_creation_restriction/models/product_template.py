from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def create(self, vals):
        if self.env.user.has_group('eg_product_creation_restriction.product_creation_restriction'):
            raise ValidationError(_("You don't have access to create product."))
        return super(ProductTemplate, self).create(vals)
