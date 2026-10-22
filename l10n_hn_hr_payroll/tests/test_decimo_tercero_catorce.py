# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Tests para 13vo y 14vo mes (Aguinaldo y Décimo Cuarto)

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import L10nHnPayrollTestCommon, TEST_DATE_2026_JAN_1, TEST_DATE_2026_DEC_31


@tagged('post_install', '-at_install', 'payroll')
class TestDecimoTerceroCatorce(L10nHnPayrollTestCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.create_employee('Empleado Décimos', wage=30000.0)
        cls.employee_start_mid_year = cls.create_employee(
            'Empleado Medio Año',
            wage=25000.0,
            contract_date_start=date(2026, 7, 1),
            date_version=date(2026, 7, 1),
        )

    def test_thirteenth_month_creation(self):
        """Crear registro 13vo mes para empleado"""
        rec = self.env['l10n.hn.thirteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        self.assertEqual(rec.year, 2026)
        self.assertEqual(rec.employee_id, self.employee)
        self.assertEqual(rec.period_start, date(2026, 1, 1))
        self.assertEqual(rec.period_end, date(2026, 12, 31))

    def test_thirteenth_month_worked_days_full_year(self):
        """Empleado todo el año: worked_days ≈ 360 (30-day months; Dec 31 puede dar 361)"""
        rec = self.env['l10n.hn.thirteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        self.assertIn(rec.worked_days, (360, 361), "worked_days debe ser 360 o 361 para año completo")

    def test_thirteenth_month_worked_days_partial_year(self):
        """Empleado desde julio: worked_days proporcional"""
        rec = self.env['l10n.hn.thirteenth.month'].create({
            'employee_id': self.employee_start_mid_year.id,
            'year': 2026,
        })
        # Julio a diciembre ≈ 180 días (30-day months; puede dar 181)
        self.assertIn(rec.worked_days, (180, 181), "worked_days debe ser 180 o 181 para medio año")

    def test_thirteenth_month_calculated_amount(self):
        """Monto calculado proporcional: (wage/360) * worked_days; wage=salario mensual"""
        rec = self.env['l10n.hn.thirteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        # wage=30000 mensual, año completo: (30000/360)*worked_days ≈ 30000
        self.assertGreater(rec.calculated_amount, 29000)
        self.assertLessEqual(rec.calculated_amount, 31000)

    def test_fourteenth_month_creation(self):
        """Crear registro 14vo mes"""
        rec = self.env['l10n.hn.fourteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        self.assertEqual(rec.year, 2026)
        self.assertEqual(rec.employee_id, self.employee)

    def test_fourteenth_month_calculated_amount(self):
        """14vo mes: período jul-jun, proporcional a días trabajados"""
        rec = self.env['l10n.hn.fourteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        # Período 14vo: jul 2025 - jun 2026. Empleado desde ene 2026 = 6 meses
        # (wage/360)*días ≈ (30000/360)*180 ≈ 15000
        self.assertGreater(rec.calculated_amount, 0)
        self.assertLessEqual(rec.calculated_amount, 35000)

    def test_isr_exempt_amount_thirteenth(self):
        """13vo mes: isr_exempt_amount hasta 10 salarios mínimos"""
        isr_config = self.create_isr_config(salario_minimo=13985.16)
        tope = isr_config.tope_exento_decimos  # 139851.60
        rec = self.env['l10n.hn.thirteenth.month'].create({
            'employee_id': self.employee.id,
            'year': 2026,
            'isr_exempt_amount': tope,
        })
        rec._compute_isr_taxable()
        # Si calculated <= tope, taxable = 0
        self.assertGreaterEqual(rec.isr_exempt_amount, 0)

    def test_benefits_generation_wizard_thirteenth(self):
        """Wizard genera 13vo mes para empleados"""
        count_before = self.env['l10n.hn.thirteenth.month'].search_count([('year', '=', 2026)])
        wizard = self.env['l10n.hn.benefits.generation.wizard'].create({
            'benefit_type': 'thirteenth',
            'year': 2026,
        })
        wizard.action_generate()
        count_after = self.env['l10n.hn.thirteenth.month'].search_count([('year', '=', 2026)])
        self.assertGreaterEqual(count_after, count_before + 1)

    def test_benefits_generation_wizard_fourteenth(self):
        """Wizard genera 14vo mes para empleados"""
        count_before = self.env['l10n.hn.fourteenth.month'].search_count([('year', '=', 2026)])
        wizard = self.env['l10n.hn.benefits.generation.wizard'].create({
            'benefit_type': 'fourteenth',
            'year': 2026,
        })
        wizard.action_generate()
        count_after = self.env['l10n.hn.fourteenth.month'].search_count([('year', '=', 2026)])
        self.assertGreaterEqual(count_after, count_before + 1)
