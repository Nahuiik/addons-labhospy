# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models


class ResCompanyInherit(models.Model):
    _inherit = 'res.company'

    invoice = fields.Boolean(string="Create Stock Move Or Picking From Invoice",
                             help="create stock move or picking from invoice")
    create_stock_move_or_picking = fields.Selection(
        selection=[('create_stock_picking_from_invoice', 'Create Stock Picking From Invoice'),
                   ('create_stock_moves_from_invoice', 'Create Stock Moves From Invoice')],
        string="Create Stock Move Or Picking From Invoice")
    warehouse_id = fields.Many2one(comodel_name="stock.warehouse", string="Warehouse",
                                   help="select warehouse for which stock picking or move are created")
