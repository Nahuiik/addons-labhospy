# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAccountReportBranchDomain(TransactionCase):
    def test_res_branch_domain_respects_selection(self):
        Report = self.env["account.report"]
        report = Report.new({"filter_res_branch": True})
        self.assertEqual(
            report._get_options_res_branch_domain({"res_branch_ids": []}),
            Domain.TRUE,
        )
        dom = report._get_options_res_branch_domain({"res_branch_ids": [1, 2]})
        self.assertEqual(dom, Domain("branch_id", "in", [1, 2]))

    def test_res_branch_domain_disabled_when_filter_off(self):
        report = self.env["account.report"].new({"filter_res_branch": False})
        self.assertEqual(
            report._get_options_res_branch_domain({"res_branch_ids": [99]}),
            Domain.TRUE,
        )
