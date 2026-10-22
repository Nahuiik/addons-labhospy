# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.gn_hr_dashboard.controllers.dashboard import GnHrDashboardController


@tagged("at_install")
class TestGnHrDashboardPeriod(TransactionCase):
    def test_previous_calendar_month_bounds(self):
        ctrl = GnHrDashboardController()
        start, end = ctrl._previous_calendar_month_bounds(date(2025, 3, 15))
        self.assertEqual(start, date(2025, 2, 1))
        self.assertEqual(end, date(2025, 2, 28))
        start2, end2 = ctrl._previous_calendar_month_bounds(date(2025, 1, 5))
        self.assertEqual(start2, date(2024, 12, 1))
        self.assertEqual(end2, date(2024, 12, 31))

    def test_resolve_period_month(self):
        ctrl = GnHrDashboardController()
        d0, d1, mode = ctrl._resolve_period(self.env, 2025, 2, None, None)
        self.assertEqual(mode, "month")
        self.assertEqual(d0, date(2025, 2, 1))
        self.assertEqual(d1, date(2025, 2, 28))

    def test_resolve_period_range(self):
        ctrl = GnHrDashboardController()
        d0, d1, mode = ctrl._resolve_period(
            self.env, 2020, 1, "2025-06-10", "2025-06-01"
        )
        self.assertEqual(mode, "range")
        self.assertEqual(d0, date(2025, 6, 1))
        self.assertEqual(d1, date(2025, 6, 10))

    def test_is_module_installed(self):
        ctrl = GnHrDashboardController()
        self.assertTrue(ctrl._is_module_installed(self.env, "base"))
        self.assertFalse(
            ctrl._is_module_installed(self.env, "nonexistent_module_xyz_123")
        )

    def test_tenure_band_label(self):
        ctrl = GnHrDashboardController()
        self.assertEqual(ctrl._tenure_band_label(0.2), "<1")
        self.assertEqual(ctrl._tenure_band_label(1.0), "1-3")
        self.assertEqual(ctrl._tenure_band_label(2.5), "1-3")
        self.assertEqual(ctrl._tenure_band_label(3.0), "3-5")
        self.assertEqual(ctrl._tenure_band_label(7.0), "5-10")
        self.assertEqual(ctrl._tenure_band_label(10.0), "10+")
