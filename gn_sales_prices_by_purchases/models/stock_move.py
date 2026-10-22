# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.tools.float_utils import float_round


class StockMove(models.Model):
    _inherit = 'stock.move'

    gn_pv_percent = fields.Float(string='% P.V.', digits='Product Price')
    gn_sale_price = fields.Float(string='P.V.', digits='Product Price')

    def _action_done(self, cancel_backorder=False):
        done_moves = super()._action_done(cancel_backorder=cancel_backorder)
        done_moves._gn_apply_template_prices_from_purchase_done()
        return done_moves

    def _gn_apply_template_prices_from_purchase_done(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        by_tmpl = {}

        for move in self:
            if move._is_purchase_return():
                continue
            pol = move.purchase_line_id
            if (
                not pol
                or pol.display_type
                or not pol.order_id.gn_update_sale_price
                or not move.product_id
            ):
                continue
            picking = move.picking_id
            if not picking or picking.picking_type_id.code != 'incoming':
                continue

            tmpl = move.product_id.product_tmpl_id
            order = pol.order_id
            company = order.company_id
            company_ccy = company.currency_id
            po_ccy = order.currency_id
            cost_po = pol.price_unit or 0.0
            pct = pol.gn_pv_percent or 0.0
            convert_date = fields.Date.context_today(move)
            if po_ccy and company_ccy and po_ccy != company_ccy:
                cost_company = po_ccy._convert(
                    cost_po,
                    company_ccy,
                    company,
                    convert_date,
                    round=False,
                )
            else:
                cost_company = cost_po
            pv_company = cost_company * (1.0 + pct / 100.0)
            cost_company = float_round(cost_company, precision_digits=prec)
            pv_company = float_round(pv_company, precision_digits=prec)

            by_tmpl[tmpl.id] = {
                'tmpl': tmpl,
                'cost': cost_company,
                'pv': pv_company,
                'picking': picking,
                'order': order,
            }

        for data in by_tmpl.values():
            tmpl = data['tmpl']
            old_cost = tmpl.standard_price
            old_list = tmpl.list_price
            new_cost = data['cost']
            new_list = data['pv']
            tmpl.write({
                'standard_price': new_cost,
                'list_price': new_list,
            })
            tmpl.message_post(
                body=_(
                    'Precio actualizado por recepción %(picking)s (OC %(po)s).\n'
                    'Costo: %(old_c)s → %(new_c)s.\n'
                    'Precio de venta: %(old_p)s → %(new_p)s %(curr)s.',
                    picking=data['picking'].display_name,
                    po=data['order'].name,
                    old_c=old_cost,
                    new_c=new_cost,
                    old_p=old_list,
                    new_p=new_list,
                    curr=data['order'].company_id.currency_id.display_name,
                )
            )
