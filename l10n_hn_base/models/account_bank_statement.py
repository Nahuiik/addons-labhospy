# -*- coding: utf-8 -*-
# See README.md: independent CE implementation; do not copy OEEL/OCA sources.

from odoo import models, _


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def hn_action_open_bank_reconciliation(self):
        self.ensure_one()
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=self.name or _("Bank reconciliation"),
            default_context={
                "search_default_statement_id": self.id,
                "search_default_journal_id": self.journal_id.id,
                "default_journal_id": self.journal_id.id,
            },
            extra_domain=[("statement_id", "=", self.id)],
            kanban_first=True,
        )
