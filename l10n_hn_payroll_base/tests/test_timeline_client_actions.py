# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_hn_payroll_base")
class TestTimelineClientActions(TransactionCase):
    """Pruebas rápidas: menús apuntan a acciones cliente existentes en base de datos."""

    def test_ce_planning_client_action(self):
        action = self.env.ref(
            "l10n_hn_payroll_base.action_hn_holidays_timeline_ce",
            raise_if_not_found=False,
        )
        self.assertTrue(action, "Falta ir.actions.client CE en datos del módulo")
        self.assertEqual(action.tag, "hn_holidays_timeline_ce")

    def test_oss_lab_client_action(self):
        action = self.env.ref(
            "l10n_hn_payroll_base.action_hn_holidays_timeline_oss",
            raise_if_not_found=False,
        )
        self.assertTrue(action, "Falta ir.actions.client OSS lab en datos del módulo")
        self.assertEqual(action.tag, "hn_holidays_timeline_oss")
