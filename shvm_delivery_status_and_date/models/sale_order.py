# -*- coding: utf-8 -*-
# Email: sales@creyox.com

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_status = fields.Selection([
        ('not_delivered', 'Not Delivered'),
        ('partially_delivered', 'Partially Delivered'),
        ('delivered', 'Delivered')
    ], string='Delivered', compute="compute_delivery_status", store=True, readonly=True)

    delivered_date = fields.Datetime(compute="compute_delivered_date", store=True)

    @api.depends('order_line.qty_delivered', 'order_line.product_uom_qty')
    def compute_delivery_status(self):
        for rec in self:
            qty_deliver_count = sum(
                rec.mapped('order_line').filtered(lambda r: r.product_id.type != 'service').mapped('qty_delivered'))
            qty_order_count = sum(
                rec.mapped('order_line').filtered(lambda r: r.product_id.type != 'service').mapped('product_uom_qty'))
            if qty_order_count > qty_deliver_count > 0:
                rec.delivery_status = 'partially_delivered'
            elif qty_order_count <= qty_deliver_count > 0:
                rec.delivery_status = 'delivered'
            else:
                rec.delivery_status = 'not_delivered'

    @api.depends('delivery_status')
    def compute_delivered_date(self):
        self.delivered_date = False
        for rec in self:
            if rec.delivery_status in ['partially_delivered', 'delivered']:
                delivery = self.env['stock.picking'].search([('sale_id', '=', rec.id), ('picking_type_code', '=', 'outgoing')], limit=1)
                if delivery:
                    rec.delivered_date = delivery.date_done
