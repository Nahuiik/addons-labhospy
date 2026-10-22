# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from datetime import date
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestGnHrPayrollEmployeeExtras(TransactionCase):
    def test_document_type_and_employee_document(self):
        company = self.env.company
        dt = self.env["hr.document.type"].create(
            {
                "name": "Test tipo documento GN",
                "is_required": True,
                "company_id": company.id,
            }
        )
        emp = self.env["hr.employee"].create(
            {"name": "Empleado GN test", "company_id": company.id}
        )
        doc = self.env["hr.employee.document"].create(
            {
                "employee_id": emp.id,
                "document_type_id": dt.id,
            }
        )
        self.assertTrue(doc)
        self.assertTrue(doc.is_missing)

    def test_recurring_concept_create(self):
        company = self.env.company
        emp = self.env["hr.employee"].create(
            {"name": "Empleado recurrente GN", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Bonificación test",
                "concept_type": "income",
                "amount_type": "fixed",
                "amount": 50.0,
                "employee_id": emp.id,
            }
        )
        self.assertEqual(concept.employee_id, emp)
        self.assertEqual(concept.company_id, company)

    def test_recurring_concept_create_from_template_without_name(self):
        """Lista editable del empleado: name readonly no se envía al guardar."""
        company = self.env["res.company"].create({"name": "Test Co recurring tpl"})
        emp = self.env["hr.employee"].create(
            {"name": "Empleado plantilla inline", "company_id": company.id}
        )
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Préstamo empresa",
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 100.0,
                "is_template": True,
                "is_loan": True,
                "company_id": company.id,
            }
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name_from_concept_id": tpl.id,
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "is_loan": True,
                "installments": 10,
                "amount": 100.0,
                "date_start": date(2026, 5, 27),
                "date_end": date(2026, 10, 15),
                "apply_biweek": "both",
            }
        )
        self.assertEqual(concept.name, tpl.name)
        self.assertEqual(concept.code, tpl.code)
        self.assertEqual(concept.amount, 100.0)
        self.assertEqual(concept.total_amount, 1000.0)

    def test_recurring_concept_apply_biweek_preserves_amount(self):
        """Cambiar quincena no debe borrar el monto (lista embebida / formulario)."""
        company = self.env.company
        emp = self.env["hr.employee"].create(
            {"name": "Empleado quincena monto", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name": "Cuota sindical",
                "code": "SIND_TEST",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 12.5,
                "date_start": date(2026, 5, 1),
                "date_end": date(2026, 12, 31),
                "apply_biweek": "both",
            }
        )
        concept.write({"apply_biweek": "first", "amount": 0.0})
        self.assertEqual(concept.amount, 12.5)
        concept.write({"apply_biweek": "second"})
        self.assertEqual(concept.amount, 12.5)

    def test_recurring_concept_loan_split_preserves_amount(self):
        company = self.env.company
        emp = self.env["hr.employee"].create(
            {"name": "Empleado split toggle", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name": "Cuota",
                "code": "SPLIT_TOGGLE",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 250.0,
                "date_start": date(2026, 1, 1),
                "apply_biweek": "both",
            }
        )
        concept.write({"loan_split_quota_across_biweeks": True, "amount": 0.0})
        self.assertEqual(concept.amount, 250.0)
        concept.write(
            {
                "loan_first_biweek_amount": 150.0,
                "loan_split_quota_across_biweeks": True,
                "amount": 0.0,
            }
        )
        self.assertEqual(concept.amount, 250.0)
        self.assertEqual(concept.loan_first_biweek_amount, 150.0)

    def test_recurring_concept_template_preserves_amount(self):
        company = self.env.company
        emp = self.env["hr.employee"].create(
            {"name": "Empleado plantilla monto", "company_id": company.id}
        )
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Plantilla sin monto",
                "code": "TPL_ZERO_AMT",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 0.0,
                "is_template": True,
                "company_id": company.id,
            }
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name": "Cuota manual",
                "code": "MANUAL_AMT",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 250.0,
                "date_start": date(2026, 1, 1),
            }
        )
        concept.write({"name_from_concept_id": tpl.id, "amount": 0.0})
        self.assertEqual(concept.amount, 250.0)
        self.assertEqual(concept.name, tpl.name)
        self.assertEqual(concept.code, tpl.code)

        tpl_with_amount = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Plantilla con monto",
                "code": "TPL_WITH_AMT",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 12.5,
                "is_template": True,
                "company_id": company.id,
            }
        )
        empty = self.env["hr.employee.recurring.concept"].new(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "date_start": date(2026, 1, 1),
            }
        )
        empty.name_from_concept_id = tpl_with_amount
        empty._onchange_name_from_concept_id()
        self.assertEqual(empty.amount, 12.5)

    def test_recurring_concept_biweek_split_non_loan(self):
        """Deducción 250/mes: 150 en 1.ª quincena y 100 en 2.ª con un solo concepto."""
        company = self.env.company
        emp = self.env["hr.employee"].create(
            {"name": "Empleado split quincena", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name": "Cuota sindical",
                "code": "SIND_SPLIT",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 250.0,
                "date_start": date(2026, 1, 1),
                "date_end": date(2026, 12, 31),
                "apply_biweek": "both",
                "loan_split_quota_across_biweeks": True,
                "loan_first_biweek_amount": 150.0,
            }
        )
        self.assertEqual(concept.loan_second_biweek_reference, 100.0)
        with patch.object(
            type(concept),
            "_gn_employee_version_is_biweekly",
            return_value=True,
        ):
            q1 = concept._gn_apply_loan_biweek_split_to_amount(
                250.0, emp, date(2026, 1, 1)
            )
            q2 = concept._gn_apply_loan_biweek_split_to_amount(
                250.0, emp, date(2026, 1, 16)
            )
        self.assertEqual(q1, 150.0)
        self.assertEqual(q2, 100.0)

    def test_recurring_concept_loan_template_with_residual(self):
        """10 × 10 + residuo 5: total calculado y cuota extra."""
        company = self.env["res.company"].create({"name": "Test Co loan residual"})
        emp = self.env["hr.employee"].create(
            {"name": "Empleado préstamo residuo", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name": "Préstamo con residuo",
                "code": "PRESTAMO_R",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "is_loan": True,
                "amount": 10.0,
                "installments": 10,
                "loan_residual_amount": 5.0,
                "date_start": date(2026, 5, 27),
                "date_end": date(2026, 10, 15),
                "apply_biweek": "both",
            }
        )
        self.assertEqual(concept.total_amount, 100.0)
        self.assertEqual(concept.loan_last_installment_amount, 5.0)
        self.assertEqual(concept.loan_total_payment_count, 11)
        self.assertEqual(concept.remaining_amount, 105.0)
        self.assertEqual(concept.gn_next_deduction_amount, 10.0)

    def test_recurring_concept_loan_template_zero_amount_single_installment(self):
        """Cuota y monto deben indicarse; total = monto × cuotas."""
        company = self.env["res.company"].create({"name": "Test Co loan tpl zero"})
        emp = self.env["hr.employee"].create(
            {"name": "Empleado préstamo 1 cuota", "company_id": company.id}
        )
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Préstamo Personal",
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 0.0,
                "is_template": True,
                "is_loan": True,
                "company_id": company.id,
            }
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name_from_concept_id": tpl.id,
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "is_loan": True,
                "installments": 1,
                "amount": 10.0,
                "date_start": date(2026, 5, 27),
                "date_end": date(2026, 5, 31),
                "apply_biweek": "both",
            }
        )
        self.assertEqual(concept.name, "Préstamo Personal")
        self.assertEqual(concept.amount, 10.0)
        self.assertEqual(concept.total_amount, 10.0)

    def test_recurring_concept_loan_template_ten_installments(self):
        """10 cuotas de 10 → total 100."""
        company = self.env["res.company"].create({"name": "Test Co loan 10x"})
        emp = self.env["hr.employee"].create(
            {"name": "Empleado préstamo 10 cuotas", "company_id": company.id}
        )
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Préstamo Personal",
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 0.0,
                "is_template": True,
                "is_loan": True,
                "company_id": company.id,
            }
        )
        concept = self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": emp.id,
                "company_id": company.id,
                "name_from_concept_id": tpl.id,
                "code": "PRESTAMO",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "is_loan": True,
                "installments": 10,
                "amount": 10.0,
                "date_start": date(2026, 5, 27),
                "date_end": date(2026, 10, 15),
                "apply_biweek": "both",
            }
        )
        self.assertEqual(concept.amount, 10.0)
        self.assertEqual(concept.total_amount, 100.0)

    def test_recurring_concept_template_no_employee(self):
        company = self.env.company
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Plantilla sindical",
                "code": "TPL_SIND_TEST",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 5.0,
                "is_template": True,
                "company_id": company.id,
            }
        )
        self.assertTrue(tpl.is_template)
        self.assertFalse(tpl.employee_id)
        self.assertEqual(tpl.company_id, company)

    def test_recurring_concept_template_rejects_employee(self):
        emp = self.env["hr.employee"].create({"name": "Emp plantilla GN"})
        with self.assertRaises(ValidationError):
            self.env["hr.employee.recurring.concept"].create(
                {
                    "name": "Inválido",
                    "code": "BAD_TPL",
                    "concept_type": "deduction",
                    "amount_type": "fixed",
                    "amount": 1.0,
                    "is_template": True,
                    "employee_id": emp.id,
                    "company_id": self.env.company.id,
                }
            )

    def test_recurring_concept_template_loan_clears_schedule(self):
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Préstamo plantilla",
                "code": "TPL_LOAN_SCHED",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 100.0,
                "is_template": True,
                "is_loan": True,
                "company_id": self.env.company.id,
            }
        )
        self.assertEqual(tpl.installments, 0)
        self.assertEqual(tpl.initial_paid_installments, 0)
        self.assertEqual(tpl.manual_paid_installments, 0)
        self.assertFalse(tpl.date_start)
        self.assertFalse(tpl.date_end)

    def test_recurring_concept_mass_assign_company_inline(self):
        company = self.env.company
        e1 = self.env["hr.employee"].create(
            {"name": "Masivo E1", "company_id": company.id}
        )
        e2 = self.env["hr.employee"].create(
            {"name": "Masivo E2", "company_id": company.id}
        )
        code = "MASIVO_SIND_01_TEST"
        wiz = self.env["hr.employee.recurring.concept.assign.wizard"].create(
            {
                "assignment_scope": "employees",
                "company_id": company.id,
                "employee_ids": [(6, 0, (e1 | e2).ids)],
                "source_mode": "inline",
                "inline_name": "Cuota sindical masiva",
                "inline_code": code,
                "inline_concept_type": "deduction",
                "inline_amount_type": "fixed",
                "assign_amount": 5.0,
                "assign_apply_biweek": "both",
            }
        )
        wiz.action_assign()
        lines = self.env["hr.employee.recurring.concept"].search(
            [("code", "=", code), ("employee_id", "in", (e1 | e2).ids)]
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].amount, 5.0)
        self.assertEqual(lines[0].apply_biweek, "both")
        self.assertEqual(lines[0].company_id, company)
        self.assertEqual(lines[1].company_id, company)

    def test_recurring_concept_count_application_periods(self):
        Rec = self.env["hr.employee.recurring.concept"]
        n_jan_both = Rec.count_application_periods(
            date(2025, 1, 1), date(2025, 1, 31), "both"
        )
        self.assertEqual(n_jan_both, 2)
        n_first_only = Rec.count_application_periods(
            date(2025, 1, 1), date(2025, 3, 31), "first"
        )
        self.assertEqual(n_first_only, 3)

    def test_recurring_concept_mass_unassign_by_code(self):
        company = self.env.company
        e1 = self.env["hr.employee"].create(
            {"name": "Desasignar E1", "company_id": company.id}
        )
        code = "DESASIGNA_MASIVO_TEST"
        self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": e1.id,
                "company_id": company.id,
                "name": "Temp",
                "code": code,
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 1.0,
                "active": True,
            }
        )
        wiz = self.env["hr.employee.recurring.concept.assign.wizard"].create(
            {
                "wizard_type": "unassign",
                "company_id": company.id,
                "assignment_scope": "employees",
                "employee_ids": [(6, 0, e1.ids)],
                "unassign_match": "code",
                "unassign_code": code,
            }
        )
        wiz.action_unassign()
        line = self.env["hr.employee.recurring.concept"].with_context(active_test=False).search(
            [("employee_id", "=", e1.id), ("code", "=", code)]
        )
        self.assertEqual(len(line), 1)
        self.assertFalse(line.active)

    def _create_loan_concept(self, **extra):
        company = self.env.company
        n = self.env["hr.employee"].search_count([]) + 1
        emp = self.env["hr.employee"].create(
            {
                "name": "Préstamo residuo test",
                "company_id": company.id,
                "birthday": date(1990, 1, 1),
                "sex": "male",
                "identification_id": f"0801199{n:06d}",
            }
        )
        vals = {
            "name": "Préstamo residuo",
            "concept_type": "deduction",
            "amount_type": "fixed",
            "amount": 1000.0,
            "is_loan": True,
            "installments": 10,
            "employee_id": emp.id,
            "date_start": date(2025, 1, 1),
        }
        vals.update(extra)
        return self.env["hr.employee.recurring.concept"].create(vals)

    def test_loan_residual_extra_payment_fifty(self):
        """10 × 100 + 1 × 50 = 1050 (caso usuario)."""
        concept = self._create_loan_concept(
            amount=100.0, installments=10, loan_residual_amount=50.0
        )
        self.assertTrue(concept.loan_has_residual)
        self.assertEqual(concept.loan_last_installment_amount, 50.0)
        self.assertEqual(concept.loan_total_payment_count, 11)
        self.assertEqual(concept._gn_loan_installment_amount(9), 100.0)
        self.assertEqual(concept._gn_loan_installment_amount(10), 50.0)
        concept.manual_paid_installments = 9
        self.assertEqual(
            concept._gn_effective_recurring_deduction_base(100.0),
            100.0,
        )
        self.assertEqual(concept.remaining_amount, 150.0)
        concept.manual_paid_installments = 10
        self.assertEqual(
            concept._gn_effective_recurring_deduction_base(100.0),
            50.0,
        )

    def test_loan_residual_extra_payment_hundred(self):
        concept = self._create_loan_concept(
            amount=1000.0, loan_residual_amount=100.0
        )
        self.assertTrue(concept.loan_has_residual)
        self.assertEqual(concept.loan_last_installment_amount, 100.0)
        self.assertEqual(concept.loan_total_payment_count, 11)
        concept.manual_paid_installments = 9
        self.assertEqual(
            concept._gn_effective_recurring_deduction_base(1000.0),
            1000.0,
        )
        concept.manual_paid_installments = 10
        self.assertEqual(
            concept._gn_effective_recurring_deduction_base(1000.0),
            100.0,
        )

    def test_loan_no_residual_when_total_matches(self):
        concept = self._create_loan_concept()
        self.assertEqual(concept.total_amount, 10000.0)
        self.assertFalse(concept.loan_has_residual)
        self.assertEqual(concept.loan_last_installment_amount, 0.0)
        self.assertEqual(concept.loan_total_payment_count, 10)

    def test_loan_rejects_negative_residual(self):
        with self.assertRaises(ValidationError):
            self._create_loan_concept(loan_residual_amount=-5.0)

    def test_loan_residual_preserved_on_amount_change(self):
        concept = self._create_loan_concept(
            amount=1000.0, loan_residual_amount=100.0
        )
        concept.write({"amount": 900.0})
        self.assertEqual(concept.total_amount, 9000.0)
        self.assertEqual(concept.loan_residual_amount, 100.0)
        self.assertEqual(concept.loan_last_installment_amount, 100.0)

    def test_loan_progress_and_next_deduction(self):
        concept = self._create_loan_concept(
            amount=1000.0, loan_residual_amount=100.0
        )
        self.assertEqual(concept.loan_installments_remaining, 11)
        self.assertEqual(concept.loan_progress_percent, 0.0)
        self.assertEqual(concept.loan_stage, "residual")
        self.assertEqual(concept.gn_next_deduction_amount, 1000.0)
        concept.manual_paid_installments = 9
        self.assertEqual(concept.loan_installments_remaining, 2)
        self.assertEqual(concept.loan_progress_percent, 81.82)
        self.assertEqual(concept.loan_stage, "residual")
        self.assertEqual(concept.gn_next_deduction_amount, 1000.0)
        concept.manual_paid_installments = 10
        self.assertEqual(concept.loan_installments_remaining, 1)
        self.assertEqual(concept.loan_stage, "almost_done")
        self.assertEqual(concept.gn_next_deduction_amount, 100.0)

    def _create_payslip_with_loan_input(self, concept, date_from, date_to):
        """Recibo mínimo con entrada vinculada al préstamo (sin reglas salariales)."""
        emp = concept.employee_id
        input_type = self.env["hr.payslip.input.type"].create(
            {"code": "LOAN_QUOTA_TEST", "name": "Préstamo test cuotas"}
        )
        struct = self.env["hr.payroll.structure"].search([], limit=1)
        if not struct:
            struct = self.env["hr.payroll.structure"].create(
                {"name": "Estructura test cuotas", "code": "GN_QUOTA_TEST"}
            )
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": emp.id,
                "struct_id": struct.id,
                "date_from": date_from,
                "date_to": date_to,
                "company_id": concept.company_id.id,
            }
        )
        payslip.with_context(_skip_recurring_sync=True).write(
            {
                "input_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": concept.name,
                            "input_type_id": input_type.id,
                            "amount": concept.amount,
                            "recurring_concept_id": concept.id,
                        },
                    )
                ]
            }
        )
        return payslip

    def test_loan_quota_not_incremented_on_compute_only(self):
        concept = self._create_loan_concept(amount=500.0, installments=5)
        payslip = self._create_payslip_with_loan_input(
            concept, date(2026, 1, 1), date(2026, 1, 15)
        )
        payslip.compute_sheet()
        self.assertEqual(concept.paid_installments, 0)
        self.assertFalse(payslip.gn_quota_registration_json)

    def test_loan_quota_increments_on_validate(self):
        concept = self._create_loan_concept(amount=500.0, installments=5)
        payslip = self._create_payslip_with_loan_input(
            concept, date(2026, 1, 1), date(2026, 1, 15)
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(concept.paid_installments, 1)
        self.assertTrue(payslip.gn_quota_registration_json)

    def test_loan_quota_reverts_on_cancel(self):
        concept = self._create_loan_concept(amount=500.0, installments=5)
        payslip = self._create_payslip_with_loan_input(
            concept, date(2026, 1, 1), date(2026, 1, 15)
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(concept.paid_installments, 1)
        payslip.sudo().action_payslip_cancel()
        self.assertEqual(concept.paid_installments, 0)
        self.assertFalse(payslip.gn_quota_registration_json)

    def test_loan_split_biweek_counts_on_second_half_only(self):
        concept = self._create_loan_concept(
            amount=1000.0,
            installments=10,
            apply_biweek="both",
            loan_split_quota_across_biweeks=True,
        )
        version = self.env["hr.version"].create(
            {
                "employee_id": concept.employee_id.id,
                "wage": 20000.0,
                "periodicity": "biweekly",
                "contract_date_start": date(2026, 1, 1),
                "date_version": date(2026, 1, 1),
            }
        )
        concept.employee_id.write({"current_version_id": version.id})
        slip_q1 = self._create_payslip_with_loan_input(
            concept, date(2026, 1, 1), date(2026, 1, 15)
        )
        slip_q1.compute_sheet()
        slip_q1.action_payslip_done()
        self.assertEqual(concept.paid_installments, 0)

        slip_q2 = self._create_payslip_with_loan_input(
            concept, date(2026, 1, 16), date(2026, 1, 31)
        )
        slip_q2.compute_sheet()
        slip_q2.action_payslip_done()
        self.assertEqual(concept.paid_installments, 1)

    def test_assign_wizard_preview_counts(self):
        company = self.env.company
        e1 = self.env["hr.employee"].create(
            {"name": "Preview E1", "company_id": company.id}
        )
        e2 = self.env["hr.employee"].create(
            {"name": "Preview E2", "company_id": company.id}
        )
        code = "PREVIEW_WIZ_TEST"
        self.env["hr.employee.recurring.concept"].create(
            {
                "employee_id": e1.id,
                "company_id": company.id,
                "name": "Existente",
                "code": code,
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 5.0,
                "date_start": date(2025, 1, 1),
            }
        )
        wiz = self.env["hr.employee.recurring.concept.assign.wizard"].create(
            {
                "company_id": company.id,
                "assignment_scope": "employees",
                "employee_ids": [(6, 0, (e1 | e2).ids)],
                "source_mode": "inline",
                "inline_name": "Masivo preview",
                "inline_code": code,
                "inline_concept_type": "deduction",
                "inline_amount_type": "fixed",
                "assign_amount": 5.0,
            }
        )
        self.assertEqual(wiz.preview_employee_count, 2)
        self.assertEqual(wiz.preview_will_create_count, 1)
        self.assertEqual(wiz.preview_skip_duplicate_count, 1)

    def test_employee_onchange_keeps_catalog_template(self):
        company = self.env.company
        tpl = self.env["hr.employee.recurring.concept"].create(
            {
                "name": "Plantilla cuota sindical",
                "code": "TPL_ONCHANGE_EMP",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 25.0,
                "is_template": True,
                "company_id": company.id,
            }
        )
        emp = self.env["hr.employee"].create(
            {"name": "Empleado onchange tpl", "company_id": company.id}
        )
        concept = self.env["hr.employee.recurring.concept"].new(
            {
                "name_from_concept_id": tpl.id,
                "company_id": company.id,
            }
        )
        concept._onchange_name_from_concept_id()
        concept.employee_id = emp
        concept._onchange_employee_id()
        self.assertEqual(concept.name_from_concept_id, tpl)
        self.assertEqual(concept.name, tpl.name)
        self.assertEqual(concept.code, tpl.code)

    def test_write_preserves_loan_residual(self):
        concept = self._create_loan_concept(
            amount=100.0, installments=10, loan_residual_amount=50.0
        )
        concept.write({"notes": "ajuste", "amount": 100.0})
        self.assertEqual(concept.amount, 100.0)
        self.assertEqual(concept.loan_residual_amount, 50.0)
        self.assertEqual(concept.loan_last_installment_amount, 50.0)

    def test_form_warning_banner_residual_no_popup(self):
        concept = self.env["hr.employee.recurring.concept"].new(
            {
                "name": "Préstamo banner",
                "concept_type": "deduction",
                "amount_type": "fixed",
                "amount": 100.0,
                "is_loan": True,
                "installments": 10,
                "loan_residual_amount": 50.0,
            }
        )
        concept._compute_gn_form_warning_html()
        self.assertTrue(concept.gn_form_has_warning)
        self.assertIn("50.0", concept.gn_form_warning_html or "")
        self.assertIn("adicional", (concept.gn_form_warning_html or "").lower())

    def test_default_bank_unique_per_country(self):
        country_hn = self.env.ref("base.hn")
        country_sv = self.env.ref("base.sv")
        bank_hn_1 = self.env["res.bank"].create(
            {
                "name": "Banco HN default 1",
                "country": country_hn.id,
                "gn_is_default_bank": True,
            }
        )
        bank_hn_2 = self.env["res.bank"].create(
            {
                "name": "Banco HN default 2",
                "country": country_hn.id,
                "gn_is_default_bank": True,
            }
        )
        self.assertFalse(bank_hn_1.gn_is_default_bank)
        self.assertTrue(bank_hn_2.gn_is_default_bank)

        bank_sv = self.env["res.bank"].create(
            {
                "name": "Banco SV default",
                "country": country_sv.id,
                "gn_is_default_bank": True,
            }
        )
        self.assertTrue(bank_sv.gn_is_default_bank)
        self.assertTrue(bank_hn_2.gn_is_default_bank)

    def test_partner_bank_default_get_uses_default_bank(self):
        country_hn = self.env.ref("base.hn")
        default_bank = self.env["res.bank"].create(
            {
                "name": "Banco HN empleados",
                "country": country_hn.id,
                "gn_is_default_bank": True,
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Contacto empleado HN",
                "country_id": country_hn.id,
            }
        )
        defaults = (
            self.env["res.partner.bank"]
            .with_context(default_partner_id=partner.id)
            .default_get(["bank_id", "partner_id"])
        )
        self.assertEqual(defaults.get("bank_id"), default_bank.id)
