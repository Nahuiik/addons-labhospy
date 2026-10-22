# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo.tests.common import TransactionCase


class TestHnVacationCron(TransactionCase):

    def test_cron_monthly_proportional_no_error(self):
        """El cron de acumulación mensual se ejecuta sin error."""
        self.env['hr.employee']._cron_hn_vacation_monthly_proportional()

    def test_cron_annual_allocation_no_error(self):
        """El cron de asignación anual se ejecuta sin error."""
        self.env['hr.employee']._cron_hn_vacation_annual_allocation()

    def test_cron_notifications_no_error(self):
        """El cron de notificaciones se ejecuta sin error."""
        self.env['hr.employee']._cron_hn_vacation_notifications()
