# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class ManualPaymentAccountMixin(models.AbstractModel):
    _name = 'gn.banks.manual_payment.mixin'
    _description = 'Manual Payment Account Helper'

    def _get_manual_payment_account_from_journal(self, journal, *, is_outbound, allow_empty=False):
        """Resolve the account used for Manual payment moves.

        Falls back to the journal outstanding or default account when the
        Manual payment method is not configured.
        """
        if not journal:
            return False

        method_lines = (
            journal.outbound_payment_method_line_ids
            if is_outbound
            else journal.inbound_payment_method_line_ids
        )
        manual_line = method_lines.filtered(
            lambda line: (line.payment_method_id.code or '').lower() == 'manual'
            or (line.payment_method_id.name or '').strip().lower() == 'manual'
        )[:1]

        account = manual_line.payment_account_id if manual_line else False
        if not account:
            account = journal.default_account_id

        if account or allow_empty:
            return account

        direction = _('outgoing') if is_outbound else _('incoming')
        raise UserError(
            _(
                "Please configure journal '%s' with the %s payment account or link one to the Manual payment method."
            )
            % (journal.display_name, direction)
        )

    def action_print_journal_entry(self):
        """PDF del asiento contable (wm_journal_entry_report)."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No hay asiento contable. Valide el documento primero."))
        report = self.env.ref('wm_journal_entry_report.account_journal_entry_report')
        return report.report_action(self.move_id)
