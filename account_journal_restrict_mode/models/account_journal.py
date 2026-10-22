# Copyright 2023 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import config


ENFORCED_TYPES = {"sale", "purchase", "general"}


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _is_restrict_mode_enforced(self):
        """Respect Odoo's test flag semantics before forcing the lock."""
        return not config["test_enable"] or (
            config["test_enable"]
            and self.env.context.get("test_account_journal_restrict_mode")
        )

    @api.constrains("restrict_mode_hash_table", "type")
    def _check_journal_restrict_mode(self):
        # Validación deshabilitada: Ya no es obligatorio tener el bloqueo de asientos activado
        # if not self._is_restrict_mode_enforced():
        #     return
        # for rec in self:
        #     if rec.type in ENFORCED_TYPES and not rec.restrict_mode_hash_table:
        #         raise UserError(
        #             self.env._(
        #                 "Journal %s must have Lock Posted Entries enabled."
        #             )
        #             % rec.name
        #         )
        pass

    def write(self, vals):
        # Validación deshabilitada: Ya no es obligatorio tener el bloqueo de asientos activado
        # if (
        #     self._is_restrict_mode_enforced()
        #     and vals.get("restrict_mode_hash_table") is False
        # ):
        #     for rec in self:
        #         if rec.type in ENFORCED_TYPES:
        #             raise UserError(
        #                 self.env._(
        #                     "Journal %s must have Lock Posted Entries enabled."
        #                 )
        #                 % rec.name
        #             )
        return super().write(vals)
