# Copyright 2023 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountJournalRestrictMode(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_account_journal_restrict_mode=True,
            )
        )
        cls.account_journal_obj = cls.env["account.journal"]
        cls.company_obj = cls.env["res.company"]
        cls.currency_obj = cls.env["res.currency"]
        cls.chart_template_obj = cls.env["account.chart.template"]
        cls.country_be = cls.env.ref("base.be")  # Refs

    def test_journal_lock_requires_manual_opt_in(self):
        with self.assertRaises(UserError):
            self.account_journal_obj.create(
                {"name": "Test Journal", "code": "TJ", "type": "general"}
            )
        journal = self.account_journal_obj.create(
            {
                "name": "Test Journal 2",
                "code": "TJ2",
                "type": "general",
                "restrict_mode_hash_table": True,
            }
        )
        with self.assertRaises(UserError):
            journal.write({"restrict_mode_hash_table": False})
