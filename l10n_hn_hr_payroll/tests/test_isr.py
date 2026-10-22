# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestISR(TransactionCase):
    """Tests for ISR (Income Tax) calculation and withholding"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company ISR',
        })
        
        # Create employee
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee ISR',
            'company_id': cls.company.id,
        })
        
        # Create contract version
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
        
        cls.version = cls.env['hr.version'].create({
            'employee_id': cls.employee.id,
            'wage': 20000.0,  # L 20,000 monthly = L 10,000 biweekly
            'periodicity': 'biweekly',
            'structure_type_id': cls.structure_type.id,
            'contract_date_start': date.today() - relativedelta(months=6),
            'date_version': date.today() - relativedelta(months=6),  # Set date_version to avoid uniqueness constraint
        })
        
        cls.employee.write({'current_version_id': cls.version.id})
        
        # Create ISR config for 2026
        cls.isr_config = cls.env['l10n.hn.isr.config'].create({
            'year': 2026,
            'company_id': cls.company.id,
            'periodicity': 'biweekly',
            'apply_in': 'both',
            'salario_minimo_promedio': 10000.0,  # L 10,000 monthly
        })
        
        # Create tax brackets (simplified for testing)
        cls.env['l10n.hn.isr.config.bracket'].create([
            {
                'config_id': cls.isr_config.id,
                'sequence': 10,
                'from_amount': 0.0,
                'to_amount': 100000.0,
                'rate': 0.0,
                'fixed_quota': 0.0,
                'excess_over': 0.0,
            },
            {
                'config_id': cls.isr_config.id,
                'sequence': 20,
                'from_amount': 100000.0,
                'to_amount': 200000.0,
                'rate': 15.0,
                'fixed_quota': 0.0,
                'excess_over': 100000.0,
            },
            {
                'config_id': cls.isr_config.id,
                'sequence': 30,
                'from_amount': 200000.0,
                'to_amount': 0.0,  # No limit
                'rate': 25.0,
                'fixed_quota': 15000.0,  # 15% of 100,000
                'excess_over': 200000.0,
            },
        ])
        
        cls.isr_config.action_validate()
    
    def test_isr_config_creation(self):
        """Test ISR configuration creation"""
        self.assertEqual(self.isr_config.year, 2026)
        self.assertEqual(self.isr_config.company_id, self.company)
        self.assertEqual(self.isr_config.state, 'validated')
        self.assertEqual(len(self.isr_config.bracket_ids), 3)
    
    def test_isr_bracket_calculation(self):
        """Test ISR bracket calculation"""
        # Test bracket 1: 0-100,000 (0%)
        tax = self.isr_config.calculate_isr_annual(50000.0)
        self.assertEqual(tax, 0.0)
        
        # Test bracket 2: 100,000-200,000 (15%)
        tax = self.isr_config.calculate_isr_annual(150000.0)
        expected = (150000.0 - 100000.0) * 0.15
        self.assertEqual(tax, expected)
        
        # Test bracket 3: >200,000 (25%)
        tax = self.isr_config.calculate_isr_annual(300000.0)
        expected = 15000.0 + (300000.0 - 200000.0) * 0.25
        self.assertEqual(tax, expected)
    
    def test_isr_withholding_basic(self):
        """Test basic ISR withholding calculation"""
        # Create a payslip for first biweekly period
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        # Calculate withholding
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(payslip)
        
        # Should return a dict with period_amount
        self.assertIn('period_amount', calculation)
        self.assertIn('audit_data', calculation)
        
        # Period amount should be negative (deduction)
        self.assertLessEqual(calculation['period_amount'], 0.0)
    
    def test_isr_withholding_ytd(self):
        """Test ISR withholding with YTD calculation"""
        # Create previous payslips
        for i in range(3):
            prev_payslip = self.env['hr.payslip'].create({
                'employee_id': self.employee.id,
                'struct_id': self.structure.id,
                'date_from': date(2026, 1, 1) + timedelta(days=i*15),
                'date_to': date(2026, 1, 15) + timedelta(days=i*15),
                'company_id': self.company.id,
            })
            # Compute sheet to generate lines
            prev_payslip.compute_sheet()
            # Set to done state
            prev_payslip.action_payslip_done()
        
        # Create current payslip
        current_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 2, 1),
            'date_to': date(2026, 2, 15),
            'company_id': self.company.id,
        })
        
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(current_payslip)
        
        # Should account for previous withholdings
        audit_data = calculation.get('audit_data', {})
        self.assertGreaterEqual(audit_data.get('isr_retained_ytd', 0), 0.0)
    
    def test_isr_employee_deduction(self):
        """Test employee ISR deduction"""
        type_afp = self.env.ref('l10n_hn_hr_payroll.deduction_type_afp')
        deduction = self.env['l10n.hn.isr.employee_deduction'].create({
            'name': 'AFP Deduction',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'year': 2026,
            'deduction_type_id': type_afp.id,
            'amount': 500.0,
            'periodicity': 'monthly',
            'date_start': date(2026, 1, 1),
        })
        
        # Test get_amount_for_period
        amount = deduction.get_amount_for_period(
            date(2026, 1, 1),
            date(2026, 1, 15)
        )
        self.assertEqual(amount, 500.0)
        
        # Test inactive deduction
        deduction.write({'active': False})
        amount = deduction.get_amount_for_period(
            date(2026, 1, 1),
            date(2026, 1, 15)
        )
        self.assertEqual(amount, 0.0)
    
    def test_isr_13th_14th_exemption(self):
        """Test 13th and 14th month exemption calculation"""
        exempt_limit = self.isr_config.salario_minimo_promedio * 10  # 100,000
        
        # Test amount below exemption
        thirteenth_taxable, fourteenth_taxable = self.isr_config._calculate_bonus_taxable(
            self.employee, 2026, self.isr_config.salario_minimo_promedio
        )
        # Should be 0 if no bonus payslips exist
        self.assertEqual(thirteenth_taxable, 0.0)
        self.assertEqual(fourteenth_taxable, 0.0)
    
    def test_isr_excluded_employee(self):
        """Test ISR exclusion for employee"""
        self.employee.write({'isr_excluded': True})
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(payslip)
        
        # Should return 0 for excluded employee
        self.assertEqual(calculation['period_amount'], 0.0)
        self.assertTrue(calculation['audit_data'].get('exempt', False))
    
    def test_isr_medical_expense_limit(self):
        """Test medical expense deduction limit"""
        # Test default limit
        limit = self.isr_config.get_medical_expense_limit()
        self.assertEqual(limit, 0.0)  # Not enabled
        
        # Enable medical expenses
        self.isr_config.write({
            'medical_expenses_enabled': True,
            'medical_expenses_default_limit': 40000.0,
        })
        
        limit = self.isr_config.get_medical_expense_limit()
        self.assertEqual(limit, 40000.0)
        
        # Test with age rules
        self.isr_config.write({
            'medical_expenses_by_age': True,
        })
        
        self.env['l10n.hn.isr.medical_expense_rule'].create({
            'config_id': self.isr_config.id,
            'age_from': 0,
            'age_to': 60,
            'limit_amount': 40000.0,
        })
        
        self.env['l10n.hn.isr.medical_expense_rule'].create({
            'config_id': self.isr_config.id,
            'age_from': 61,
            'age_to': 0,  # No limit
            'limit_amount': 50000.0,
        })
        
        # Test for age 30
        limit = self.isr_config.get_medical_expense_limit(employee_age=30)
        self.assertEqual(limit, 40000.0)
        
        # Test for age 65
        limit = self.isr_config.get_medical_expense_limit(employee_age=65)
        self.assertEqual(limit, 50000.0)
    
    def test_isr_period_applies(self):
        """Test period application logic"""
        # Test biweekly with both halves
        self.isr_config.write({
            'periodicity': 'biweekly',
            'apply_in': 'both',
        })
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        applies = self.isr_config._period_applies(self.isr_config, payslip)
        self.assertTrue(applies)
        
        # Test first half only
        self.isr_config.write({'apply_in': 'first_half'})
        applies = self.isr_config._period_applies(self.isr_config, payslip)
        self.assertTrue(applies)
        
        # Test second half only (should not apply to first half)
        self.isr_config.write({'apply_in': 'second_half'})
        applies = self.isr_config._period_applies(self.isr_config, payslip)
        self.assertFalse(applies)
        
        # Test monthly (should always apply)
        self.isr_config.write({'periodicity': 'monthly'})
        applies = self.isr_config._period_applies(self.isr_config, payslip)
        self.assertTrue(applies)
    
    def test_isr_audit_record_creation(self):
        """Test ISR audit record creation"""
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 15),
            'company_id': self.company.id,
        })
        
        calculation = self.env['l10n.hn.isr.config'].compute_withholding(payslip)
        
        # Check audit record was created
        audit = self.env['l10n.hn.isr.audit'].search([
            ('payslip_id', '=', payslip.id)
        ])
        
        self.assertTrue(audit)
        self.assertEqual(audit.employee_id, self.employee)
        self.assertEqual(audit.year, 2026)
        self.assertIn('isr_period_amount', audit._fields)
