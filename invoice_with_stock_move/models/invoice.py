# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _get_default_warehouse(self):
        return self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.user.company_id.id)],
            limit=1,
        )

    @api.model
    def _get_default_picking_type_id(self):
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.user.company_id.id)],
            limit=1,
        )
        move_type = self.env.context.get('default_move_type')
        if not (warehouse and move_type):
            return False
        if move_type == 'out_invoice':
            return warehouse.out_type_id.id
        if move_type == 'in_invoice':
            return warehouse.in_type_id.id
        if move_type == 'out_refund':
            return warehouse.in_type_id.id
        if move_type == 'in_refund':
            return warehouse.out_type_id.id
        return False

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        default=_get_default_warehouse,
    )
    create_stock_moves = fields.Boolean(
        "Create Stock Moves?",
        copy=False,
        default=True,
    )
    picking_id = fields.Many2one('stock.picking', 'Picking', copy=False)
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        'Picking Type',
        copy=False,
        default=_get_default_picking_type_id,
    )
    acs_location_id = fields.Many2one('stock.location', 'Src Location', copy=False)
    acs_location_dest_id = fields.Many2one('stock.location', 'Destination Location', copy=False)

    @api.onchange('warehouse_id', 'picking_type_id', 'move_type', 'create_stock_moves')
    def onchange_warehouse(self):
        if not self.warehouse_id:
            return

        partner = self.partner_id
        move_type = self.move_type
        if move_type == 'out_invoice':
            self.picking_type_id = self.warehouse_id.out_type_id.id
            self.acs_location_id = self.warehouse_id.lot_stock_id.id
            self.acs_location_dest_id = partner.property_stock_customer.id if partner else False
        elif move_type == 'in_invoice':
            self.picking_type_id = self.warehouse_id.in_type_id.id
            self.acs_location_id = partner.property_stock_supplier.id if partner else False
            self.acs_location_dest_id = self.warehouse_id.lot_stock_id.id
        elif move_type == 'out_refund':
            self.picking_type_id = self.warehouse_id.in_type_id.id
            self.acs_location_id = partner.property_stock_customer.id if partner else False
            self.acs_location_dest_id = self.warehouse_id.lot_stock_id.id
        elif move_type == 'in_refund':
            self.picking_type_id = self.warehouse_id.out_type_id.id
            self.acs_location_id = self.warehouse_id.lot_stock_id.id
            self.acs_location_dest_id = partner.property_stock_supplier.id if partner else False

    # Hook: Allow to change in other module
    @api.model
    def assign_invoice_lots(self, picking):
        pass

    def _get_invoice_datetime(self):
        """Return a datetime with invoice_date combined with current time."""
        invoice_date = self.invoice_date or fields.Date.context_today(self)
        if isinstance(invoice_date, str):
            invoice_date = fields.Date.to_date(invoice_date)
        now_dt = fields.Datetime.to_datetime(fields.Datetime.now())
        return datetime.combine(invoice_date, now_dt.time())

    def move_line_from_invoice_lines(self, picking, location_id, location_dest_id):
        invoice_datetime = self._get_invoice_datetime()
        invoice_date = invoice_datetime.date()
        self = self.with_context(invoice_date=invoice_date, combined_date=invoice_datetime)
        created_move = False
        for line in self.invoice_line_ids:
            product = line.product_id
            if product and product.type != 'service':
                created_move = self.env['stock.move'].create({
                    'product_id': product.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id.id,
                    'date': invoice_datetime,
                    'force_invoice_date': invoice_date,
                    'picking_id': picking.id,
                    'picking_type_id': picking.picking_type_id.id,
                    'state': 'draft',
                    'description_picking': line.name,
                    'location_id': location_id.id,
                    'location_dest_id': location_dest_id.id,
                })
        self.invoice_line_ids.write({'date': invoice_date})
        return created_move

    def acs_create_picking(self, picking_type_id, location_id, location_dest_id):
        invoice_datetime = self._get_invoice_datetime()
        invoice_date = invoice_datetime.date()

        picking_vals = {
            'partner_id': self.partner_id.id,
            'force_invoice_date': invoice_date,
            'scheduled_date': invoice_datetime,
            'company_id': self.company_id.id,
            'picking_type_id': picking_type_id.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'move_type': 'direct',
            'origin': self.name,
        }
        if 'branch_id' in self._fields:
            picking_vals['branch_id'] = self.branch_id.id

        picking = self.env['stock.picking'].create(picking_vals)
        self.picking_id = picking.id
        picking.write({'scheduled_date': invoice_datetime})
        self.move_line_from_invoice_lines(picking, location_id, location_dest_id)

        picking.action_confirm()
        picking.action_assign()
        self.assign_invoice_lots(picking)
        if picking.state == 'assigned':
            for move in picking.move_lines.filtered(lambda m: m.state not in ['done', 'cancel']):
                for move_line in move.move_line_ids:
                    move_line.qty_done = move_line.product_uom_qty
                    move_line.write({'date': invoice_datetime or self.invoice_date})
                move.write({'force_invoice_date': invoice_date})
            picking.button_validate()
            picking.move_ids_without_package.write({'date': invoice_datetime})

    def action_post(self):
        res = super().action_post()
        for inv in self:
            if inv.move_type == 'out_invoice':
                has_stockable_products = inv.check_can_create_stock_move()
                all_services = all(line.product_id.type == 'service' for line in inv.invoice_line_ids)
                inv.create_stock_moves = has_stockable_products and not all_services
                if inv.create_stock_moves:
                    if not (inv.picking_type_id and inv.acs_location_id and inv.acs_location_dest_id):
                        inv.onchange_warehouse()
                    if inv.picking_type_id and inv.acs_location_id and inv.acs_location_dest_id:
                        inv.acs_create_picking(inv.picking_type_id, inv.acs_location_id, inv.acs_location_dest_id)
        return res

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            if move.picking_id:
                move.picking_id.action_cancel()
        return res

    def check_can_create_stock_move(self):
        types = self.invoice_line_ids.mapped('product_id.type')
        return any(product_type in ('product', 'consu') for product_type in types)

    delivery_count = fields.Integer(string='Delivery Orders', compute='_compute_picking_ids')

    def action_view_delivery(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        if self.picking_id:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = self.picking_id.id
            action['context'] = {
                **self._context,
                'default_partner_id': self.partner_id.id,
                'default_picking_type_id': self.picking_id.picking_type_id.id,
                'default_origin': self.name,
            }
        else:
            action['domain'] = [('id', '=', False)]
        return action

    @api.depends('picking_id')
    def _compute_picking_ids(self):
        for move in self:
            move.delivery_count = 1 if move.picking_id else 0


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    force_invoice_date = fields.Date(string="Force Invoice Date")


class StockMove(models.Model):
    _inherit = 'stock.move'

    force_invoice_date = fields.Date(string="Force Invoice Date")
