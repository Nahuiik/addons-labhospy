# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, api
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _search(self, domain, *args, **kwargs):
        """Overriding the _search method to modify how products are searched"""
        user = self.env.user
        restricted_group = self.env.ref(
            "cr_product_restric_user.cr_product_restriction_on_user"
        )

        if restricted_group in user.group_ids:
            if user.cr_restriction_on == "product":
                product_ids = user.cr_product_template_ids.ids
                if product_ids:
                    domain = Domain.AND([domain, [("id", "in", product_ids)]])
                else:
                    return super()._search(Domain.FALSE, *args, **kwargs)

            elif user.cr_restriction_on == "category":
                category_ids = user.cr_product_category_ids.ids
                if category_ids:
                    domain = Domain.AND([domain, [("categ_id", "in", category_ids)]])
                else:
                    return super()._search(Domain.FALSE, *args, **kwargs)

        return super()._search(domain, *args, **kwargs)


class Product(models.Model):
    _inherit = "product.product"

    @api.model
    def _search(self, domain, *args, **kwargs):
        """Overriding the _search method to modify how products are searched"""
        user = self.env.user
        restricted_group = self.env.ref(
            "cr_product_restric_user.cr_product_restriction_on_user"
        )

        if restricted_group in user.group_ids:
            if user.cr_restriction_on == "product":
                template_ids = user.cr_product_template_ids.ids
                if template_ids:
                    domain = Domain.AND([domain, [("product_tmpl_id", "in", template_ids)]])
                else:
                    return super()._search(Domain.FALSE, *args, **kwargs)

            elif user.cr_restriction_on == "category":
                category_ids = user.cr_product_category_ids.ids
                if category_ids:
                    domain = Domain.AND([domain, [("categ_id", "in", category_ids)]])
                else:
                    return super()._search(Domain.FALSE, *args, **kwargs)

        return super()._search(domain, *args, **kwargs)
