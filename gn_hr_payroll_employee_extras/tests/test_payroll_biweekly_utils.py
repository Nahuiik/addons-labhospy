# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.gn_hr_payroll_employee_extras.models.payroll_biweekly_utils import (
    biweekly_date_range,
    biweekly_end_from_start,
    biweekly_start_from_today,
    period_number_from_day,
    spanish_month_name,
)


@tagged("post_install", "-at_install", "gn_payroll_extras")
class TestPayrollBiweeklyUtils(TransactionCase):
    def test_biweekly_date_range_first(self):
        a, b = biweekly_date_range(2026, 3, "1")
        self.assertEqual(a, date(2026, 3, 1))
        self.assertEqual(b, date(2026, 3, 15))

    def test_biweekly_date_range_second(self):
        a, b = biweekly_date_range(2026, 3, 2)
        self.assertEqual(a, date(2026, 3, 16))
        self.assertEqual(b, date(2026, 3, 31))

    def test_period_number_from_day(self):
        self.assertEqual(period_number_from_day(1), "1")
        self.assertEqual(period_number_from_day(15), "1")
        self.assertEqual(period_number_from_day(16), "2")

    def test_biweekly_start_end_roundtrip(self):
        t = date(2026, 4, 10)
        s = biweekly_start_from_today(t)
        self.assertEqual(s, date(2026, 4, 1))
        self.assertEqual(biweekly_end_from_start(s), date(2026, 4, 15))

    def test_spanish_month_name(self):
        self.assertEqual(spanish_month_name(11), "noviembre")
