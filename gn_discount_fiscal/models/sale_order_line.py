# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.tools.float_utils import float_round


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends(
        'product_id',
        'product_uom_id',
        'product_uom_qty',
        'order_id.partner_id',
        'order_id.partner_id.gn_birthdate',
        'order_id.partner_id.gn_is_special_patient',
        'order_id.partner_id.is_company',
    )
    def _compute_discount(self):
        super()._compute_discount()
        prec = self.env['decimal.precision'].precision_get('Discount')
        for line in self:
            if (
                not line.product_id
                or line.display_type
                or line.is_downpayment
                or line._is_global_discount()
                or line.combo_item_id
            ):
                continue
            fiscal = line._gn_get_fiscal_discount_percent_for_line()
            if not fiscal:
                continue
            base = line.discount or 0.0
            combined = 100.0 * (
                1.0 - (1.0 - base / 100.0) * (1.0 - fiscal / 100.0)
            )
            line.discount = float_round(combined, precision_digits=prec)

    def _gn_get_fiscal_discount_percent_for_line(self):
        self.ensure_one()
        order = self.order_id
        if not order:
            return 0.0
        partner = order.partner_id.commercial_partner_id
        if not partner or partner.is_company:
            return 0.0
        return partner.gn_fiscal_discount_percent or 0.0
