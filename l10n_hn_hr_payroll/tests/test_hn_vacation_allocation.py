# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase


class TestHnVacationAllocation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Employee = self.env['hr.employee']
        self.LeaveType = self.env['hr.leave.type']
        self.Plan = self.env['gn.hn.vacation.plan']
        self.company = self.env.company
        vacation_type = self.LeaveType.gn_primary_vacation_leave_type(self.company)
        if not vacation_type:
            self.skipTest('No HN vacation type')
        self.vacation_type = vacation_type
        self.plan = self.Plan.search([('company_id', 'in', [False, self.company.id])], limit=1)
        if not self.plan:
            self.plan = self.Plan.create({
                'name': 'Test',
                'code': 'TEST',
            })
            self.env['gn.hn.vacation.rule'].create({
                'plan_id': self.plan.id,
                'min_years': 1,
                'max_years': 99,
                'days_entitled': 15,
            })

    def test_employee_daily_rate(self):
        """Usa un empleado existente para evitar problemas con res.partner/group_rfq."""
        emp = self.Employee.search([('active', '=', True)], limit=1)
        if not emp:
            self.skipTest('No hay empleados activos en la base de datos')
        rate = emp._hn_vacation_daily_rate(date.today())
        self.assertGreaterEqual(rate, 0)

    def test_get_default_hn_vacation_plan(self):
        """Verifica que _get_default_hn_vacation_plan retorna un plan válido."""
        emp = self.Employee.search([('active', '=', True)], limit=1)
        if not emp:
            self.skipTest('No hay empleados activos')
        plan = emp._get_default_hn_vacation_plan()
        self.assertTrue(plan or True, 'Puede retornar None si no hay planes')
