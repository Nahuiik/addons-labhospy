# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, Command
from odoo.exceptions import ValidationError


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    stock_picking_count = fields.Integer(string="Total Stock Pickings", help="Delivery count",
                                         compute="compute_stock_picking_count", default=0)
    stock_move_count = fields.Integer(string="Total Stock Move", help="Stock Move Count",
                                      compute='compute_stock_move_count', default=0)

    def action_post(self):
        res = super(AccountMoveInherit, self).action_post()
        move_or_picking_boolean = self.env.company.invoice
        if move_or_picking_boolean:
            move_or_picking = self.env.company.create_stock_move_or_picking
            warehouse = self.company_id.warehouse_id

            location_id = location_dest_id = picking_type = False

            if self.move_type == 'out_invoice':
                picking_type = warehouse.out_type_id.id
                location_id = warehouse.lot_stock_id.id
                location_dest_id = self.partner_id.property_stock_customer.id
            elif self.move_type == 'in_invoice':
                picking_type = warehouse.in_type_id.id
                location_id = self.partner_id.property_stock_supplier.id
                location_dest_id = warehouse.lot_stock_id.id
            elif self.move_type in ['out_refund', 'in_refund']:
                # optional: handle refunds if required
                picking_type = warehouse.in_type_id.id if self.move_type == 'out_refund' else warehouse.out_type_id.id
                location_id = warehouse.lot_stock_id.id
                location_dest_id = self.partner_id.property_stock_supplier.id
            else:
                # skip creating stock records for unsupported move types
                return res

            if move_or_picking == 'create_stock_picking_from_invoice':
                stock_move_data = []
                for move in self.invoice_line_ids:
                    stock_move_data.append(Command.create({
                        'product_id': move.product_id.id,
                        'quantity': move.quantity,
                        'product_uom_id': move.product_uom_id.id,
                        'reference': f"{move.product_id.name}",
                        'location_id': location_id,
                        'location_dest_id': location_dest_id,
                    }))

                self.env['stock.picking'].create({
                    'partner_id': self.partner_id.id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'picking_type_id': picking_type,
                    'move_type': 'direct',
                    'scheduled_date': self.invoice_date,
                    'move_line_ids': stock_move_data,
                    'account_move_id': self.id
                })
            elif move_or_picking == 'create_stock_moves_from_invoice':
                for move in self.invoice_line_ids:
                    self.env['stock.move'].create({
                        'product_id': move.product_id.id,
                        'product_uom_qty': move.quantity,
                        'product_uom': move.product_uom_id.id,
                        'name': f"{move.product_id.name}",
                        'location_id': location_id,
                        'location_dest_id': location_dest_id,
                        'account_move_line_id': move.id,
                    })
        return res

    def compute_stock_picking_count(self):
        picking_count = 0
        for invoice in self:
            picking_count = self.env['stock.picking'].search_count([('account_move_id', '=', invoice.id)])
        self.stock_picking_count = picking_count

    def compute_stock_move_count(self):
        move_count = 0
        for invoice in self:
            line_ids = invoice.invoice_line_ids.mapped('id')
            move_count = self.env['stock.move'].search_count([('account_move_line_id', 'in', line_ids)])
        self.stock_move_count = move_count

    def action_show_stock_picking(self):
        stock_pickings = self.env['stock.picking'].search([('account_move_id', '=', self.id)])
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        if len(stock_pickings) > 1:
            action['domain'] = [('id', 'in', stock_pickings.ids)]
        elif len(stock_pickings) == 1:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['views'] = form_view
            action['res_id'] = stock_pickings.id
        else:
            raise ValidationError("System couldn't find Delivery Order !!")
        return action

    def action_show_stock_move(self):
        line_ids = self.invoice_line_ids.mapped('id')
        stock_move = self.env['stock.move'].search([('account_move_line_id', 'in', line_ids)])
        action = self.env['ir.actions.act_window']._for_xml_id('stock.stock_move_action')
        if len(stock_move) > 1:
            action['domain'] = [('id', 'in', stock_move.ids)]
        elif len(stock_move) == 1:
            form_view = [(self.env.ref('stock.view_move_form').id, 'form')]
            action['views'] = form_view
            action['res_id'] = stock_move.id
        else:
            raise ValidationError("System couldn't find Stock Moves !!")
        return action
