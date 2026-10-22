# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestHnVacationPlan(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Plan = self.env['gn.hn.vacation.plan']
        self.Rule = self.env['gn.hn.vacation.rule']
        self.company = self.env.company

    def test_plan_get_days_for_seniority(self):
        plan = self.Plan.create({
            'name': 'Test Plan',
            'code': 'TEST',
        })
        self.Rule.create([
            {'plan_id': plan.id, 'min_years': 1, 'max_years': 2, 'days_entitled': 10},
            {'plan_id': plan.id, 'min_years': 3, 'max_years': 5, 'days_entitled': 15},
            {'plan_id': plan.id, 'min_years': 6, 'max_years': 99, 'days_entitled': 20},
        ])
        self.assertEqual(plan.get_days_for_seniority(1), 10)
        self.assertEqual(plan.get_days_for_seniority(2), 10)
        self.assertEqual(plan.get_days_for_seniority(3), 15)
        self.assertEqual(plan.get_days_for_seniority(5), 15)
        self.assertEqual(plan.get_days_for_seniority(6), 20)
        self.assertEqual(plan.get_days_for_seniority(10), 20)
        self.assertEqual(plan.get_days_for_seniority(0), 0)

    def test_plan_get_days_sin_reglas(self):
        """Plan sin reglas retorna 0."""
        plan = self.Plan.create({
            'name': 'Plan vacío',
            'code': 'EMPTY',
        })
        self.assertEqual(plan.get_days_for_seniority(1), 0)
        self.assertEqual(plan.get_days_for_seniority(5), 0)

    def test_plan_constraint_codigo_unico(self):
        """El código debe ser único por compañía."""
        self.Plan.create({
            'name': 'Plan A',
            'code': 'UNIQUE',
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.Plan.create({
                'name': 'Plan B',
                'code': 'UNIQUE',
            })

    def test_plan_allow_proportional(self):
        """Plan con allow_proportional y allow_monthly_proportional."""
        plan = self.Plan.create({
            'name': 'Plan proporcional',
            'code': 'PROP',
            'allow_proportional': True,
            'allow_monthly_proportional': True,
        })
        self.Rule.create({
            'plan_id': plan.id,
            'min_years': 1,
            'max_years': 99,
            'days_entitled': 12,
        })
        self.assertTrue(plan.allow_proportional)
        self.assertTrue(plan.allow_monthly_proportional)
        self.assertEqual(plan.get_days_for_seniority(1), 12)

    def test_plan_vacation_accrual_mode_default(self):
        plan = self.Plan.create({'name': 'Modo', 'code': 'MODE'})
        self.assertEqual(plan.vacation_accrual_mode, 'annual')
