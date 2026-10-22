# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    account_move_id = fields.Many2one(string='Invoice Id', comodel_name='account.move',
                                      help='invoice associated with the stock picking')
