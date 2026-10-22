# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    move_invoice_user_id = fields.Many2one(
        comodel_name='res.users',
        related='move_id.invoice_user_id',
        string='Vendedor',
        readonly=True,
    )
