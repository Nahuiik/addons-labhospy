# -*- coding: utf-8 -*-

import logging
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestSalesDashboardMetrics(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('gn_sales_dashboard.group_sales_dashboard_user')
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'group_ids': [(4, cls.group.id)]})
        cls.service = cls.env['sales.dashboard.service'].with_user(cls.admin)

    def test_get_filter_options(self):
        opts = self.service.get_filter_options()
        self.assertIn('period_presets', opts)
        self.assertIn('branches', opts)
        self.assertTrue(opts['company_id'])

    def test_get_dashboard_init(self):
        data = self.service.get_dashboard_init({'period': 'this_month'})
        self.assertTrue(data['success'])
        self.assertIn('core', data)
        self.assertIn('advanced', data)
        self.assertIn('health', data['advanced'])
        self.assertIn('kpis', data['core'])

    def test_get_dashboard_core(self):
        data = self.service.get_dashboard_core({'period': 'this_month'})
        self.assertTrue(data['success'])
        self.assertIn('kpis', data)
        self.assertGreater(len(data['kpis']), 0)
        self.assertIn('hero_sales', data['charts'])
        self.assertIn('generated_at', data['header'])

    def test_drilldown_has_views(self):
        action = self.service.get_drilldown_action('net_sales', [], {'period': 'this_month'})
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertIn('views', action)
        self.assertTrue(action['views'])

    def test_credit_notes_subtracted_from_net(self):
        parsed = self.service._parse_filters({'period': 'this_year'})
        metrics = self.service._compute_metrics(parsed)
        net = metrics['net_sales']['value']
        gross = metrics['gross_invoicing']['value']
        credits = metrics['credit_notes']['value']
        self.assertLessEqual(net, gross + 1e-6)
        if credits:
            self.assertAlmostEqual(net, gross - credits, places=2)

    def test_get_dashboard_widgets(self):
        data = self.service.get_dashboard_widgets({'period': 'this_month'}, [
            'seller_ranking', 'team_ranking', 'top_products', 'top_customers',
            'pipeline_funnel', 'pipeline_chart',
        ])
        self.assertTrue(data['success'])
        widgets = data['widgets']
        self.assertIn('seller_ranking', widgets)
        self.assertIn('pipeline_chart', widgets)

    def test_get_table_page(self):
        page = self.service.get_table_page(
            {'period': 'this_month'}, 'recent_invoices', 1, 10, '', 'date desc',
        )
        self.assertIn('rows', page)
        self.assertIn('columns', page)
        self.assertGreater(len(page['columns']), 0)

    def test_entity_drilldown_has_views(self):
        action = self.service.get_entity_drilldown(
            {'period': 'this_month'}, 'account.move', [], 'Facturas',
        )
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertIn('views', action)

    def test_get_dashboard_advanced(self):
        data = self.service.get_dashboard_advanced({'period': 'this_month'}, [
            'health', 'forecast', 'rfm', 'alerts', 'goal_tracker',
        ])
        self.assertTrue(data['success'])
        self.assertIn('score', data['advanced']['health'])
        self.assertIn('method', data['advanced']['forecast'])

    def test_export_kpis_csv(self):
        result = self.service.export_kpis_csv({'period': 'this_month'})
        self.assertEqual(result['filename'], 'ventas_kpis.csv')
        self.assertTrue(result['data'])

    def test_kpi_semantics_fields(self):
        data = self.service.get_dashboard_core({'period': 'this_month'})
        kpis = {k['key']: k for k in data['kpis']}
        for key in ('net_sales', 'credit_notes', 'target_achievement'):
            self.assertIn(key, kpis)
            self.assertIn('has_data', kpis[key])
            self.assertIn('tier', kpis[key])
            self.assertIn('direction', kpis[key])
            self.assertIn('semantic_tone', kpis[key])
        self.assertEqual(kpis['net_sales']['tier'], 'primary')
        self.assertEqual(kpis['credit_notes']['tier'], 'secondary')
        self.assertEqual(kpis['growth']['tier'], 'secondary')
        self.assertEqual(kpis['credit_notes']['direction'], 'down')

    def test_growth_empty_without_compare(self):
        data = self.service.get_dashboard_core({'period': 'this_month', 'compare_mode': 'none'})
        growth = next(k for k in data['kpis'] if k['key'] == 'growth')
        self.assertFalse(growth['has_data'])
        self.assertTrue(growth['empty_reason'])

    def test_init_summary_enrichment(self):
        data = self.service.get_dashboard_init({'period': 'this_month'})
        adv = data['advanced']
        self.assertIn('insights', adv)
        self.assertIn('top5', adv)
        self.assertIn('closing_forecast', adv)
        self.assertIn('title', adv['health'])
        self.assertIn('factors', adv['health'])
        if adv['health']['factors']:
            factor = adv['health']['factors'][0]
            self.assertIn('normalized_score', factor)
            self.assertIn('weighted_score', factor)
            self.assertIn('description', factor)
        alerts = adv.get('alerts', {})
        self.assertIn('counts', alerts)
        goal = adv.get('goal_tracker', {})
        self.assertIn('is_configured', goal)
        self.assertIn('gap', goal)
