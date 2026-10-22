# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gn_fiscal_matrix_notice = fields.Char(
        string='Aviso descuento fiscal',
        compute='_compute_gn_fiscal_matrix_notice',
    )

    @api.depends(
        'partner_id',
        'partner_id.gn_birthdate',
        'partner_id.gn_is_special_patient',
        'partner_id.is_company',
    )
    def _compute_gn_fiscal_matrix_notice(self):
        for order in self:
            partner = order.partner_id.commercial_partner_id if order.partner_id else False
            if (
                partner
                and not partner.is_company
                and partner.gn_fiscal_discount_percent > 0
            ):
                order.gn_fiscal_matrix_notice = _(
                    'Se aplica descuento fiscal según la matriz configurada (%(pct)s%%).'
                ) % {'pct': partner.gn_fiscal_discount_percent}
            else:
                order.gn_fiscal_matrix_notice = False
