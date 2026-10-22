from odoo import models, api, _
import math


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    #@api.onchange('price_unit')
    #def validate_price_change(self):
    #    warning = {}
    #    if self.product_id and self.product_id.type == 'product' and self.product_id.hospital_product_type in ['medicament', 'disposable_material']:
    #        is_in_group = self.env.user.has_group('gn_sale_and_purchase_history.sell_with_lower_up_group')
    #        price = self.product_id.lst_price
    #        if not is_in_group:
    #            if self.price_unit < price :
    #                warning = {
    #                    'title': _("Price Warning!"),
    #                    'message': _("Sale price should not be less then %s for this product")%(round(price, 4)),
    #                }
    #    if warning:
    #        self.price_unit = price
#
    #        return {'warning': warning}

    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     """round unit price to higher number when price in decimal point for sale invoice"""
    #     # res = super(AccountMoveLine, self)._onchange_product_id()
    #     if self.move_id.move_type in ['out_invoice', 'out_refund']:
    #         self.price_unit = math.ceil(self.price_unit)
    #     return res

