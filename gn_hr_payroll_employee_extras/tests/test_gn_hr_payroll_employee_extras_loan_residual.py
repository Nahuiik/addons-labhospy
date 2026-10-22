# -*- coding: utf-8 -*-
# Tests residuo como cuota adicional (campo loan_residual_amount).

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestGnHrLoanResidualExtraPayment(TransactionCase):
    def _create_loan(self, **extra):
        company = self.env["res.company"].create({"name": "Test Co loan residual"})
        emp = self.env["hr.employee"].create(
            {"name": "Residuo extra test", "company_id": company.id}
        )
        vals = {
            "name": "Préstamo residuo",
            "concept_type": "deduction",
            "amount_type": "fixed",
            "amount": 100.0,
            "is_loan": True,
            "installments": 10,
            "employee_id": emp.id,
            "date_start": date(2025, 1, 1),
        }
        vals.update(extra)
        return self.env["hr.employee.recurring.concept"].create(vals)

    def test_ten_fixed_plus_residual_fifty(self):
        """10 × 100 + 1 × 50 = 1050 (caso usuario)."""
        concept = self._create_loan(loan_residual_amount=50.0)
        self.assertTrue(concept.loan_has_residual)
        self.assertEqual(concept.total_amount, 1000.0)
        self.assertEqual(concept.loan_last_installment_amount, 50.0)
        self.assertEqual(concept.loan_total_payment_count, 11)
        self.assertEqual(concept._gn_loan_installment_amount(0), 100.0)
        self.assertEqual(concept._gn_loan_installment_amount(9), 100.0)
        self.assertEqual(concept._gn_loan_installment_amount(10), 50.0)
        concept.manual_paid_installments = 9
        self.assertEqual(concept.gn_next_deduction_amount, 100.0)
        self.assertEqual(concept.remaining_amount, 150.0)
        concept.manual_paid_installments = 10
        self.assertEqual(concept.gn_next_deduction_amount, 50.0)
        self.assertEqual(concept.remaining_amount, 50.0)

    def test_ten_fixed_plus_residual_hundred(self):
        concept = self._create_loan(amount=1000.0, loan_residual_amount=100.0)
        self.assertEqual(concept.total_amount, 10000.0)
        self.assertEqual(concept.loan_last_installment_amount, 100.0)
        self.assertEqual(concept.loan_total_payment_count, 11)
        concept.manual_paid_installments = 9
        self.assertEqual(concept._gn_effective_recurring_deduction_base(1000.0), 1000.0)
        concept.manual_paid_installments = 10
        self.assertEqual(concept._gn_effective_recurring_deduction_base(1000.0), 100.0)

    def test_no_residual_when_total_exact(self):
        concept = self._create_loan()
        self.assertEqual(concept.total_amount, 1000.0)
        self.assertFalse(concept.loan_has_residual)
        self.assertEqual(concept.loan_last_installment_amount, 0.0)
        self.assertEqual(concept.loan_total_payment_count, 10)
        for i in range(10):
            self.assertEqual(concept._gn_loan_installment_amount(i), 100.0)

    def test_rejects_negative_residual(self):
        with self.assertRaises(ValidationError):
            self._create_loan(loan_residual_amount=-1.0)
