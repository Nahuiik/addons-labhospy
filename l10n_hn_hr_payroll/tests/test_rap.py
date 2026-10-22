# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestRAP(TransactionCase):
    """Tests for RAP (Retirement and Pension) calculation"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company RAP',
        })
        
        # Create RAP settings for 2026
        cls.rap_settings = cls.env['l10n.hn.rap.settings'].create({
            'year': 2026,
            'company_id': cls.company.id,
            'foviif_floor_monthly': 15000.0,
            'foviif_employee_rate': 1.5,
            'foviif_employer_rate': 1.5,
            'frl_minimum_wage_high_scale': 10000.0,
            'frl_employer_rate': 4.0,
            'apply_first_quincena': True,
            'apply_second_quincena': True,
        })
        
        cls.rap_settings.action_validate()
    
    def test_rap_settings_creation(self):
        """Test RAP settings creation"""
        self.assertEqual(self.rap_settings.year, 2026)
        self.assertEqual(self.rap_settings.company_id, self.company)
        self.assertEqual(self.rap_settings.state, 'validated')
        self.assertEqual(self.rap_settings.foviif_employee_rate, 1.5)
        self.assertEqual(self.rap_settings.foviif_employer_rate, 1.5)
        self.assertEqual(self.rap_settings.frl_employer_rate, 4.0)
    
    def test_frl_ceiling_calculation(self):
        """Test FRL ceiling calculation (3x minimum wage)"""
        expected_ceiling = self.rap_settings.frl_minimum_wage_high_scale * 3.0
        self.assertEqual(self.rap_settings.frl_ceiling_monthly, expected_ceiling)
        self.assertEqual(self.rap_settings.frl_ceiling_monthly, 30000.0)
    
    def test_foviif_floor_for_period(self):
        """Test FOVIIF floor calculation for different periods"""
        # Monthly period (30 days)
        floor = self.rap_settings.get_foviif_floor_for_period(30)
        self.assertEqual(floor, 15000.0)
        
        # Biweekly period (15 days)
        floor = self.rap_settings.get_foviif_floor_for_period(15)
        expected = 15000.0 * (15.0 / 30.0)
        self.assertEqual(floor, expected)
        self.assertEqual(floor, 7500.0)
        
        # Weekly period (7 days)
        floor = self.rap_settings.get_foviif_floor_for_period(7)
        expected = 15000.0 * (7.0 / 30.0)
        self.assertEqual(floor, round(expected, 2))
    
    def test_rap_unique_validated(self):
        """Test that only one validated RAP setting per year/company"""
        # Try to create another validated setting
        with self.assertRaises(ValidationError):
            duplicate = self.env['l10n.hn.rap.settings'].create({
                'year': 2026,
                'company_id': self.company.id,
                'foviif_floor_monthly': 15000.0,
                'foviif_employee_rate': 1.5,
                'foviif_employer_rate': 1.5,
                'frl_minimum_wage_high_scale': 10000.0,
                'frl_employer_rate': 4.0,
                'state': 'validated',
            })
    
    def test_rap_rates_validation(self):
        """Test RAP rates validation"""
        # Test negative rates
        with self.assertRaises(ValidationError):
            self.rap_settings.write({
                'foviif_employee_rate': -1.0,
            })
        
        with self.assertRaises(ValidationError):
            self.rap_settings.write({
                'frl_employer_rate': -1.0,
            })
    
    def test_rap_draft_validation(self):
        """Test RAP settings can be set to draft"""
        self.rap_settings.action_draft()
        self.assertEqual(self.rap_settings.state, 'draft')
        
        # Should be able to create another validated setting now
        new_settings = self.env['l10n.hn.rap.settings'].create({
            'year': 2026,
            'company_id': self.company.id,
            'foviif_floor_monthly': 15000.0,
            'foviif_employee_rate': 1.5,
            'foviif_employer_rate': 1.5,
            'frl_minimum_wage_high_scale': 10000.0,
            'frl_employer_rate': 4.0,
        })
        new_settings.action_validate()
        self.assertEqual(new_settings.state, 'validated')
    
    def test_rap_calculation_base(self):
        """Test RAP calculation uses configured floor, not salary"""
        # RAP should be calculated based on foviif_floor_monthly, not employee salary
        # This is tested in salary rules, but we can verify the settings are correct
        self.assertGreater(self.rap_settings.foviif_floor_monthly, 0)
        self.assertGreater(self.rap_settings.foviif_employee_rate, 0)
        
        # Calculate expected FOVIIF employee contribution
        expected_employee = self.rap_settings.foviif_floor_monthly * (self.rap_settings.foviif_employee_rate / 100.0)
        self.assertEqual(expected_employee, 225.0)  # 15000 * 1.5% = 225
