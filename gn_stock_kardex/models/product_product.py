# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, fields, models


def _kardex_action(env, product_ids, display_name):
    today = fields.Date.today()
    date_from = today.replace(day=1)
    date_to = today
    return {
        'type': 'ir.actions.client',
        'tag': 'gn_stock_kardex_preview',
        'name': _('Kardex — %s', display_name),
        'target': 'current',
        'context': {
            'kardex_company_id': env.company.id,
            'kardex_branch_id': False,
            'kardex_branch_name': '',
            'kardex_product_ids': product_ids,
            'kardex_date_from': fields.Date.to_string(date_from),
            'kardex_date_to': fields.Date.to_string(date_to),
            'kardex_view_mode': 'detail',
        },
    }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_stock_kardex(self):
        self.ensure_one()
        return _kardex_action(self.env, [self.id], self.display_name)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_open_stock_kardex(self):
        self.ensure_one()
        variants = self.product_variant_ids
        if len(variants) == 1:
            return _kardex_action(self.env, [variants.id], self.display_name)
        return _kardex_action(self.env, list(variants.ids), self.display_name)
