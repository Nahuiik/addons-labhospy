# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    account_move_line_id = fields.Many2one(string="Invoice Line Id", comodel_name='account.move.line',
                                           help="invoice line associated with the stock moves")
