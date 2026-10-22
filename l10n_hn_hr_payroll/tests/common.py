# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Factories y helpers para tests de l10n_hn_hr_payroll

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase


# Fechas fijas para tests deterministas
TEST_DATE_2026_JAN_1 = date(2026, 1, 1)
TEST_DATE_2026_JAN_15 = date(2026, 1, 15)
TEST_DATE_2026_JAN_31 = date(2026, 1, 31)
TEST_DATE_2026_FEB_15 = date(2026, 2, 15)
TEST_DATE_2026_DEC_31 = date(2026, 12, 31)


class L10nHnPayrollTestCommon(TransactionCase):
    """Base común con factories para tests de nómina Honduras"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_company()
        cls._create_calendar()
        cls._create_structure_type()
        cls._create_structure()

    @classmethod
    def _create_company(cls):
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company Honduras',
        })

    @classmethod
    def _create_calendar(cls):
        cls.calendar = cls.env.ref('resource.resource_calendar_std', raise_if_not_found=False)
        if not cls.calendar:
            cls.calendar = cls.env['resource.calendar'].create({
                'name': 'Standard 40h/week',
            })

    @classmethod
    def _create_structure_type(cls):
        cls.structure_type = cls.env['hr.payroll.structure.type'].search([
            ('default_schedule_pay', '=', 'bi-weekly')
        ], limit=1)
        if not cls.structure_type:
            cls.structure_type = cls.env['hr.payroll.structure.type'].create({
                'name': 'Nómina Quincenal Test',
                'default_schedule_pay': 'bi-weekly',
                'default_resource_calendar_id': cls.calendar.id if cls.calendar else False,
            })

    @classmethod
    def _create_structure(cls):
        cls.structure = cls.env['hr.payroll.structure'].search([
            ('type_id', '=', cls.structure_type.id),
            ('company_id', 'in', [False, cls.company.id]),
        ], limit=1)
        if not cls.structure:
            cls.structure = cls.env['hr.payroll.structure'].create({
                'name': 'Estructura Test Honduras',
                'type_id': cls.structure_type.id,
                'code': 'HN_TEST',
                'company_id': cls.company.id,
            })

    @classmethod
    def create_employee(cls, name='Test Employee', wage=20000.0, **kwargs):
        """Crea empleado con contrato (hr.version)"""
        employee = cls.env['hr.employee'].create({
            'name': name,
            'company_id': cls.company.id,
            **kwargs
        })
        version = cls.env['hr.version'].create({
            'employee_id': employee.id,
            'wage': wage,
            'periodicity': kwargs.get('periodicity', 'biweekly'),
            'structure_type_id': cls.structure_type.id,
            'contract_date_start': kwargs.get('contract_date_start', TEST_DATE_2026_JAN_1),
            'date_version': kwargs.get('date_version', TEST_DATE_2026_JAN_1),
        })
        employee.write({'current_version_id': version.id})
        return employee

    @classmethod
    def create_ihss_settings(cls, year=2026, **kwargs):
        """Crea configuración IHSS validada"""
        vals = {
            'year': year,
            'company_id': cls.company.id,
            'ivm_ceiling_monthly': kwargs.get('ivm_ceiling_monthly', 20000.0),
            'ivm_employer_rate': kwargs.get('ivm_employer_rate', 3.5),
            'ivm_employee_rate': kwargs.get('ivm_employee_rate', 2.5),
            'em_ceiling_monthly': kwargs.get('em_ceiling_monthly', 20000.0),
            'em_employer_rate': kwargs.get('em_employer_rate', 1.0),
            'em_employee_rate': kwargs.get('em_employee_rate', 1.0),
            'payment_periodicity': kwargs.get('payment_periodicity', 'biweekly'),
            'include_in': kwargs.get('include_in', 'both'),
        }
        settings = cls.env['l10n.hn.ihss.settings'].create(vals)
        settings.action_validate()
        return settings

    @classmethod
    def create_rap_settings(cls, year=2026, **kwargs):
        """Crea configuración RAP validada"""
        vals = {
            'year': year,
            'company_id': cls.company.id,
            'foviif_floor_monthly': kwargs.get('foviif_floor_monthly', 15000.0),
            'foviif_employee_rate': kwargs.get('foviif_employee_rate', 1.5),
            'foviif_employer_rate': kwargs.get('foviif_employer_rate', 1.5),
            'frl_minimum_wage_high_scale': kwargs.get('frl_minimum_wage_high_scale', 10000.0),
            'frl_employer_rate': kwargs.get('frl_employer_rate', 4.0),
        }
        settings = cls.env['l10n.hn.rap.settings'].create(vals)
        settings.action_validate()
        return settings

    @classmethod
    def create_isr_config(cls, year=2026, salario_minimo=13985.16, **kwargs):
        """Crea configuración ISR validada con tramos 2026"""
        config = cls.env['l10n.hn.isr.config'].create({
            'year': year,
            'company_id': cls.company.id,
            'periodicity': kwargs.get('periodicity', 'biweekly'),
            'apply_in': kwargs.get('apply_in', 'both'),
            'salario_minimo_promedio': salario_minimo,
            'salario_exento': kwargs.get('salario_exento', 19027.03),
            'multiplicador_tope_exento_decimos': kwargs.get('multiplicador_tope_exento_decimos', 10.0),
            **{k: v for k, v in kwargs.items() if k not in (
                'periodicity', 'apply_in', 'salario_exento', 'multiplicador_tope_exento_decimos')}
        })
        brackets = [
            {'from_amount': 0.0, 'to_amount': 228324.32, 'rate': 0.0, 'fixed_quota': 0.0, 'excess_over': 0.0},
            {'from_amount': 228324.33, 'to_amount': 348154.10, 'rate': 15.0, 'fixed_quota': 0.0, 'excess_over': 228324.33},
            {'from_amount': 348154.11, 'to_amount': 809660.75, 'rate': 20.0, 'fixed_quota': 17974.47, 'excess_over': 348154.11},
            {'from_amount': 809660.76, 'to_amount': 0.0, 'rate': 25.0, 'fixed_quota': 110275.80, 'excess_over': 809660.76},
        ]
        for i, b in enumerate(brackets):
            cls.env['l10n.hn.isr.config.bracket'].create({
                'config_id': config.id,
                'sequence': (i + 1) * 10,
                **b
            })
        config.action_validate()
        return config

    def create_payslip(self, employee, date_from=None, date_to=None, struct=None):
        """Crea payslip para empleado (instance method - usa self)"""
        date_from = date_from or TEST_DATE_2026_JAN_1
        date_to = date_to or TEST_DATE_2026_JAN_15
        struct = struct or self.structure
        return self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': struct.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company.id,
        })

    def create_payslip_run(self, date_start=None, date_end=None):
        """Crea payslip run (batch) (instance method)"""
        date_start = date_start or TEST_DATE_2026_JAN_1
        date_end = date_end or TEST_DATE_2026_JAN_15
        return self.env['hr.payslip.run'].create({
            'name': 'Test Run',
            'date_start': date_start,
            'date_end': date_end,
            'company_id': self.company.id,
        })
