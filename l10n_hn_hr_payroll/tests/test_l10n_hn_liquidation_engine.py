# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_hn_hr_payroll.models.hn_liquidation_calculator import (
    LiquidationInputDTO,
    build_lines_for_scenario,
    compute_salary_bases,
    notice_payment_days_art116,
    severance_salary_days_capped,
    vacation_proportional_divisor_for_year,
)
from .common import L10nHnPayrollTestCommon, TEST_DATE_2026_JAN_1


@tagged('post_install', '-at_install', 'payroll')
class TestL10nHnLiquidationCalculator(TransactionCase):

    def test_notice_art116_brackets(self):
        d, _note = notice_payment_days_art116(2)
        self.assertEqual(d, 1.0)
        self.assertEqual(notice_payment_days_art116(4)[0], 7.0)
        self.assertEqual(notice_payment_days_art116(8)[0], 14.0)
        self.assertEqual(notice_payment_days_art116(15)[0], 30.0)
        self.assertEqual(notice_payment_days_art116(30)[0], 60.0)

    def test_compute_salary_bases(self):
        sbd, sod, spd, _m = compute_salary_bases(
            monthly_wages_last_six=[30000, 30000, 30000],
            monthly_commissions_last_six=[3000],
            monthly_cash_wage=30000,
            in_kind_monthly_capped=5000,
        )
        self.assertGreater(sbd, 900)
        self.assertGreater(sod, sbd)
        self.assertGreaterEqual(spd, sod)

    def test_severance_cap_micro(self):
        months = 120  # 10 años
        d_cap_normal = severance_salary_days_capped(months, False)
        d_cap_micro = severance_salary_days_capped(months, True)
        self.assertLessEqual(d_cap_normal, 25 * 30)
        self.assertLessEqual(d_cap_micro, 15 * 30)

    def test_literal_g_resignation_15_years(self):
        inp = LiquidationInputDTO(
            total_months=15 * 12,
            continuous_service_years=15,
            is_microenterprise=False,
            sbd=1000, sod=1200, spd=1500, occupational_daily=1500,
        )
        lines = build_lines_for_scenario('resignation', inp, apply_literal_g_resignation=True)
        sever = [l for l in lines if l.side == 'income' and '35%' in l.name]
        self.assertTrue(sever, 'Debe existir línea 35% literal g renuncia 15 años')
        self.assertEqual(sever[0].payee_type, 'employee')

    def test_dismissal_unjustified_preaviso_and_cesantia(self):
        inp = LiquidationInputDTO(
            total_months=4,
            continuous_service_years=0.33,
            is_microenterprise=False,
            sbd=1000, sod=1000, spd=1000, occupational_daily=1000,
            employer_omitted_notice=True,
        )
        lines = build_lines_for_scenario('dismissal_unjustified', inp)
        inc = [l for l in lines if l.side == 'income']
        names = ' '.join(l.name for l in inc)
        self.assertIn('Preaviso', names)
        self.assertIn('Auxilio de cesantía', names)

    def test_notice_under_three_months_one_day(self):
        d, _ = notice_payment_days_art116(2)
        self.assertEqual(d, 1.0, '24 h preaviso → 1 día de salario')

    def test_vacation_proportional_divisors_stss_guide(self):
        self.assertEqual(vacation_proportional_divisor_for_year(1), 36)
        self.assertEqual(vacation_proportional_divisor_for_year(2), 30)
        self.assertEqual(vacation_proportional_divisor_for_year(3), 24)
        self.assertEqual(vacation_proportional_divisor_for_year(4), 18)
        self.assertEqual(vacation_proportional_divisor_for_year(99), 18)

    def test_microenterprise_no_literal_g_resignation(self):
        inp = LiquidationInputDTO(
            total_months=15 * 12,
            continuous_service_years=15,
            is_microenterprise=True,
            sbd=1000, sod=1200, spd=1500, occupational_daily=1500,
        )
        lines = build_lines_for_scenario(
            'resignation', inp, apply_literal_g_resignation=True,
        )
        sever = [l for l in lines if l.side == 'income' and '35%' in l.name]
        self.assertFalse(sever, 'Art. 120-A: sin literal g en microempresa')

    def test_proportional_vacation_not_auto_without_employer_fault(self):
        inp = LiquidationInputDTO(
            total_months=8,
            continuous_service_years=0.5,
            is_microenterprise=False,
            sbd=1000, sod=1000, spd=1000, occupational_daily=1000,
            vacation_proportional_days=5.0,
        )
        lines_no = build_lines_for_scenario(
            'resignation', inp, employer_fault_vacation_proportional=False,
        )
        prop_no = [l for l in lines_no if l.concept == 'proportional_vacation']
        self.assertFalse(prop_no)
        lines_yes = build_lines_for_scenario(
            'resignation', inp, employer_fault_vacation_proportional=True,
        )
        prop_yes = [l for l in lines_yes if l.concept == 'proportional_vacation']
        self.assertTrue(prop_yes)
        self.assertEqual(prop_yes[0].rule_origin, 'labor_rule')

    def test_proportional_vacation_company_policy_flag(self):
        inp = LiquidationInputDTO(
            total_months=8,
            continuous_service_years=0.5,
            is_microenterprise=False,
            sbd=1000, sod=1000, spd=1000, occupational_daily=1000,
            vacation_proportional_days=3.0,
            force_proportional_vacation_company=True,
        )
        lines = build_lines_for_scenario(
            'resignation', inp, employer_fault_vacation_proportional=False,
        )
        pol = [l for l in lines if l.concept == 'proportional_vacation']
        self.assertTrue(pol)
        self.assertEqual(pol[0].rule_origin, 'company_policy')

    def test_death_occupational_funeral_and_620(self):
        inp = LiquidationInputDTO(
            total_months=24,
            continuous_service_years=2,
            is_microenterprise=False,
            sbd=500, sod=600, spd=700, occupational_daily=800,
        )
        lines = build_lines_for_scenario('death_occupational', inp)
        f = [l for l in lines if l.concept == 'occupational_funeral']
        d620 = [l for l in lines if l.concept == 'occupational_620']
        self.assertTrue(f and d620)
        self.assertAlmostEqual(f[0].amount, 30 * 800)
        self.assertAlmostEqual(d620[0].amount, 620 * 800)
        self.assertEqual(f[0].payee_type, 'beneficiary')


@tagged('post_install', '-at_install', 'payroll')
class TestL10nHnLiquidationEngine(L10nHnPayrollTestCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.emp = cls.create_employee('Emp Liquidación', wage=30000.0)
        cls.company.is_microenterprise = False

    def test_engine_creates_lines_unjustified(self):
        liq = self.env['l10n.hn.liquidation'].create({
            'employee_id': self.emp.id,
            'company_id': self.company.id,
            'date': date(2026, 6, 1),
            'start_date': TEST_DATE_2026_JAN_1,
            'end_date': date(2026, 5, 31),
            'legal_termination_reason': 'dismissal_unjustified',
            'current_wage_monthly': 30000,
            'reason': 'dismissal',
        })
        self.env['hn.liquidation.engine'].apply_to_record(liq, simulation=False)
        self.assertGreater(len(liq.income_ids), 0)
        self.assertGreater(liq.spd_computed, 0)
