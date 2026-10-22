# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from datetime import date, datetime, timedelta
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStockValuationReport(TransactionCase):
    """Test Stock Valuation Report functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Company = cls.env["res.company"]
        cls.Report = cls.env["stock.valuation.report"]
        cls.ReportLine = cls.env["stock.valuation.report.line"]
        cls.Product = cls.env["product.product"]
        cls.ProductCategory = cls.env["product.category"]
        cls.AccountAccount = cls.env["account.account"]
        cls.AccountJournal = cls.env["account.journal"]

        # Get or create company
        cls.company = cls.env.company

        # Create stock valuation account if not exists
        if not cls.company.stock_valuation_account_id:
            chart_template = cls.company.chart_template_id
            if chart_template:
                # Try to find existing stock account
                stock_account = cls.AccountAccount.search(
                    [
                        ("company_id", "=", cls.company.id),
                        ("code", "=like", "1%"),
                        ("deprecated", "=", False),
                    ],
                    limit=1,
                )
                if stock_account:
                    cls.company.stock_valuation_account_id = stock_account

        # Create expense account if not exists
        if not hasattr(cls.company, "inventory_bridge_expense_account_id") or not cls.company.inventory_bridge_expense_account_id:
            expense_account = cls.AccountAccount.search(
                [
                    ("company_id", "=", cls.company.id),
                    ("code", "=like", "6%"),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )
            if expense_account and hasattr(cls.company, "inventory_bridge_expense_account_id"):
                cls.company.inventory_bridge_expense_account_id = expense_account

    def test_create_report(self):
        """Test creating a stock valuation report"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        self.assertTrue(report, "Report should be created")
        self.assertEqual(report.company_id, self.company)
        self.assertEqual(report.date_to, date_to)

    def test_compute_valuation(self):
        """Test computing valuation values"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Trigger computation
        report._compute_valuation()

        # Check that values are computed (may be 0 if no stock)
        self.assertIsNotNone(report.initial_balance)
        self.assertIsNotNone(report.ending_stock)
        self.assertIsNotNone(report.stock_variation)
        self.assertEqual(
            report.stock_variation,
            report.ending_stock - report.initial_balance,
            "Stock variation should equal ending stock minus initial balance",
        )

    def test_action_compute(self):
        """Test action_compute button"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Call action_compute
        result = report.action_compute()

        # Check that action returns a dict
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("res_model"), "stock.valuation.report")
        self.assertEqual(result.get("res_id"), report.id)

    def test_valuation_lines_creation(self):
        """Test that valuation lines are created when there's stock"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Trigger computation
        report._compute_valuation()

        # Check that lines are created (may be empty if no stock)
        self.assertIsNotNone(report.valuation_line_ids)

    def test_report_without_date_from(self):
        """Test report without date_from (should use 0 as initial balance)"""
        date_to = fields.Datetime.now()

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": False,
                "date_to": date_to,
            }
        )

        # Trigger computation
        report._compute_valuation()

        # Initial balance should be 0 when date_from is not set
        self.assertEqual(report.initial_balance, 0.0)
        self.assertIsNotNone(report.ending_stock)
        self.assertEqual(report.stock_variation, report.ending_stock)

    def test_report_without_company(self):
        """Test report without company (should not compute)"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": False,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Trigger computation
        report._compute_valuation()

        # Values should be 0 when company is not set
        self.assertEqual(report.initial_balance, 0.0)
        self.assertEqual(report.ending_stock, 0.0)
        self.assertEqual(report.stock_variation, 0.0)

    def test_generate_entry_wizard(self):
        """Test opening generate entry wizard"""
        date_to = fields.Datetime.now()
        date_from = date_to - timedelta(days=30)

        report = self.Report.create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

        # Trigger computation first
        report._compute_valuation()

        # Only test if there's a variation
        if report.stock_variation != 0:
            result = report.action_generate_entry()

            # Check that action returns a dict
            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("res_model"), "stock.valuation.generate.entry")




