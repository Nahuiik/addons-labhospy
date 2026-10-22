# -*- coding: utf-8 -*-

from odoo import models, fields


class Sequence(models.Model):
    _inherit = "ir.sequence"

    journal_id = fields.Many2one("account.journal", string="Journal")
    move_type = fields.Selection([
        ('debit', 'Débitos'),
        ('credit', 'Créditos'),
        ('deposit', 'Depósitos'),
        ('check', 'Cheques'),
        ('transference', 'Transferencias'),
        ('transference_banks', 'Transferencias entre Bancos'),
        ('credit_card', 'Credit Card'),
        ('otro', 'Otro'),
    ], string="Transaction Type")
