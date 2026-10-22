# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase


class TestHnVacationPayroll(TransactionCase):

    def test_salary_average_6m_uses_history_when_present(self):
        History = self.env['l10n.hn.employee.monthly.salary.history']
        Employee = self.env['hr.employee']
        emp = Employee.search([('active', '=', True)], limit=1)
        if not emp or not History:
            self.skipTest('Requiere empleado e historial HN')
        d = date(2026, 6, 15)
        base_month = d.replace(day=1) - relativedelta(months=1)
        History.search([
            ('employee_id', '=', emp.id),
            ('year', '=', base_month.year),
            ('month', '=', base_month.month),
        ]).unlink()
        History.create({
            'employee_id': emp.id,
            'year': base_month.year,
            'month': base_month.month,
            'amount_net': 3000.0,
            'amount_commission': 0.0,
            'data_source': 'manual',
        })
        avg = emp._hn_vacation_payroll_salary_average_6m(d)
        self.assertGreater(avg, 0)

    def test_accrued_cash_days_respects_settled(self):
        Allocation = self.env['hr.leave.allocation']
        Employee = self.env['hr.employee']
        LeaveType = self.env['hr.leave.type']
        emp = Employee.search([('active', '=', True)], limit=1)
        if not emp:
            self.skipTest('Requiere tipo vacaciones HN y empleado')
        vtype = LeaveType.gn_primary_vacation_leave_type(emp.company_id or self.env.company)
        if not vtype:
            self.skipTest('Requiere tipo vacaciones principal para país de la compañía')
        alloc = Allocation.search([
            ('employee_id', '=', emp.id),
            ('holiday_status_id', '=', vtype.id),
            ('state', '=', 'validate'),
        ], limit=1)
        if not alloc:
            self.skipTest('Requiere asignación HN validada')
        prev = alloc.hn_vac_payroll_settled_days or 0.0
        try:
            alloc.hn_vac_payroll_settled_days = prev + 1.0
            r_before = emp._hn_vacation_payroll_accrued_cash_days()
            alloc.hn_vac_payroll_settled_days = prev
            r_after = emp._hn_vacation_payroll_accrued_cash_days()
            self.assertGreater(r_after, r_before)
        finally:
            alloc.hn_vac_payroll_settled_days = prev

    def test_vacation_structure_has_kind(self):
        struct = self.env.ref('l10n_hn_hr_payroll.structure_hn_vacation_anniversary', raise_if_not_found=False)
        if not struct:
            self.skipTest('Estructura XML no cargada')
        self.assertEqual(struct.hn_vacation_payroll_kind, 'anniversary_month')
