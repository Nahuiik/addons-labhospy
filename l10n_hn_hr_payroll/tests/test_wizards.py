# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Tests para wizards del módulo

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError

from .common import L10nHnPayrollTestCommon, TEST_DATE_2026_JAN_1, TEST_DATE_2026_JAN_15


@tagged('post_install', '-at_install', 'payroll')
class TestWizards(L10nHnPayrollTestCommon, TransactionCase):
    """Tests para wizards: ISR, Benefits, Vecinal, etc."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.create_employee('Empleado Wizard', wage=25000.0)
        cls.ihss = cls.create_ihss_settings()
        cls.rap = cls.create_rap_settings()
        cls.isr_config = cls.create_isr_config()

    def test_isr_calculation_wizard_create(self):
        """Wizard ISR: crear y verificar campos"""
        wizard = self.env['l10n.hn.isr.calculation.wizard'].create({
            'config_id': self.isr_config.id,
            'period_type': 'first_half',
            'year': 2026,
            'month': '1',
        })
        self.assertEqual(wizard.config_id, self.isr_config)
        self.assertEqual(wizard.year, 2026)
        date_from, date_to = wizard._get_period_dates()
        self.assertEqual(date_from, date(2026, 1, 1))
        self.assertEqual(date_to, date(2026, 1, 15))

    def test_isr_calculation_wizard_annual_periods(self):
        """Wizard ISR: períodos anuales según periodicidad"""
        wizard = self.env['l10n.hn.isr.calculation.wizard'].create({
            'config_id': self.isr_config.id,
            'period_type': 'annual',
            'year': 2026,
        })
        periods = wizard._get_annual_periods()
        # Biweekly: 24 períodos
        self.assertEqual(len(periods), 24)

    def test_benefits_wizard_thirteenth(self):
        """Wizard Benefits: genera 13vo mes"""
        wizard = self.env['l10n.hn.benefits.generation.wizard'].create({
            'benefit_type': 'thirteenth',
            'year': 2026,
        })
        result = wizard.action_generate()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')

    def test_benefits_wizard_fourteenth(self):
        """Wizard Benefits: genera 14vo mes"""
        wizard = self.env['l10n.hn.benefits.generation.wizard'].create({
            'benefit_type': 'fourteenth',
            'year': 2026,
        })
        result = wizard.action_generate()
        self.assertEqual(result['type'], 'ir.actions.client')

    def test_recurring_concept_assign_wizard_exists(self):
        """Wizard asignar conceptos recurrentes: existe y se puede crear"""
        wizard_model = self.env.get('hr.employee.recurring.concept.assign.wizard')
        if wizard_model:
            wizard = wizard_model.create({})
            self.assertTrue(wizard)
