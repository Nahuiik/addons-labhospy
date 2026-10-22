# -*- coding: utf-8 -*-
# See README.md: independent CE implementation; do not copy OEEL/OCA sources.

from odoo import models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def hn_action_open_reconcile(self):
        """Open unreconciled statement lines (checked & posted), same semantics as CE dashboard counter."""
        self.ensure_one()
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=_("Bank reconciliation"),
            default_context={
                "default_journal_id": self.id,
                "search_default_journal_id": self.id,
                "search_default_not_reconciled": 1,
            },
            kanban_first=True,
        )

    def hn_action_open_to_check(self):
        """Lines waiting for review (unchecked moves)."""
        self.ensure_one()
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=_("To review"),
            default_context={
                "default_journal_id": self.id,
                "search_default_journal_id": self.id,
                "search_default_to_check": 1,
            },
            kanban_first=True,
        )

    def hn_action_open_bank_transactions(self):
        """All statement lines for this journal (list-first)."""
        self.ensure_one()
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=_("Bank transactions"),
            default_context={
                "default_journal_id": self.id,
                "search_default_journal_id": self.id,
            },
            kanban_first=False,
        )

    def hn_action_open_reconcile_statement(self):
        self.ensure_one()
        statement_id = self.env.context.get("statement_id")
        if not statement_id:
            return False
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=_("Statement"),
            default_context={
                "default_journal_id": self.id,
                "search_default_journal_id": self.id,
                "search_default_statement_id": statement_id,
            },
            extra_domain=[("statement_id", "=", statement_id)],
            kanban_first=False,
        )
