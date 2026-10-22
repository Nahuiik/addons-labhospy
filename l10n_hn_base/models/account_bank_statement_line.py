# -*- coding: utf-8 -*-
# See README.md: independent CE implementation; do not copy OEEL/OCA sources.

import ast

from odoo import api, models, _


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    @api.model
    def hn_open_bank_reconciliation_action(
        self,
        default_context=None,
        extra_domain=None,
        name=None,
        kanban_first=True,
    ):
        """Build the main CE window action for bank matching (list + kanban), independent of OCA/Enterprise."""
        if default_context is None:
            default_context = {}
        if extra_domain is None:
            extra_domain = []
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_hn_base.action_bank_statement_line_hn_kanban"
            if kanban_first
            else "l10n_hn_base.action_bank_statement_line_hn_list"
        )
        action = dict(action)
        journal_id = default_context.get("default_journal_id") or default_context.get(
            "search_default_journal_id"
        )
        journal = self.env["account.journal"].browse(journal_id) if journal_id else self.env["account.journal"]
        ctx = {}
        raw_ctx = action.get("context")
        if isinstance(raw_ctx, str):
            try:
                ctx = ast.literal_eval(raw_ctx.strip() or "{}")
            except (ValueError, SyntaxError):
                ctx = {}
        elif isinstance(raw_ctx, dict):
            ctx = dict(raw_ctx)
        ctx.update(
            {
                **default_context,
                "hn_bank_rec_journal_id": journal_id,
                "bank_statements_source": journal[:1].bank_statements_source,
            }
        )
        action["name"] = name or action.get("name") or _("Bank matching")
        action["context"] = ctx
        base_domain = [("state", "!=", "cancel")]
        action["domain"] = base_domain + extra_domain
        return action

    def action_hn_open_reconciliation(self):
        self.ensure_one()
        return self.env["account.bank.statement.line"].hn_open_bank_reconciliation_action(
            name=self.payment_ref or _("Transaction"),
            default_context={
                "default_statement_id": self.statement_id.id,
                "default_journal_id": self.journal_id.id,
                "search_default_journal_id": self.journal_id.id,
                "search_default_id": self.id,
            },
            extra_domain=[("id", "=", self.id)],
            kanban_first=True,
        )

    def action_hn_open_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
