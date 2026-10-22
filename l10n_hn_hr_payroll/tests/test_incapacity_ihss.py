# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Tests para incapacidad IHSS Honduras (días 1-3 patrono, día 4+ IHSS)

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

from .common import L10nHnPayrollTestCommon


@tagged('post_install', '-at_install')
class TestIncapacityIHSS(L10nHnPayrollTestCommon):
    """Casos de prueba para incapacidad IHSS según especificación."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leave_type = cls.env.ref(
            'l10n_hn_hr_payroll.leave_type_ihss_incapacity',
            raise_if_not_found=False
        )
        if not cls.leave_type:
            cls.leave_type = cls.env['hr.leave.type'].create({
                'name': 'Incapacidad (IHSS)',
                'is_ihss_incapacity': True,
                'work_entry_type_id': cls.env.ref(
                    'l10n_hn_hr_payroll.work_entry_type_hn_incap_pat'
                ).id,
            })
        cls.work_entry_pat = cls.env.ref('l10n_hn_hr_payroll.work_entry_type_hn_incap_pat')
        cls.work_entry_ihss = cls.env.ref('l10n_hn_hr_payroll.work_entry_type_hn_incap_ihss')

    def _create_leave(self, employee, date_from, date_to, validate=True):
        """Crea y opcionalmente valida una ausencia por incapacidad."""
        leave = self.env['hr.leave'].create({
            'name': 'Incapacidad test',
            'employee_id': employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })
        if validate:
            leave.action_approve()
            if leave.state == 'validate1':
                leave.action_validate()
        return leave

    def test_01_incapacity_2_days_both_patrono(self):
        """Incapacidad 2 días (Mar-Mié): ambos deben ser Patrono, calendar_days_patrono=2."""
        employee = self.create_employee(
            name='Empleado Test 1',
            contract_date_start=date(2026, 2, 1),
        )
        # Mar 3 - Mié 4 Feb 2026
        leave = self._create_leave(
            employee,
            date(2026, 2, 3),
            date(2026, 2, 4),
        )
        self.assertEqual(leave.hn_incap_calendar_days_patrono, 2)
        self.assertEqual(leave.hn_incap_calendar_days_ihss, 0)
        self.assertEqual(leave.hn_incap_day_index_start, 1)
        self.assertEqual(leave.hn_incap_day_index_end, 2)

    def test_02_incapacity_5_days_monday_start(self):
        """Incapacidad 5 días iniciando lunes: L=1, M=2, X=3 patrono; J=4, V=5 IHSS."""
        employee = self.create_employee(
            name='Empleado Test 2',
            contract_date_start=date(2026, 2, 1),
        )
        # Lun 2 - Vie 6 Feb 2026
        leave = self._create_leave(
            employee,
            date(2026, 2, 2),
            date(2026, 2, 6),
        )
        self.assertEqual(leave.hn_incap_calendar_days_patrono, 3)
        self.assertEqual(leave.hn_incap_calendar_days_ihss, 2)
        self.assertEqual(leave.hn_incap_day_index_start, 1)
        self.assertEqual(leave.hn_incap_day_index_end, 5)

    def test_03_incapacity_friday_start(self):
        """Incapacidad iniciando viernes 5 días: Vie(1) Pat, Sáb(2) Pat, Dom(3) Pat, Lun(4) IHSS, Mar(5) IHSS.
        Verificar que el LUNES (laborable) genere work entry tipo IHSS."""
        employee = self.create_employee(
            name='Empleado Test 3',
            contract_date_start=date(2026, 1, 1),
        )
        # Vie 6 - Mar 10 Feb 2026
        leave = self._create_leave(
            employee,
            date(2026, 2, 6),
            date(2026, 2, 10),
        )
        self.assertEqual(leave.hn_incap_calendar_days_patrono, 3)
        self.assertEqual(leave.hn_incap_calendar_days_ihss, 2)
        self.assertEqual(leave.hn_incap_day_index_start, 1)
        self.assertEqual(leave.hn_incap_day_index_end, 5)

        # Verificar work entries: Lun 9 y Mar 10 deben ser IHSS
        work_entries = self.env['hr.work.entry'].search([
            ('employee_id', '=', employee.id),
            ('leave_id', '=', leave.id),
            ('active', '=', True),
        ])
        # Lun 9 Feb = día 4 del caso -> IHSS
        monday_entries = work_entries.filtered(
            lambda e: e.date == date(2026, 2, 9)
        )
        if monday_entries:
            self.assertEqual(
                monday_entries[0].work_entry_type_id.code,
                'HN_INCAP_IHSS',
                'El lunes (día 4) debe ser tipo IHSS',
            )

    def test_04_encadenadas_sin_hueco(self):
        """Dos incapacidades encadenadas sin hueco (termina 10, nueva inicia 11):
        la segunda debe arrancar con day_index_start = anterior_end+1 (no reiniciar)."""
        employee = self.create_employee(
            name='Empleado Test 4',
            contract_date_start=date(2026, 2, 1),
        )
        leave1 = self._create_leave(
            employee,
            date(2026, 2, 1),
            date(2026, 2, 10),
        )
        self.assertEqual(leave1.hn_incap_day_index_start, 1)
        self.assertEqual(leave1.hn_incap_day_index_end, 10)

        leave2 = self._create_leave(
            employee,
            date(2026, 2, 11),
            date(2026, 2, 15),
        )
        self.assertEqual(
            leave2.hn_incap_day_index_start, 11,
            'La segunda leave debe continuar con day_index 11',
        )
        self.assertEqual(leave2.hn_incap_day_index_end, 15)
        self.assertEqual(leave2.hn_incap_case_key, leave1.hn_incap_case_key)

    def test_05_encadenadas_con_hueco(self):
        """Dos incapacidades con hueco de 1 día: debe reiniciar el caso (day_index_start=1)."""
        employee = self.create_employee(
            name='Empleado Test 5',
            contract_date_start=date(2026, 2, 1),
        )
        leave1 = self._create_leave(
            employee,
            date(2026, 2, 1),
            date(2026, 2, 10),
        )
        leave2 = self._create_leave(
            employee,
            date(2026, 2, 12),  # Hueco: 11 no está en leave
            date(2026, 2, 15),
        )
        self.assertEqual(
            leave2.hn_incap_day_index_start, 1,
            'Con hueco debe reiniciar caso',
        )
        self.assertNotEqual(leave2.hn_incap_case_key, leave1.hn_incap_case_key)

    def test_06_no_overlap(self):
        """Prohibir traslapes de incapacidades."""
        employee = self.create_employee(
            name='Empleado Test 6',
            contract_date_start=date(2026, 2, 1),
        )
        self._create_leave(employee, date(2026, 2, 1), date(2026, 2, 10))
        with self.assertRaises(ValidationError):
            self._create_leave(employee, date(2026, 2, 5), date(2026, 2, 15))

    def test_07_payslip_days_incap(self):
        """Payslip debe computar hn_incap_days_patrono_cal y hn_incap_days_ihss_cal."""
        employee = self.create_employee(
            name='Empleado Test 7',
            contract_date_start=date(2026, 2, 1),
        )
        self._create_leave(employee, date(2026, 2, 1), date(2026, 2, 10))
        payslip = self.create_payslip(
            employee,
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 15),
        )
        self.assertEqual(payslip.hn_incap_days_patrono_cal, 3)
        self.assertEqual(payslip.hn_incap_days_ihss_cal, 7)
