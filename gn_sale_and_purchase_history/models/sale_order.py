from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _description = 'Sale Order'
    
    exclude_from_sale_price = fields.Boolean(string="Exclude From Sale Price")

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'

    exclude_from_sale_price = fields.Boolean(
        related='order_id.exclude_from_sale_price',
        string="Exclude From Sale Price",
        store=True,
        depends=['order_id.exclude_from_sale_price'],
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        SaleHistory = self.env['sale.history']
        for line in lines:
            if not line.order_id or not line.product_id:
                continue
            history_vals = {
                'partner_id': line.order_id.partner_id.id or False,
                'order_date': line.order_id.date_order,
                'qty': line.product_uom_qty,
                'product_id': line.product_id.product_tmpl_id.id,
                'sale_order': line.order_id.id,
                'price': line.price_unit,
                'exclude_from_sale_price': line.order_id.exclude_from_sale_price,
            }
            SaleHistory.create(history_vals)
        return lines
        
        
