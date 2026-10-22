# -*- coding: utf-8 -*-
# Email: sales@creyox.com

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_merge_order_line(self):
        for order in self:
            lines = []
            dlt_lines = []
            if order:
                if order.state in ['done', 'cancel']:
                    raise ValidationError('Order might be in locked or cancel state!')
                elif order.state in ['draft', 'sent', 'purchase']:
                    for line in order.order_line:
                        if line:
                            same_line = self.env['purchase.order.line'].search(
                                [('order_id', '=', order.id), ('product_id', '=', line.product_id.id)])
                            if len(same_line) > 1 and same_line not in lines:
                                quantity = 0
                                dlt_lines.append(same_line - same_line[0])
                                lines.append(same_line)
                                for rec in same_line:
                                    quantity += rec.product_qty
                                same_line[0].product_qty = quantity
            if dlt_lines and order.state in ['draft', 'sent']:
                for dlt in dlt_lines:
                    dlt.product_qty = 0.0
                    dlt.unlink()
            elif dlt_lines and order.state == 'purchase':
                for dlt in dlt_lines:
                    dlt.product_qty = 0.0

    @api.model
    def create(self, vals):
        res = super(PurchaseOrder, self).create(vals)
        for rec in res:
            sale_line_merge = self.env['res.config.settings'].search([('po_merge_duplicate_line', '=', True)])
            if sale_line_merge:
                rec.action_merge_order_line()
        return res

    def write(self, values):
        res = super(PurchaseOrder, self).write(values)
        for rec in self:
            sale_line_merge = self.env['res.config.settings'].search([('po_merge_duplicate_line', '=', True)])
            if sale_line_merge:
                rec.action_merge_order_line()
        return res
