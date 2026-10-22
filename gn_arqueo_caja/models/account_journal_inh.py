# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class AccountJournalInh(models.Model):
    _inherit = "account.journal"

    receipt_in_advance = fields.Boolean(string="Recibo por Anticipado", help="Marcar si este diario se usa para recibos por anticipado")

