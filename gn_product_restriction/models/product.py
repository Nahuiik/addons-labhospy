# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import AccessError

GN_GROUP = 'gn_product_restriction.group_allow_product_create'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group(GN_GROUP):
            raise AccessError(_(
                "No tiene permiso para crear productos. "
                "Solicite el grupo «Permitir crear productos (GN)» al administrador."
            ))
        # sudo() para que create() no falle por perm_write=0 en el ACL del
        # grupo GN; el chequeo de permisos ya se hizo arriba.
        records = super(ProductTemplate, self.sudo()).create(vals_list)
        return records.with_env(self.env)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group(GN_GROUP):
            raise AccessError(_(
                "No tiene permiso para crear productos. "
                "Solicite el grupo «Permitir crear productos (GN)» al administrador."
            ))
        records = super(ProductProduct, self.sudo()).create(vals_list)
        return records.with_env(self.env)
