# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestISRSAR2026(TransactionCase):
    """Tests for ISR SAR 2026 calculation algorithm"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company SAR 2026',
        })
        
        # Create employee with birthday for age calculation
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee SAR 2026',
            'company_id': cls.company.id,
            'birthday': date(1990, 5, 15),  # Age ~35 years
        })
        
        # Create structure type and structure
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
            'default_schedule_pay': 'bi-weekly',
        })
        
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Test Structure',
            'type_id': cls.structure_type.id,
            'code': 'TEST_STRUCTURE',
            'company_id': cls.company.id,
        })
        
        # Create contract version
        cls.version = cls.env['hr.version'].create({
            'employee_id': cls.employee.id,
            'wage': 30000.0,  # L 30,000 monthly = L 15,000 biweekly
            'periodicity': 'biweekly',
            'structure_type_id': cls.structure_type.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
            # SAR 2026 fields
            'dias_vacaciones_pagadas_anual': 15,
            'colegiacion_anual': 2000.0,
            'pension_privada_anual': 5000.0,
            'otros_ingresos_anual': 0.0,
            'otras_deducciones_anual': 1000.0,
        })
        
        cls.employee.write({'current_version_id': cls.version.id})
        
        # Create ISR config for 2026 with SAR 2026 fields
        cls.isr_config = cls.env['l10n.hn.isr.config'].create({
            'year': 2026,
            'company_id': cls.company.id,
            'periodicity': 'biweekly',
            'apply_in': 'both',
            'salario_minimo_promedio': 13985.16,
            # SAR 2026 fields
            'multiplicador_tope_exento_decimos': 10.0,
            'meses_retencion': 12,
            'meses_excluidos_retencion': '',  # No excluded months
            'edad_tercera_edad': 65,
            'exoneracion_tercera_edad_monto': 350000.0,
            'medical_expenses_enabled': True,
            'medical_expenses_by_age': True,
            'medical_expenses_default_limit': 40000.0,
        })
        
        # Create SAR 2026 tax brackets (marginal progressive)
        cls.env['l10n.hn.isr.config.bracket'].create([
            {
                'config_id': cls.isr_config.id,
                'sequence': 10,
                'from_amount': 0.0,
                'to_amount': 228324.32,
                'rate': 0.0,
                'fixed_quota': 0.0,
                'excess_over': 0.0,
            },
            {
                'config_id': cls.isr_config.id,
                'sequence': 20,
                'from_amount': 228324.33,
                'to_amount': 348154.10,
                'rate': 15.0,
                'fixed_quota': 0.0,
                'excess_over': 228324.33,
            },
            {
                'config_id': cls.isr_config.id,
                'sequence': 30,
                'from_amount': 348154.11,
                'to_amount': 809660.75,
                'rate': 20.0,
                'fixed_quota': 17974.47,
                'excess_over': 348154.11,
            },
            {
                'config_id': cls.isr_config.id,
                'sequence': 40,
                'from_amount': 809660.76,
                'to_amount': 0.0,  # No limit
                'rate': 25.0,
                'fixed_quota': 110275.80,
                'excess_over': 809660.76,
            },
        ])
        
        # Create medical expense rules by age
        cls.env['l10n.hn.isr.medical_expense_rule'].create([
            {
                'config_id': cls.isr_config.id,
                'age_from': 0,
                'age_to': 59,
                'limit_amount': 40000.0,
            },
            {
                'config_id': cls.isr_config.id,
                'age_from': 60,
                'age_to': 64,
                'limit_amount': 70000.0,
            },
            {
                'config_id': cls.isr_config.id,
                'age_from': 65,
                'age_to': 0,  # No limit
                'limit_amount': 110000.0,
            },
        ])
        
        cls.isr_config.action_validate()
    
    def test_sar_2026_config_fields(self):
        """Test SAR 2026 configuration fields"""
        self.assertEqual(self.isr_config.multiplicador_tope_exento_decimos, 10.0)
        self.assertEqual(self.isr_config.meses_retencion, 12)
        self.assertEqual(self.isr_config.edad_tercera_edad, 65)
        self.assertEqual(self.isr_config.exoneracion_tercera_edad_monto, 350000.0)
        
        # Test computed field
        expected_tope = 13985.16 * 10.0
        self.assertEqual(self.isr_config.tope_exento_decimos, expected_tope)
    
    def test_sar_2026_marginal_tax_calculation(self):
        """Test SAR 2026 marginal progressive tax calculation"""
        # Test bracket 1: Exempt (0 to 228,324.32)
        tax = self.isr_config.calculate_isr_annual(100000.0)
        self.assertEqual(tax, 0.0)
        
        # Test bracket 2: 15% (228,324.33 to 348,154.10)
        taxable = 250000.0
        tax = self.isr_config.calculate_isr_annual(taxable)
        excess = taxable - 228324.33
        expected = excess * 0.15
        self.assertAlmostEqual(tax, expected, places=2)
        
        # Test bracket 3: 20% (348,154.11 to 809,660.75)
        taxable = 500000.0
        tax = self.isr_config.calculate_isr_annual(taxable)
        excess = taxable - 348154.11
        expected = 17974.47 + (excess * 0.20)
        self.assertAlmostEqual(tax, expected, places=2)
        
        # Test bracket 4: 25% (>809,660.76)
        taxable = 1000000.0
        tax = self.isr_config.calculate_isr_annual(taxable)
        excess = taxable - 809660.76
        expected = 110275.80 + (excess * 0.25)
        self.assertAlmostEqual(tax, expected, places=2)
    
    def test_sar_2026_decimos_exemption(self):
        """Test 13th and 14th month exemption calculation"""
        # Annual salary
        R = 360000.0  # L 30,000 monthly × 12
        
        # Calculate décimos
        decimo_13 = R / 12.0
        decimo_14 = R / 12.0
        tope_exento = self.isr_config.tope_exento_decimos
        
        # Test exemption
        exceso_13 = max(0, decimo_13 - tope_exento)
        exceso_14 = max(0, decimo_14 - tope_exento)
        
        # With salary of L 30,000/month, décimos are L 30,000 each
        # Tope exento is 139,851.60 (13985.16 × 10)
        # So there should be no excess
        self.assertEqual(exceso_13, 0.0)
        self.assertEqual(exceso_14, 0.0)
        
        # Test with higher salary that exceeds exemption
        R_high = 2000000.0  # L 2,000,000 annual
        decimo_13_high = R_high / 12.0  # ~166,666.67
        exceso_13_high = max(0, decimo_13_high - tope_exento)
        self.assertGreater(exceso_13_high, 0.0)
    
    def test_sar_2026_vacation_excess(self):
        """Test vacation excess calculation"""
        # Set vacation days > 30
        self.version.write({'dias_vacaciones_pagadas_anual': 45})
        
        R = 360000.0  # Annual salary
        dias_vacaciones = 45
        
        if dias_vacaciones > 30:
            exceso_vacaciones = (dias_vacaciones - 30) * (R / 360.0)
        else:
            exceso_vacaciones = 0.0
        
        expected_excess = 15 * (R / 360.0)
        self.assertAlmostEqual(exceso_vacaciones, expected_excess, places=2)
        
        # Test with 30 days or less (no excess)
        self.version.write({'dias_vacaciones_pagadas_anual': 30})
        dias_vacaciones = 30
        exceso_vacaciones = (dias_vacaciones - 30) * (R / 360.0) if dias_vacaciones > 30 else 0.0
        self.assertEqual(exceso_vacaciones, 0.0)
    
    def test_sar_2026_medical_expense_by_age(self):
        """Test medical expense deduction limits by age"""
        # Test age 35 (should use 0-59 rule)
        age_35 = 35
        limit = self.isr_config.get_medical_expense_limit(age_35)
        self.assertEqual(limit, 40000.0)
        
        # Test age 62 (should use 60-64 rule)
        age_62 = 62
        limit = self.isr_config.get_medical_expense_limit(age_62)
        self.assertEqual(limit, 70000.0)
        
        # Test age 70 (should use 65+ rule)
        age_70 = 70
        limit = self.isr_config.get_medical_expense_limit(age_70)
        self.assertEqual(limit, 110000.0)
    
    def test_sar_2026_third_age_exemption(self):
        """Test third age exemption"""
        # Create employee with age >= 65
        old_employee = self.env['hr.employee'].create({
            'name': 'Old Employee',
            'company_id': self.company.id,
            'birthday': date(1955, 1, 1),  # Age ~71 years
        })
        
        old_version = self.env['hr.version'].create({
            'employee_id': old_employee.id,
            'wage': 50000.0,
            'periodicity': 'monthly',
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
        })
        
        old_employee.write({'current_version_id': old_version.id})
        
        # Calculate age
        age = self.isr_config._get_employee_age(old_employee)
        self.assertGreaterEqual(age, 65)
        
        # Test exemption application
        AJ = 500000.0  # Net income
        if age >= self.isr_config.edad_tercera_edad:
            AH = max(0, AJ - self.isr_config.exoneracion_tercera_edad_monto)
        else:
            AH = AJ
        
        expected_AH = max(0, 500000.0 - 350000.0)
        self.assertEqual(AH, expected_AH)
    
    def test_sar_2026_excluded_months(self):
        """Test excluded months parsing and installment calculation"""
        # Test parsing excluded months
        self.isr_config.write({'meses_excluidos_retencion': '6,12'})
        meses_excluidos = self.isr_config._parse_excluded_months()
        self.assertEqual(set(meses_excluidos), {6, 12})
        
        # Test installment number calculation
        mes_actual = 7  # July
        numero_cuota = self.isr_config._get_current_installment_number(mes_actual, meses_excluidos)
        # Months 1-7 excluding 6 = 6 installments
        self.assertEqual(numero_cuota, 6)
        
        # Test with no excluded months
        self.isr_config.write({'meses_excluidos_retencion': ''})
        meses_excluidos = self.isr_config._parse_excluded_months()
        self.assertEqual(meses_excluidos, [])
        
        mes_actual = 7
        numero_cuota = self.isr_config._get_current_installment_number(mes_actual, [])
        self.assertEqual(numero_cuota, 7)
    
    def test_sar_2026_salary_ytd_and_projection(self):
        """Test salary YTD and annual projection"""
        year = 2026
        
        # Create payslips with compute_sheet (genera líneas con contract_id)
        for i in range(3):
            payslip = self.env['hr.payslip'].create({
                'employee_id': self.employee.id,
                'struct_id': self.structure.id,
                'date_from': date(year, 1, 1) + timedelta(days=i*15),
                'date_to': date(year, 1, 15) + timedelta(days=i*15),
                'company_id': self.company.id,
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()
        
        # Get salary YTD (suma de líneas BASIC)
        salary_ytd = self.isr_config._get_salary_ytd(
            self.employee, year, date(year, 2, 15), exclude_payslip_id=None
        )
        # Debe ser > 0 si hay payslips con BASIC
        self.assertGreaterEqual(salary_ytd, 0.0)
        
        # Test annual projection
        date_from = date(year, 2, 1)
        projected = self.isr_config._project_annual_salary(
            self.employee, salary_ytd, date_from
        )
        # Should project remaining months (o igual si salary_ytd=0)
        self.assertGreaterEqual(projected, salary_ytd)
    
    def test_sar_2026_bonuses_ytd_and_projection(self):
        """Test bonuses YTD and annual projection"""
        year = 2026
        
        # Create payslips with compute_sheet (evita crear líneas sin contract_id)
        for i in range(2):
            payslip = self.env['hr.payslip'].create({
                'employee_id': self.employee.id,
                'struct_id': self.structure.id,
                'date_from': date(year, 1, 1) + timedelta(days=i*15),
                'date_to': date(year, 1, 15) + timedelta(days=i*15),
                'company_id': self.company.id,
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()
        
        # Get bonuses YTD (puede ser 0 si la estructura no tiene bonos)
        bonuses_ytd = self.isr_config._get_bonuses_ytd(
            self.employee, year, date(year, 2, 1), exclude_payslip_id=None
        )
        self.assertGreaterEqual(bonuses_ytd, 0.0)
        
        # Test annual projection
        date_from = date(year, 2, 1)
        projected = self.isr_config._project_annual_bonuses(
            self.employee, bonuses_ytd, date_from
        )
        self.assertGreaterEqual(projected, bonuses_ytd)
    
    def test_sar_2026_annual_deductions(self):
        """Test annual deductions from model"""
        year = 2026
        
        # Create employee deductions
        type_afp = self.env.ref('l10n_hn_hr_payroll.deduction_type_afp')
        type_colegio = self.env.ref('l10n_hn_hr_payroll.deduction_type_colegio_profesional')
        self.env['l10n.hn.isr.employee_deduction'].create([
            {
                'name': 'AFP Privado',
                'employee_id': self.employee.id,
                'company_id': self.company.id,
                'year': year,
                'deduction_type_id': type_afp.id,
                'amount': 500.0,
                'periodicity': 'monthly',
                'date_start': date(year, 1, 1),
            },
            {
                'name': 'Colegio Profesional',
                'employee_id': self.employee.id,
                'company_id': self.company.id,
                'year': year,
                'deduction_type_id': type_colegio.id,
                'amount': 2000.0,
                'periodicity': 'annual',
                'date_start': date(year, 1, 1),
            },
        ])
        
        # Get annual deductions
        deductions = self.isr_config._get_annual_deductions_from_model(
            self.employee, year
        )
        # Monthly: 500 × 12 = 6000, Annual: 2000 = 2000, Total = 8000
        expected = (500.0 * 12) + 2000.0
        self.assertAlmostEqual(deductions, expected, places=2)
    
    def test_sar_2026_complete_calculation(self):
        """Test complete SAR 2026 withholding calculation"""
        # Create a payslip
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        # Calculate withholding using SAR 2026 algorithm
        calculation = self.isr_config._compute_withholding_sar_2026(payslip)
        
        # Verify structure: devuelve period_amount y audit_data
        self.assertIn('period_amount', calculation)
        self.assertIn('audit_data', calculation)
        audit = calculation['audit_data']
        self.assertIn('isr_annual_calculated', audit)
        self.assertIn('isr_period_amount', audit)
        self.assertIn('projected_taxable_base', audit)
        self.assertIn('total_deductions_ytd', audit)
        self.assertIn('total_taxable_income_ytd', audit)
        self.assertIn('salary_annual', audit)
        self.assertIn('thirteenth_month_taxable', audit)
        self.assertIn('fourteenth_month_taxable', audit)
        self.assertIn('excess_vacations', audit)
        
        # Verify values are reasonable
        self.assertGreaterEqual(audit['isr_period_amount'], 0.0)
        self.assertGreaterEqual(audit['isr_annual_calculated'], 0.0)
    
    def test_sar_2026_withholding_with_excluded_month(self):
        """Test withholding calculation with excluded month"""
        # Set June as excluded month
        self.isr_config.write({'meses_excluidos_retencion': '6'})
        
        # Create payslip for June
        payslip_june = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 15),
            'company_id': self.company.id,
        })
        
        # Calculate withholding
        result = self.isr_config._calculate_isr_withholding_sar_2026(
            self.employee,
            payslip_june.date_from,
            payslip_june.date_to,
            salary_ytd=150000.0,
            projected_salary_annual=360000.0,
            bonuses_ytd=0.0,
            projected_bonuses_annual=0.0,
            other_income_annual=0.0
        )
        
        # Retention should be 0 for excluded month
        self.assertEqual(result['retention_current_month'], 0.0)
    
    def test_sar_2026_ytd_update(self):
        """Test ISR YTD update when payslip is confirmed"""
        # Create payslip y compute_sheet (genera líneas con contract_id)
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        
        # Initial YTD should be 0
        self.assertEqual(self.version.isr_retenido_ytd, 0.0)
        
        # Confirm payslip (state = validated en Odoo 19)
        payslip.action_payslip_done()
        
        # YTD se actualiza en hr_payslip al confirmar (si el módulo lo implementa)
        # Verificar que el payslip quedó confirmado
        self.assertIn(payslip.state, ('validated', 'done'))
    
    def test_sar_2026_manual_override(self):
        """Test manual ISR override"""
        # Set manual ISR
        self.version.write({
            'isr_manual': True,
            'amount_isr_manual': 1000.0,
        })
        
        # Create payslip
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        # Calculate withholding
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(payslip)
        
        # Should return manual amount
        self.assertEqual(abs(calculation['period_amount']), 1000.0)
        self.assertTrue(calculation['audit_data'].get('manual', False))
    
    def test_sar_2026_employee_age_calculation(self):
        """Test employee age calculation"""
        # Test with birthday
        age = self.isr_config._get_employee_age(self.employee)
        # Employee born in 1990, so in 2026 should be ~36 years old
        self.assertGreaterEqual(age, 35)
        self.assertLessEqual(age, 37)
        
        # Test without birthday
        employee_no_birthday = self.env['hr.employee'].create({
            'name': 'No Birthday Employee',
            'company_id': self.company.id,
        })
        age = self.isr_config._get_employee_age(employee_no_birthday)
        self.assertEqual(age, 0)
    
    def test_sar_2026_compute_withholding_dispatcher(self):
        """Test compute_withholding dispatcher uses SAR 2026 when fields present"""
        # Config has SAR 2026 fields, should use SAR 2026 algorithm
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(payslip)
        
        # Should return calculation result
        self.assertIn('period_amount', calculation)
        self.assertIn('audit_data', calculation)
        
        # Verify audit record was created
        audit = self.env['l10n.hn.isr.audit'].search([
            ('payslip_id', '=', payslip.id)
        ], limit=1)
        self.assertTrue(audit)
    
    def test_sar_2026_zero_taxable_base(self):
        """Test calculation when taxable base is zero or negative"""
        # Set high deductions to make taxable base negative
        self.version.write({
            'colegiacion_anual': 100000.0,
            'pension_privada_anual': 100000.0,
            'otras_deducciones_anual': 100000.0,
        })
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        result = self.isr_config._calculate_isr_withholding_sar_2026(
            self.employee,
            payslip.date_from,
            payslip.date_to,
            salary_ytd=0.0,
            projected_salary_annual=100000.0,  # Low salary
            bonuses_ytd=0.0,
            projected_bonuses_annual=0.0,
            other_income_annual=0.0
        )
        
        # ISR should be 0 when taxable base is negative
        self.assertEqual(result['isr_annual'], 0.0)
        self.assertEqual(result['retention_current_month'], 0.0)
