# -*- coding: utf-8 -*-

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestInvoicePaymentReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['gn.accounting.invoice.payment.service']
        cls.company = cls.env.company

    def _base_filters(self):
        today = fields.Date.context_today(self)
        return {
            'company_id': self.company.id,
            'payment_period': 'this_month',
            'date_from': today.replace(day=1).isoformat(),
            'date_to': today.isoformat(),
            'show_pending_invoices': True,
            'compare_mode': 'previous',
        }

    def test_filter_options(self):
        opts = self.service.get_filter_options()
        self.assertEqual(opts['company_id'], self.company.id)
        self.assertIn('payment_period_presets', opts)

    def test_dashboard_init(self):
        data = self.service.get_dashboard_init(self._base_filters())
        self.assertTrue(data.get('success'))
        self.assertIn('kpis', data)
        self.assertIn('table', data)
        self.assertIn('cards', data['kpis'])

    def test_pagination_totals_consistency(self):
        filters = self._base_filters()
        full = self.service.get_dashboard_init(filters)
        page = self.service.get_table_page(filters, 1, 10)
        self.assertEqual(page['totals']['amount_total'], full['table']['totals']['amount_total'])

    def test_table_meta_counts(self):
        page = self.service.get_table_page(self._base_filters(), 1, 50)
        self.assertIn('meta', page)
        self.assertIn('payment_count', page['meta'])
        self.assertIn('invoice_count', page['meta'])
        self.assertIn('client_count', page['meta'])

    def test_view_mode_by_invoice(self):
        filters = dict(self._base_filters(), view_mode='by_invoice')
        page = self.service.get_table_page(filters, 1, 100)
        inv_ids = [r['invoice_id'] for r in page['rows']]
        self.assertEqual(len(inv_ids), len(set(inv_ids)))

    def test_view_mode_consolidated_children(self):
        filters = dict(self._base_filters(), view_mode='consolidated')
        page = self.service.get_table_page(filters, 1, 100)
        expandable = [r for r in page['rows'] if r.get('expandable')]
        for row in expandable:
            self.assertIn('children', row)

    def test_group_by_advisor(self):
        page = self.service.get_table_page(self._base_filters(), 1, 50, group_by='advisor')
        if page.get('groups'):
            grp = page['groups'][0]
            self.assertIn('amount_total', grp)
            self.assertIn('invoice_count', grp)
            self.assertIn('payment_count', grp)

    def test_charts_metrics_structure(self):
        data = self.service.get_dashboard_init(self._base_filters())
        adv = data['charts']['advisor_ranking']
        self.assertIn('metrics', adv)
        self.assertIn('paid', adv['metrics'])
        self.assertIn('recovery_pct', adv['metrics'])
        self.assertLessEqual(len(adv['labels']), 11)

    def test_aging_buckets_percentages(self):
        data = self.service.get_dashboard_init(self._base_filters())
        buckets = data['aging']['buckets']
        self.assertIn('pct', buckets['current'])
        total_pct = sum(b['pct'] for b in buckets.values())
        self.assertAlmostEqual(total_pct, 100.0, delta=0.2)

    def test_overdue_page(self):
        filters = dict(self._base_filters(), overdue_filter_mode='overdue_only')
        result = self.service.get_overdue_page(filters, 1, 25)
        self.assertIn('rows', result)
        self.assertIn('totals', result)
        for row in result['rows']:
            self.assertIn('collection_priority', row)

    def test_collection_priority_levels(self):
        pri = self.service._collection_priority({
            'balance_pending': 100000,
            'days_overdue': 95,
            'customer_rank_num': 8,
        }, 100000)
        self.assertIn(pri['level'], ('Alta', 'Media', 'Baja'))
        self.assertIn('tooltip', pri)

    def test_period_bounds(self):
        df, dt = self.service._period_bounds('this_month')
        self.assertLessEqual(df, dt)

    def test_saved_view_crud(self):
        Saved = self.env['gn.accounting.invoice.payment.saved.view']
        result = Saved.save_view('Test vista QA', {'payment_state': 'paid'})
        self.assertTrue(result.get('id'))
        views = Saved.list_views()
        self.assertTrue(any(v['name'] == 'Test vista QA' for v in views))
        Saved.delete_view(result['id'])

    def test_sql_mode_estimate(self):
        agg = self.env['gn.accounting.invoice.payment.aggregation']
        parsed = self.service._parse_filters(self._base_filters())
        count = agg._estimate_row_count(parsed)
        self.assertGreaterEqual(count, 0)

    def test_unique_invoice_totals_no_duplicate(self):
        rows = [
            {'invoice_id': 1, 'amount_total': 100, 'amount_applied': 50, '_has_payment': True},
            {'invoice_id': 1, 'amount_total': 100, 'amount_applied': 50, '_has_payment': True},
        ]
        inv_map = self.service._unique_invoice_totals(rows)
        self.assertEqual(sum(inv_map.values()), 100)

    def test_charts_have_drilldown(self):
        data = self.service.get_dashboard_init(self._base_filters())
        charts = data.get('charts', {})
        self.assertIn('drilldown', charts.get('timeline', {}))
        self.assertIn('drilldown', charts.get('advisor_ranking', {}))

    def test_timeline_respects_period(self):
        filters = dict(self._base_filters(),
                       date_from='2026-07-01', date_to='2026-07-31',
                       payment_period='custom')
        data = self.service.get_dashboard_init(filters)
        labels = data['charts']['timeline']['labels']
        if labels:
            self.assertGreaterEqual(labels[0], '2026-07-01')
            self.assertLessEqual(labels[-1], '2026-07-31')
