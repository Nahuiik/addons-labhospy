# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Ajith V(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class SaleOrder(models.Model):
    """
    This class extends the 'sale.order' model to include a new field
    'delivery_status' which tracks the delivery status of the sale order.
    """
    _inherit = 'sale.order'

    delivery_status = fields.Selection(
        selection_add=[
            ('nothing', 'Nothing to Deliver'),
            ('to_deliver', 'To Deliver'),
            ('delivered', 'Delivered'),
            ('processing', 'Processing'),
        ],
    )

    @api.depends(
        'state',
        'order_line.qty_delivered',
        'order_line.product_uom_qty',
        'order_line.product_uom_id.rounding',
        'order_line.product_id.type',
        'order_line.display_type',
        'picking_ids.state',
    )
    def _compute_delivery_status(self):
        """Compute an intuitive delivery status for the sale order."""
        super()._compute_delivery_status()
        for order in self:
            if order.state == 'cancel':
                order.delivery_status = False
                continue

            pickings = order.picking_ids.filtered(lambda p: p.state != 'cancel')
            stock_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id.type != 'service'
            )
            service_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id.type == 'service'
            )

            status = 'pending'
            if not stock_lines and not service_lines:
                status = 'pending'
            elif not stock_lines and service_lines:
                status = 'full' if order.state in ('sale', 'done') else 'pending'
            elif stock_lines:
                all_zero = True
                all_full = True
                any_delivered = False
                for line in stock_lines:
                    rounding = line.product_uom_id.rounding or 1e-6
                    if not float_is_zero(line.qty_delivered, precision_rounding=rounding):
                        all_zero = False
                        any_delivered = True
                    if float_compare(line.qty_delivered, line.product_uom_qty, precision_rounding=rounding) < 0:
                        all_full = False
                    elif float_compare(line.qty_delivered, line.product_uom_qty, precision_rounding=rounding) > 0:
                        any_delivered = True

                if all_zero:
                    status = 'pending'
                elif not all_full:
                    status = 'partial'
                else:
                    status = 'full'

            if pickings.filtered(lambda picking: picking.state in ('waiting', 'confirmed', 'assigned')):
                status = 'started'

            order.delivery_status = status
