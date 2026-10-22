# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestHnVacationValidation(TransactionCase):
    """Tests de validaciones críticas: anticipación mínima, aniversario."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env['hr.employee']
        cls.LeaveType = cls.env['hr.leave.type']
        cls.Leave = cls.env['hr.leave']
        cls.Plan = cls.env['gn.hn.vacation.plan']
        cls.company = cls.env.company
        cls.vacation_type = cls.LeaveType.gn_primary_vacation_leave_type(cls.company)
        if not cls.vacation_type:
            raise Exception('No HN vacation type in database')
        cls.plan = cls.Plan.search([('company_id', 'in', [False, cls.company.id])], limit=1)
        if not cls.plan:
            cls.plan = cls.Plan.create({
                'name': 'Test Plan',
                'code': 'TESTVAL',
            })
            cls.env['gn.hn.vacation.rule'].create({
                'plan_id': cls.plan.id,
                'min_years': 1,
                'max_years': 99,
                'days_entitled': 15,
            })
        cls.emp = cls.Employee.search([('active', '=', True)], limit=1)
        if not cls.emp:
            raise Exception('No active employee in database')

    def test_approve_less_than_10_days_only_hr_manager(self):
        """Con menos de 10 días solo RR.HH. puede aprobar; no exige motivo en la solicitud."""
        today = date.today()
        date_from = today + timedelta(days=5)
        date_to = date_from + timedelta(days=4)
        leave = self.Leave.create({
            'name': ' ',
            'employee_id': self.emp.id,
            'holiday_status_id': self.vacation_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'state': 'confirm',
        })
        mgr_group = self.env.ref('hr_holidays.group_hr_holidays_manager')
        hr_user = self.env['res.users'].create({
            'name': 'Test HR manager min days',
            'login': 'hr_mgr_mindays_%s' % self.emp.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, mgr_group.id])],
        })
        leave.with_user(hr_user).action_approve()
        self.assertEqual(leave.state, 'validate')

    def test_hn_vacation_backend_create_when_portal_disabled(self):
        """Portal bloqueado no impide crear vacaciones HN desde el backend."""
        today = date.today()
        date_to = today + timedelta(days=4)
        prev = self.emp.hn_vacation_requests_allowed
        self.emp.hn_vacation_requests_allowed = False
        try:
            leave = self.Leave.create({
                'name': 'Desde backend con portal desactivado',
                'employee_id': self.emp.id,
                'holiday_status_id': self.vacation_type.id,
                'request_date_from': today,
                'request_date_to': date_to,
            })
            self.assertTrue(leave.id)
            self.assertTrue(leave.gn_vacation_is_primary)
        finally:
            self.emp.hn_vacation_requests_allowed = prev

    def test_anniversary_rule_min_start_first_year(self):
        """Antes del primer aniversario la fecha mínima es ingreso + 1 año."""
        self.emp.contract_date_start = date(2024, 3, 10)
        d = date(2024, 9, 1)
        min_s = self.emp._hn_min_vacation_start_for_anniversary_rule(d)
        self.assertEqual(min_s, date(2025, 3, 10))

    def test_anniversary_rule_min_start_same_year_before_anniversary(self):
        """Tras el primer año, antes del aniversario del año de la solicitud aún aplica la fecha."""
        self.emp.contract_date_start = date(2020, 6, 15)
        d = date(2025, 5, 1)
        min_s = self.emp._hn_min_vacation_start_for_anniversary_rule(d)
        self.assertEqual(min_s, date(2025, 6, 15))

    def test_anniversary_rule_min_start_none_after_anniversary(self):
        self.emp.contract_date_start = date(2020, 6, 15)
        d = date(2025, 8, 1)
        min_s = self.emp._hn_min_vacation_start_for_anniversary_rule(d)
        self.assertIsNone(min_s)

    def test_anniversary_blocks_admin_without_explicit_override(self):
        """Responsable de Ausencias ya no omite la regla salvo excepción explícita."""
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        today = date.today()
        try:
            with self.assertRaises(ValidationError):
                self.Leave.create({
                    'name': 'Sin excepción',
                    'employee_id': self.emp.id,
                    'holiday_status_id': self.vacation_type.id,
                    'request_date_from': today,
                    'request_date_to': today,
                })
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire

    def test_anniversary_allowed_with_context_override(self):
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        today = date.today()
        try:
            leave = self.Leave.with_context(gn_allow_anniversary_vacation_override=True).create({
                'name': 'Import / masivo',
                'employee_id': self.emp.id,
                'holiday_status_id': self.vacation_type.id,
                'request_date_from': today,
                'request_date_to': today,
            })
            self.assertTrue(leave.id)
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire

    def test_anniversary_allowed_with_leave_exception_flag(self):
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        today = date.today()
        try:
            leave = self.Leave.create({
                'name': 'RRHH excepción',
                'employee_id': self.emp.id,
                'holiday_status_id': self.vacation_type.id,
                'request_date_from': today,
                'request_date_to': today,
                'gn_allow_before_anniversary_vacation': True,
            })
            self.assertTrue(leave.id)
            self.assertTrue(leave.gn_allow_before_anniversary_vacation)
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire

    def test_anniversary_blocks_hr_officer_without_manager(self):
        """Oficial de Ausencias sin Responsable no debe poder crear fuera de la regla."""
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        officer_only = self.env['res.users'].create({
            'name': 'Officer anniv block test',
            'login': 'officer_anniv_block_%s' % self.emp.id,
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_holidays.group_hr_holidays_user').id,
            ])],
        })
        today = date.today()
        try:
            with self.assertRaises(ValidationError):
                self.env['hr.leave'].with_user(officer_only).create({
                    'name': ' ',
                    'employee_id': self.emp.id,
                    'holiday_status_id': self.vacation_type.id,
                    'request_date_from': today,
                    'request_date_to': today,
                })
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire

    def test_anniversary_assert_blocks_plain_user_when_type_requires(self):
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        prev_ov = self.emp.hn_override_anniversary_vacation_block
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        no_hr = self.env['res.users'].create({
            'name': 'Test no HR anniv',
            'login': 'nohr_anniv_test_%s' % self.emp.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        try:
            with self.assertRaises(ValidationError):
                self.env['hr.leave'].with_user(no_hr)._gn_assert_anniversary_vacation_start(
                    self.emp, self.vacation_type, date.today()
                )
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire
            self.emp.hn_override_anniversary_vacation_block = prev_ov

    def test_anniversary_create_under_sudo_enforces_real_uid(self):
        """Si create va con sudo (portal), la regla debe usar gn_leave_real_uid, no el superusuario."""
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        prev_ov = self.emp.hn_override_anniversary_vacation_block
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = False
        no_hr = self.env['res.users'].create({
            'name': 'Test portal sudo anniv',
            'login': 'portal_sudo_anniv_%s' % self.emp.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        try:
            with self.assertRaises(ValidationError):
                self.env['hr.leave'].sudo().with_context(gn_leave_real_uid=no_hr.id).create({
                    'name': ' ',
                    'employee_id': self.emp.id,
                    'holiday_status_id': self.vacation_type.id,
                    'request_date_from': date.today(),
                    'request_date_to': date.today(),
                })
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire
            self.emp.hn_override_anniversary_vacation_block = prev_ov

    def test_anniversary_assert_respects_employee_override(self):
        prev_block = self.vacation_type.gn_vacation_block_before_anniversary
        self.vacation_type.gn_vacation_block_before_anniversary = True
        hire = date.today() - timedelta(days=100)
        prev_hire = self.emp.contract_date_start
        prev_ov = self.emp.hn_override_anniversary_vacation_block
        self.emp.contract_date_start = hire
        self.emp.hn_override_anniversary_vacation_block = True
        no_hr = self.env['res.users'].create({
            'name': 'Test no HR anniv 2',
            'login': 'nohr_anniv2_%s' % self.emp.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        try:
            self.env['hr.leave'].with_user(no_hr)._gn_assert_anniversary_vacation_start(
                self.emp, self.vacation_type, date.today()
            )
        finally:
            self.vacation_type.gn_vacation_block_before_anniversary = prev_block
            self.emp.contract_date_start = prev_hire
            self.emp.hn_override_anniversary_vacation_block = prev_ov

    def test_compute_hn_vacation_data_no_error(self):
        """_compute_hn_vacation_data no debe fallar con múltiples empleados."""
        emps = self.Employee.search([('active', '=', True)], limit=5)
        if len(emps) < 2:
            self.skipTest('Need at least 2 employees')
        for emp in emps:
            _ = emp.hn_current_balance
            _ = emp.hn_vacation_balance
            _ = emp.hn_current_entitled_days
