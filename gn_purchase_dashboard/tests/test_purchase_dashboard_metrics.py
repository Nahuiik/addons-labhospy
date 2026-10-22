# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.exceptions import AccessError

from odoo.addons.base.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPurchaseDashboardMetrics(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref('gn_purchase_dashboard.group_purchase_dashboard_user')
        cls.env.user.write({'group_ids': [(4, cls.group_user.id)]})
        cls.service = cls.env['purchase.dashboard.service']

    def test_filter_options(self):
        opts = self.service.get_filter_options()
        self.assertIn('period_presets', opts)
        self.assertIn('vendors', opts)
        self.assertIn('buyers', opts)

    def test_dashboard_init(self):
        result = self.service.get_dashboard_init({'period': 'this_month'})
        self.assertTrue(result['core']['success'])
        self.assertTrue(len(result['core']['kpis']) >= 12)
        self.assertIn('health', result['advanced'])
        self.assertIn('alerts', result['advanced'])
        self.assertIn('insights', result['advanced'])

    def test_dashboard_widgets(self):
        keys = ['monthly_purchases', 'top_vendors', 'forecast', 'sankey_flow', 'waterfall_financial']
        result = self.service.get_dashboard_widgets({'period': 'this_month'}, keys)
        self.assertTrue(result['success'])
        for key in keys:
            self.assertIn(key, result['widgets'])
        sankey = result['widgets']['sankey_flow']
        self.assertIn('nodes', sankey)
        self.assertIn('links', sankey)
        waterfall = result['widgets']['waterfall_financial']
        self.assertIn('steps', waterfall)

    def test_drilldown_action(self):
        action = self.service.get_drilldown_action('total_purchased', [], {'period': 'this_month'})
        self.assertEqual(action['res_model'], 'purchase.order')
        self.assertIn('domain', action)

    def test_access_control(self):
        user = self.env['res.users'].create({
            'name': 'Purchase Dashboard Denied',
            'login': 'pd_denied_test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.service.with_user(user).get_dashboard_init({})
