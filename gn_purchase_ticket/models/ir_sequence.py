# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Sequence(models.Model):
    _inherit = "ir.sequence"

    move_type = fields.Selection(selection_add=[('purchase_ticket', 'Purchase Ticket')])
    is_purchase_ticket = fields.Boolean(string="Purchase Ticket")

    @api.onchange('move_type')
    def change_move_type(self):
        if self.move_type == 'purchase_ticket':
            self.is_purchase_ticket = True
        else:
            self.is_purchase_ticket = False

