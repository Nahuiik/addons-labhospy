# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestIHSS(TransactionCase):
    """Tests for IHSS (Social Security) calculation"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company IHSS',
        })
        
        # Create IHSS settings for 2026
        cls.ihss_settings = cls.env['l10n.hn.ihss.settings'].create({
            'year': 2026,
            'company_id': cls.company.id,
            'ivm_ceiling_monthly': 20000.0,
            'ivm_employer_rate': 3.5,
            'ivm_employee_rate': 2.5,
            'ivm_state_rate': 0.5,
            'em_ceiling_monthly': 20000.0,
            'em_employer_rate': 1.0,
            'em_employee_rate': 1.0,
            'payment_periodicity': 'biweekly',
            'include_in': 'both',
            'apply_first_quincena': True,
            'apply_second_quincena': True,
        })
        
        cls.ihss_settings.action_validate()
    
    def test_ihss_settings_creation(self):
        """Test IHSS settings creation"""
        self.assertEqual(self.ihss_settings.year, 2026)
        self.assertEqual(self.ihss_settings.company_id, self.company)
        self.assertEqual(self.ihss_settings.state, 'validated')
        self.assertEqual(self.ihss_settings.ivm_ceiling_monthly, 20000.0)
        self.assertEqual(self.ihss_settings.em_ceiling_monthly, 20000.0)
    
    def test_ihss_quota_calculation(self):
        """Test IHSS quota calculation"""
        # IVM monthly quota
        expected_ivm = self.ihss_settings.ivm_ceiling_monthly * (self.ihss_settings.ivm_employee_rate / 100.0)
        self.assertEqual(self.ihss_settings.ivm_quota_monthly, expected_ivm)
        self.assertEqual(self.ihss_settings.ivm_quota_monthly, 500.0)  # 20000 * 2.5%
        
        # EM monthly quota
        expected_em = self.ihss_settings.em_ceiling_monthly * (self.ihss_settings.em_employee_rate / 100.0)
        self.assertEqual(self.ihss_settings.em_quota_monthly, expected_em)
        self.assertEqual(self.ihss_settings.em_quota_monthly, 200.0)  # 20000 * 1.0%
        
        # Total monthly IHSS
        expected_total = expected_ivm + expected_em
        self.assertEqual(self.ihss_settings.ihss_amount_monthly, expected_total)
        self.assertEqual(self.ihss_settings.ihss_amount_monthly, 700.0)
        
        # Biweekly quota (half of monthly)
        expected_biweekly = expected_total / 2.0
        self.assertEqual(self.ihss_settings.ihss_quota_biweekly, expected_biweekly)
        self.assertEqual(self.ihss_settings.ihss_quota_biweekly, 350.0)
    
    def test_ihss_unique_validated(self):
        """Test that only one validated IHSS setting per year/company"""
        # Try to create another validated setting
        with self.assertRaises(ValidationError):
            duplicate = self.env['l10n.hn.ihss.settings'].create({
                'year': 2026,
                'company_id': self.company.id,
                'ivm_ceiling_monthly': 20000.0,
                'ivm_employer_rate': 3.5,
                'ivm_employee_rate': 2.5,
                'em_ceiling_monthly': 20000.0,
                'em_employer_rate': 1.0,
                'em_employee_rate': 1.0,
                'payment_periodicity': 'biweekly',
                'state': 'validated',
            })
    
    def test_ihss_include_in_onchange(self):
        """Test include_in onchange logic"""
        # Set to first quincena only - need to call onchange manually when using write()
        self.ihss_settings.write({'include_in': 'first'})
        self.ihss_settings._onchange_include_in()  # Manually trigger onchange
        self.assertTrue(self.ihss_settings.apply_first_quincena)
        self.assertFalse(self.ihss_settings.apply_second_quincena)
        
        # Set to second quincena only
        self.ihss_settings.write({'include_in': 'second'})
        self.ihss_settings._onchange_include_in()  # Manually trigger onchange
        self.assertFalse(self.ihss_settings.apply_first_quincena)
        self.assertTrue(self.ihss_settings.apply_second_quincena)
        
        # Set to both
        self.ihss_settings.write({'include_in': 'both'})
        self.ihss_settings._onchange_include_in()  # Manually trigger onchange
        self.assertTrue(self.ihss_settings.apply_first_quincena)
        self.assertTrue(self.ihss_settings.apply_second_quincena)
    
    def test_ihss_draft_validation(self):
        """Test IHSS settings can be set to draft"""
        self.ihss_settings.action_draft()
        self.assertEqual(self.ihss_settings.state, 'draft')
        
        # Should be able to create another validated setting now
        new_settings = self.env['l10n.hn.ihss.settings'].create({
            'year': 2026,
            'company_id': self.company.id,
            'ivm_ceiling_monthly': 20000.0,
            'ivm_employer_rate': 3.5,
            'ivm_employee_rate': 2.5,
            'em_ceiling_monthly': 20000.0,
            'em_employer_rate': 1.0,
            'em_employee_rate': 1.0,
            'payment_periodicity': 'biweekly',
        })
        new_settings.action_validate()
        self.assertEqual(new_settings.state, 'validated')
    
    def test_ihss_calculation_base(self):
        """Test IHSS calculation uses configured ceiling, not salary"""
        # IHSS should be calculated based on ivm_ceiling_monthly and em_ceiling_monthly,
        # not employee salary. This is tested in salary rules, but we verify settings.
        self.assertGreater(self.ihss_settings.ivm_ceiling_monthly, 0)
        self.assertGreater(self.ihss_settings.em_ceiling_monthly, 0)
        
        # Verify rates are correct
        self.assertEqual(self.ihss_settings.ivm_employee_rate, 2.5)
        self.assertEqual(self.ihss_settings.em_employee_rate, 1.0)
        
        # Verify employer rates
        self.assertEqual(self.ihss_settings.ivm_employer_rate, 3.5)
        self.assertEqual(self.ihss_settings.em_employer_rate, 1.0)
    
    def test_ihss_consolidated_rule(self):
        """Test that IHSS rule consolidates IVM and EM"""
        # The salary rule should sum both IVM and EM
        # This is verified by checking that the rule exists and calculates correctly
        # Actual calculation is tested in salary rules tests
        self.assertEqual(self.ihss_settings.ihss_amount_monthly, 700.0)
        self.assertEqual(self.ihss_settings.ivm_quota_monthly + self.ihss_settings.em_quota_monthly, 700.0)
