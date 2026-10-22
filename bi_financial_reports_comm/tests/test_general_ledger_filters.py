# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestGeneralLedgerFilters(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_notrack=True,
                no_reset_password=True,
                tracking_disable=True,
            )
        )
        cls.company = cls.env.company
        cls.receivable = cls.company_data["default_account_receivable"]
        cls.revenue = cls.company_data["default_account_revenue"]
        cls.journal = cls.company_data["default_journal_sale"]

    def _call_report(self, date_from=None, date_to=None, target_move="posted", display_account="movement", journal_ids=None):
        ctx = {
            "date_from": date_from or date.today(),
            "date_to": date_to or date.today(),
            "target_move": target_move,
            "display_account": display_account,
        }
        if journal_ids is not None:
            ctx["journal_ids"] = journal_ids
        return self.env["general.ledger.report"].with_context(ctx).get_data_general_ledger()

    def test_filter_posted_excludes_draft(self):
        """target_move=posted excluye asientos en borrador."""
        move_vals = {
            "journal_id": self.journal.id,
            "date": date.today(),
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 100, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 100}),
            ],
        }
        draft_move = self.env["account.move"].create(move_vals)
        self.assertEqual(draft_move.state, "draft")

        accounts, total_bal, total_cr, total_dr, total_neg, has_draft = self._call_report(
            target_move="posted"
        )
        # No debe haber líneas de ese asiento en borrador
        all_ids = []
        for acc in accounts:
            all_ids.extend([it["id"] for it in (acc.get("journal_items") or [])])
        draft_line_ids = draft_move.line_ids.ids
        for lid in draft_line_ids:
            self.assertNotIn(lid, all_ids, "Asiento en borrador no debe aparecer con target_move=posted")

    def test_filter_all_includes_draft(self):
        """target_move=all incluye asientos en borrador."""
        move_vals = {
            "journal_id": self.journal.id,
            "date": date.today(),
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 100, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 100}),
            ],
        }
        draft_move = self.env["account.move"].create(move_vals)
        self.assertEqual(draft_move.state, "draft")

        accounts, _, _, _, _, _ = self._call_report(target_move="all")
        all_ids = []
        for acc in accounts:
            all_ids.extend([it["id"] for it in (acc.get("journal_items") or [])])
        draft_line_ids = draft_move.line_ids.ids
        found = any(lid in all_ids for lid in draft_line_ids)
        self.assertTrue(found, "Asiento en borrador debe aparecer con target_move=all")

    def test_has_draft_warning_when_drafts_exist(self):
        """has_draft_warning True cuando hay asientos en borrador en el período."""
        move_vals = {
            "journal_id": self.journal.id,
            "date": date.today(),
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 50, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 50}),
            ],
        }
        self.env["account.move"].create(move_vals)

        _, _, _, _, _, has_draft = self._call_report(target_move="posted")
        self.assertTrue(has_draft, "Debería activarse has_draft_warning cuando hay asientos en borrador")

    def test_no_draft_warning_when_no_drafts(self):
        """has_draft_warning False cuando no hay asientos en borrador."""
        move_vals = {
            "journal_id": self.journal.id,
            "date": date.today(),
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 100, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 100}),
            ],
        }
        move = self.env["account.move"].create(move_vals)
        move.action_post()

        _, _, _, _, _, has_draft = self._call_report(target_move="posted")
        self.assertFalse(has_draft, "No debe haber advertencia cuando no hay borradores")

    def test_filter_by_date_range(self):
        """Filtro de rango de fechas limita los apuntes al período."""
        dt_inside = date.today()
        move_vals = {
            "journal_id": self.journal.id,
            "date": dt_inside,
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 200, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 200}),
            ],
        }
        move = self.env["account.move"].create(move_vals)
        move.action_post()

        from_date = date(dt_inside.year, dt_inside.month, 1)
        to_date = dt_inside

        accounts, total_balance, total_cr, total_dr, _, _ = self._call_report(
            date_from=from_date,
            date_to=to_date,
        )
        self.assertGreater(len(accounts), 0, "Debe haber cuentas con movimiento en el período")
        # Verificar que los totales reflejan el asiento
        self.assertIn("200", str(total_dr) or str(total_cr), "Total debe incluir el asiento del período")

    def test_filter_by_journal(self):
        """Filtro por diarios limita a los apuntes de esos diarios."""
        move_vals = {
            "journal_id": self.journal.id,
            "date": date.today(),
            "line_ids": [
                (0, 0, {"account_id": self.receivable.id, "debit": 100, "credit": 0}),
                (0, 0, {"account_id": self.revenue.id, "debit": 0, "credit": 100}),
            ],
        }
        move = self.env["account.move"].create(move_vals)
        move.action_post()

        journals = self.env["account.journal"].search([("company_id", "=", self.company.id)], limit=2)
        journal_ids = journals.ids
        if self.journal.id in journal_ids:
            accounts, _, _, _, _, _ = self._call_report(journal_ids=journal_ids)
            all_journal_codes = set()
            for acc in accounts:
                for it in (acc.get("journal_items") or []):
                    if it.get("journal_id"):
                        all_journal_codes.add(it["journal_id"])
            self.assertTrue(
                any(
                    self.journal.code == jc
                    for jc in all_journal_codes
                ),
                "Debe incluir apuntes del diario filtrado",
            )
