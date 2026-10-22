# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Devintelle Software Solutions (<http://devintelle.com>).
#
##############################################################################
from odoo import api, fields, models


class PurchaseHistory(models.Model):
    _name = 'purchase.history'
    _rec_name = 'po_order'
    _order = 'id desc'
    _description = 'Purchase History'

    partner_id = fields.Many2one(
        'res.partner',
        string="Supplier",
        domain="[('supplier_rank', '>', 0)]",
    )
    order_date = fields.Datetime(string="Date")
    qty = fields.Float(string="Quantity")
    product_id = fields.Many2one('product.template', string='Product')
    po_order = fields.Many2one('purchase.order', string='Purchase Order')
    sale_order = fields.Many2one('sale.order', string='Sale Order Number')
    remark = fields.Char(string='Remark')
    price = fields.Float(string='Price')
    exclude_from_sale_price = fields.Boolean(string="Exclude From Sale Price")


class SaleHistory(models.Model):
    _name = 'sale.history'
    _rec_name = 'sale_order'
    _order = 'id desc'
    _description = 'Sale History'

    partner_id = fields.Many2one(
        'res.partner',
        string="Customer",
        domain="[('customer_rank', '>', 0)]",
    )
    order_date = fields.Datetime(string="Date")
    qty = fields.Float(string="Quantity")
    product_id = fields.Many2one('product.template', string='Product')
    sale_order = fields.Many2one('sale.order', string='Sale Order Number')
    remark = fields.Char(string='Remark')
    price = fields.Float(string='Price')
    exclude_from_sale_price = fields.Boolean(string="Exclude From Sale Price")


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    _description = 'Purchase Order'

    exclude_from_sale_price = fields.Boolean(string="Exclude From Sale Price")


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'

    exclude_from_sale_price = fields.Boolean(
        related='order_id.exclude_from_sale_price',
        string="Exclude From Sale Price",
        store=True,
        depends=['order_id.exclude_from_sale_price'],
    )

    # def write(self,vals):
    #     if not vals.get('price_unit'):
    #         for line in self:
    #             vals.update({'price_unit':line.price_unit,
    #                         'exclude_from_sale_price': line.order_id.exclude_from_sale_price})
    #     if vals.get('price_unit'):
    #         for line in self:
    #             vals_his={
    #                 'partner_id':line.order_id.partner_id.id or False,
    #                 'order_date':line.order_id.date_order or '',
    #                 'qty':line.product_qty or 0.0 ,
    #                 'product_id':line.product_id.product_tmpl_id.id or False,
    #                 'po_order' : line.order_id.id or False,
    #                 'price':vals['price_unit'] or 0.00,
    #                 'exclude_from_sale_price': line.order_id.exclude_from_sale_price
    #             }
    #         self.env['purchase.history'].create(vals_his)
    #             #line.product_id.product_tmpl_id._compute_sale_price()
    #     print('write ===============>>>')        
    #     res=super(purchase_order_line,self).write(vals)

    #     return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        PurchaseHistory = self.env['purchase.history']
        for line in lines:
            if not line.order_id or not line.product_id:
                continue
            history_vals = {
                'partner_id': line.order_id.partner_id.id or False,
                'order_date': line.order_id.date_order,
                'qty': line.product_qty,
                'product_id': line.product_id.product_tmpl_id.id,
                'po_order': line.order_id.id,
                'price': line.price_unit,
                'exclude_from_sale_price': line.order_id.exclude_from_sale_price,
            }
            PurchaseHistory.create(history_vals)
        return lines
        
        
        
#    def wkf_confirm_order(self, cr, uid, ids, context=None):
#        for purchase in self.browse(cr,uid,ids):
#            for line in purchase.order_line:
#                if line.product_id:
#                    vals={
#                        'partner_id':purchase.partner_id.id or False,
#                        'order_date':purchase.date_order or '',
#                        'qty':line.product_qty or 0.0,
#                        'product_id':line.product_id.product_tmpl_id.id or False,
#                    }
#                    self.pool.get('purchase.history').create(cr,uid,vals)
#        res=super(purchase_order,self).wkf_confirm_order(cr, uid, ids, context)
#        return res
