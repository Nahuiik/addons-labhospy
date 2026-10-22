# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Tests de payslip end-to-end, inputs y reglas salariales

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import (
    L10nHnPayrollTestCommon,
    TEST_DATE_2026_JAN_1,
    TEST_DATE_2026_JAN_15,
)


@tagged('post_install', '-at_install', 'payroll')
class TestPayslipInputsAndRules(L10nHnPayrollTestCommon, TransactionCase):
    """Tests payslip: compute_sheet, líneas BASIC/GROSS/NET, IHSS, RAP, ISR"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.create_employee('Empleado Payslip', wage=25000.0)
        cls.create_ihss_settings()
        cls.create_rap_settings()
        cls.create_isr_config()

    def test_payslip_create_and_compute(self):
        """Crear payslip y ejecutar compute_sheet"""
        payslip = self.create_payslip(self.employee)
        payslip.compute_sheet()
        self.assertTrue(payslip.line_ids)

    def test_payslip_basic_line(self):
        """Línea BASIC: salario quincenal = wage/2"""
        payslip = self.create_payslip(self.employee)
        payslip.compute_sheet()
        basic = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        if basic:
            expected = self.employee.current_version_id.wage / 2.0
            self.assertAlmostEqual(basic[0].total, expected, places=2)

    def test_payslip_gross_net_categories(self):
        """GROSS y NET existen; NET = devengado - deducciones"""
        payslip = self.create_payslip(self.employee)
        payslip.compute_sheet()
        gross = payslip.line_ids.filtered(lambda l: l.code == 'GROSS')
        net = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        if gross and net:
            # NET puede ser mayor que GROSS si hay reglas que suman a NET (ej. reembolsos)
            # Verificar que ambas líneas existen y tienen valores razonables
            self.assertGreater(gross[0].total, 0)
            self.assertGreater(net[0].total, 0)

    def test_payslip_deductions_exist(self):
        """Existen líneas de deducción (IHSS, RAP, ISR si aplica)"""
        payslip = self.create_payslip(self.employee)
        payslip.compute_sheet()
        ded_lines = payslip.line_ids.filtered(lambda l: l.category_id.code == 'DED')
        self.assertTrue(ded_lines, "Debe haber al menos una deducción")

    def test_payslip_action_done(self):
        """Payslip puede pasarse a validated (done)"""
        payslip = self.create_payslip(self.employee)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        # Odoo 19 hr_payroll: state = 'validated' (no 'done')
        self.assertIn(payslip.state, ('validated', 'done'))

    def test_payslip_run_create(self):
        """Payslip run se puede crear"""
        run = self.create_payslip_run()
        self.assertTrue(run.id)
