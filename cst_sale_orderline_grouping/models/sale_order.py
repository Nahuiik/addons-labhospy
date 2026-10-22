# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        create_context = self.env.context.copy()
        create_context.update({'skip_create':True})
        records = super().create(vals_list)
        for order in records:
            order_line_vals = order.prepare_section_lines_vals()
            order.with_context(**create_context).write({'order_line': [(6, 0, 0)] + order_line_vals})
        return records

    def write(self, vals):
        res = super().write(vals)
        write_context = self.env.context.copy()
        write_context.update({'line_skip': True})
        for order in self:
            if not self.env.context.get('skip_create') and not self.env.context.get('line_skip'):
                order_line_vals = order.prepare_section_lines_vals()
                order.with_context(**write_context).write({'order_line': [(6, 0, 0)] + order_line_vals})
        return res

    def prepare_section_lines_vals(self):
        """
        :return: Displaying category wise grouping of Order lines
        """
        to_add_vals = []
        categorize_lines = {}
        section_names = set()
        for line in self.order_line:
            if line.display_type == 'line_section' or not line.product_id:
                continue
            category_name = line.product_id.categ_id.name or _('New Category')
            if category_name in section_names:
                categorize_lines[category_name].append(line)
            else:
                categorize_lines[category_name] = [line]
                section_names.add(category_name)
        sequence = 10
        for category, order_lines in categorize_lines.items():
            to_add_vals.append((0, 0, {
                'display_type': 'line_section',
                'name': category,
                'sequence': sequence,
            }))
            sequence += 1
            for order_line in order_lines:
                to_add_vals.append((0, 0, {
                    'product_id': order_line.product_id.id,
                    'product_uom_qty': order_line.product_uom_qty,
                    'price_unit': order_line.price_unit,
                    'name': order_line.name,
                    'order_id': self.id,
                    'tax_ids': [[6, 0, order_line.tax_ids.ids]],
                    'sequence': sequence,
                }))
                sequence += 1

        return to_add_vals

