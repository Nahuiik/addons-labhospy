# Copyright 2019 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.account.models.account_move import BYPASS_LOCK_CHECK


class AccountMove(models.Model):
    _inherit = "account.move"

    def _check_lock_to_dates(self):
        if self.env.context.get("bypass_lock_check") is BYPASS_LOCK_CHECK:
            return
        for move in self:
            journal = move.journal_id
            violated_lock_to_dates = move.company_id._get_lock_to_date_violations(
                move.date,
                fiscalyear=True,
                sale=journal and journal.type == "sale",
                purchase=journal and journal.type == "purchase",
                hard=True,
            )
            if violated_lock_to_dates:
                message = _(
                    "You cannot add/modify entries posterior to "
                    "and inclusive of: %(lock_date_info)s.",
                    lock_date_info=self.env["res.company"]._format_lock_dates(
                        violated_lock_to_dates
                    ),
                )
                raise UserError(message)
        return True

    def _check_fiscal_lock_dates(self):
        return self._check_lock_to_dates()

    def _get_violated_lock_dates(self, invoice_date, has_tax):
        self.ensure_one()
        locks = self.company_id._get_lock_to_date_violations(
            invoice_date,
            fiscalyear=True,
            sale=(self.journal_id and self.journal_id.type == "sale"),
            purchase=(self.journal_id and self.journal_id.type == "purchase"),
            tax=has_tax,
            hard=True,
        )
        locks.sort()
        return locks

    def action_post(self):
        self._check_lock_to_dates()
        return super().action_post()

    def button_cancel(self):
        self._check_lock_to_dates()
        return super().button_cancel()

    def button_draft(self):
        self._check_lock_to_dates()
        return super().button_draft()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _check_tax_lock_date(self):
        for line in self:
            move = line.move_id
            if move.state != "posted":
                continue
            violated_lock_to_dates = move.company_id._get_lock_to_date_violations(
                move.date,
                fiscalyear=False,
                sale=False,
                purchase=False,
                tax=True,
                hard=True,
            )
            if violated_lock_to_dates and line._affect_tax_report():
                message = _(
                    "The operation is refused as it would impact locked tax entries "
                    "posterior to and inclusive of: %(lock_date_info)s.",
                    lock_date_info=self.env["res.company"]._format_lock_dates(
                        violated_lock_to_dates
                    ),
                )
                raise UserError(message)
        return True
