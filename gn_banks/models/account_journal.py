# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    bank_multi_sequence = fields.Boolean(string='Banks Multi Sequence', default=False)
    sequence_ids = fields.One2many("ir.sequence", "journal_id", "Sequences")