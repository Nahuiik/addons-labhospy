# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestWeeklyBalance(TransactionCase):
    """Pruebas del motor de balance semanal en gn_banks_balance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        assert cls.bank_journal, 'Se requiere un diario bancario en la compañía.'
        assert cls.bank_journal.default_account_id, (
            'El diario bancario debe tener cuenta de liquidez.'
        )
        cls.bank_journal.write({'gn_include_in_balance_dashboard': True})
        cls.common = cls.env['banks.weekly.balance.common']
        cls.dashboard = cls.env['banks.weekly.balance.dashboard']
        cls.wizard_model = cls.env['banks.weekly.balance.report']
        cls.offset_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('expense', 'expense_direct_cost', 'asset_current')),
        ], limit=1)
        assert cls.offset_account, 'Se requiere una cuenta de contrapartida.'

    def _post_bank_movement(self, move_date, amount, inflow=True):
        liquidity = self.bank_journal.default_account_id
        line_liq = {
            'account_id': liquidity.id,
            'debit': amount if inflow else 0.0,
            'credit': 0.0 if inflow else amount,
        }
        line_offset = {
            'account_id': self.offset_account.id,
            'debit': 0.0 if inflow else amount,
            'credit': amount if inflow else 0.0,
        }
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': move_date,
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, line_liq), (0, 0, line_offset)],
        })
        move.action_post()
        return move

    def _wizard(self, **extra):
        vals = {
            'company_id': self.company.id,
            'year': 2026,
            'month': '1',
            'journal_ids': [(6, 0, self.bank_journal.ids)],
        }
        vals.update(extra)
        return self.wizard_model.create(vals)

    def test_period_bucket_ranges(self):
        from datetime import date
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        _ps, _pe, week_ranges = self.common._period_bucket_ranges(start, end, 'week')
        self.assertGreaterEqual(len(week_ranges), 4)
        _ps, _pe, fn_ranges = self.common._period_bucket_ranges(start, end, 'fortnight')
        self.assertGreaterEqual(len(fn_ranges), 2)
        _ps, _pe, month_ranges = self.common._period_bucket_ranges(start, end, 'month')
        self.assertEqual(len(month_ranges), 1)

    def test_build_dashboard_payload_structure(self):
        self._post_bank_movement('2026-01-05', 1000.0, inflow=True)
        self._post_bank_movement('2026-01-06', 200.0, inflow=False)
        wizard = self._wizard(month='1', year=2026)
        payload = self.common.build_dashboard_payload(wizard, {'group_by': 'week'})
        self.assertTrue(payload.get('has_data'))
        self.assertIn('kpis', payload)
        self.assertIn('weeks', payload)
        self.assertIn('charts', payload)
        self.assertIn('waterfall', payload['charts'])
        self.assertIn('cashflow', payload['charts'])
        self.assertIn('balance_evolution', payload['charts'])
        kpis = payload['kpis']
        for key in (
            'initial_balance', 'final_balance', 'total_inflows', 'total_outflows',
            'net_flow', 'average_weekly_liquidity',
        ):
            self.assertIn(key, kpis)
        self.assertGreaterEqual(kpis['total_inflows'], 1000.0)
        self.assertGreaterEqual(kpis['total_outflows'], 200.0)

    def test_week_balance_coherence(self):
        self._post_bank_movement('2026-01-08', 500.0, inflow=True)
        wizard = self._wizard(month='1', year=2026)
        payload = self.common.build_dashboard_payload(wizard)
        for week in payload.get('weeks', []):
            expected_final = round(week['initial_balance'] + week['net_flow'], 2)
            self.assertAlmostEqual(week['final_balance'], expected_final, places=2)
            self.assertAlmostEqual(
                week['net_flow'],
                round(week['inflows'] - week['outflows'], 2),
                places=2,
            )

    def test_waterfall_steps(self):
        self._post_bank_movement('2026-01-03', 300.0, inflow=True)
        wizard = self._wizard(month='1', year=2026)
        payload = self.common.build_dashboard_payload(wizard)
        steps = payload['waterfall']
        self.assertTrue(steps)
        self.assertEqual(steps[0]['type'], 'initial')
        self.assertIn(steps[-1]['type'], ('final', 'total'))
        self.assertIn('short_label', steps[0])
        self.assertIn('running_balance', steps[0])

    def test_insights_structure(self):
        self._post_bank_movement('2026-01-04', 800.0, inflow=False)
        wizard = self._wizard(month='1', year=2026)
        payload = self.common.build_dashboard_payload(wizard)
        self.assertTrue(payload.get('insights'))
        first = payload['insights'][0]
        self.assertIn('category', first)
        self.assertIn('severity', first)
        self.assertIn('title', first)
        self.assertIn('message', first)

    def test_rpc_get_bank_weekly_dashboard_data(self):
        self._post_bank_movement('2026-01-07', 150.0, inflow=True)
        filters = {
            'company_id': self.company.id,
            'year': 2026,
            'month': '1',
            'journal_ids': self.bank_journal.ids,
            'compare_previous': False,
            'group_by': 'week',
        }
        data = self.dashboard.get_bank_weekly_dashboard_data(filters)
        self.assertTrue(data.get('has_data'))
        self.assertTrue(data.get('currency', {}).get('id'))

    def test_drilldown_preview_inflow(self):
        wizard = self._wizard(month='1', year=2026)
        _ps, _pe, ranges = self.common.resolve_period_and_ranges(wizard, 'week')
        week_no, w_start, _w_end = ranges[0]
        self._post_bank_movement(w_start.isoformat(), 250.0, inflow=True)
        filters = {
            'company_id': self.company.id,
            'year': 2026,
            'month': '1',
            'journal_ids': self.bank_journal.ids,
            'group_by': 'week',
        }
        preview = self.dashboard.get_drilldown_preview(
            filters,
            {'week_no': week_no, 'journal_id': self.bank_journal.id, 'metric': 'inflow'},
            50,
        )
        self.assertGreaterEqual(preview.get('count', 0), 1)
        self.assertTrue(preview.get('lines'))

    def test_search_balance_journals_respects_flag(self):
        other = self.bank_journal.copy({'name': 'Banco sin dashboard', 'code': 'BNKWB2'})
        other.write({'gn_include_in_balance_dashboard': False})
        journals = self.common.search_balance_journals(self.company.id)
        self.assertIn(self.bank_journal, journals)
        self.assertNotIn(other, journals)

    def test_open_weekly_dashboard_action_from_balances(self):
        action = self.bank_journal.action_open_weekly_balance_dashboard()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'gn_banks_balance_weekly_dashboard')
        self.assertIn(self.bank_journal.id, action['context']['dashboard_journal_ids'])
        self.assertEqual(action['context']['dashboard_company_id'], self.company.id)

    def test_open_weekly_dashboard_action_selected_journals(self):
        other = self.bank_journal.copy({
            'name': 'Banco dashboard 2',
            'code': 'BNKWB3',
            'gn_include_in_balance_dashboard': True,
        })
        action = (self.bank_journal + other).action_open_weekly_balance_dashboard()
        self.assertEqual(
            sorted(action['context']['dashboard_journal_ids']),
            sorted([self.bank_journal.id, other.id]),
        )

    def test_collect_period_buckets_aggregations(self):
        wizard = self._wizard(month='1', year=2026)
        _ps, _pe, ranges = self.common.resolve_period_and_ranges(wizard, 'week')
        account_id = self.bank_journal.default_account_id.id
        agg_before = self.common._collect_period_buckets(
            self.company, [account_id], ranges,
        )
        self._post_bank_movement('2026-01-05', 1000.0, inflow=True)
        self._post_bank_movement('2026-01-06', 200.0, inflow=False)
        self._post_bank_movement('2026-01-15', 500.0, inflow=True)
        agg = self.common._collect_period_buckets(
            self.company, [account_id], ranges,
        )
        self.assertIn('base_balance', agg)
        self.assertIn('end_balance', agg)
        self.assertIn('agg_debit', agg)
        self.assertIn('agg_credit', agg)
        self.assertIn('buckets', agg)
        delta_in = (
            agg['agg_debit'][account_id]
            - agg_before['agg_debit'].get(account_id, 0.0)
        )
        delta_out = (
            agg['agg_credit'][account_id]
            - agg_before['agg_credit'].get(account_id, 0.0)
        )
        self.assertAlmostEqual(delta_in, 1500.0, places=2)
        self.assertAlmostEqual(delta_out, 200.0, places=2)
        for week_no in agg['buckets']:
            bucket = agg['buckets'][week_no]
            expected_final = (
                bucket['opening'][account_id]
                + bucket['inflow'][account_id]
                - bucket['outflow'][account_id]
            )
            self.assertAlmostEqual(
                bucket['final'][account_id], expected_final, places=2,
            )

    def test_payload_aggregations_cache_present(self):
        wizard = self._wizard(month='1', year=2026)
        payload = self.common.build_dashboard_payload(wizard, {'group_by': 'week'})
        self.assertTrue(payload.get('has_data'))
        self.assertIn(
            '_aggregations', payload,
            msg='Aggregations cache must remain in build_dashboard_payload so '
                'financial_health can reuse it; RPC layer pops it before send.',
        )
        agg = payload['_aggregations']
        for key in ('base_balance', 'end_balance', 'agg_debit', 'agg_credit', 'buckets'):
            self.assertIn(key, agg)

    def test_payload_consistency_post_refactor(self):
        wizard = self._wizard(month='1', year=2026)
        baseline = self.common.build_dashboard_payload(
            wizard, {'group_by': 'week'},
        )
        baseline_kpis = baseline['kpis']
        self._post_bank_movement('2026-01-04', 700.0, inflow=True)
        self._post_bank_movement('2026-01-09', 250.0, inflow=False)
        self._post_bank_movement('2026-01-22', 400.0, inflow=False)
        payload = self.common.build_dashboard_payload(wizard, {'group_by': 'week'})
        kpis = payload['kpis']
        self.assertAlmostEqual(
            kpis['total_inflows'] - baseline_kpis.get('total_inflows', 0.0),
            700.0, places=2,
        )
        self.assertAlmostEqual(
            kpis['total_outflows'] - baseline_kpis.get('total_outflows', 0.0),
            650.0, places=2,
        )
        self.assertAlmostEqual(
            kpis['net_flow'] - baseline_kpis.get('net_flow', 0.0),
            50.0, places=2,
        )
        weeks = payload['weeks']
        self.assertTrue(weeks)
        if len(weeks) >= 2:
            self.assertAlmostEqual(
                weeks[1]['initial_balance'],
                weeks[0]['final_balance'],
                places=2,
            )

    def test_build_dashboard_payload_query_count(self):
        for day in (3, 7, 12, 18, 25):
            self._post_bank_movement(f'2026-01-{day:02d}', 100.0 + day, inflow=True)
            self._post_bank_movement(f'2026-01-{day:02d}', 30.0 + day, inflow=False)
        wizard = self._wizard(month='1', year=2026)
        self.env.flush_all()
        self.env.invalidate_all()
        count_before = self.cr.sql_log_count
        payload = self.common.build_dashboard_payload(
            wizard, {'group_by': 'week'},
        )
        self.env.flush_all()
        queries = self.cr.sql_log_count - count_before
        self.assertTrue(payload.get('has_data'))
        self.assertLess(
            queries, 25,
            'build_dashboard_payload should issue fewer than 25 queries '
            'after the bucket aggregation refactor (got %s).' % queries,
        )

    def test_fetch_bucket_metrics_reproducible(self):
        wizard = self._wizard(month='1', year=2026)
        _ps, _pe, ranges = self.common.resolve_period_and_ranges(wizard, 'week')
        account_id = self.bank_journal.default_account_id.id
        baseline_metrics = self.common._fetch_bucket_metrics(
            self.company, [account_id], ranges,
        )
        baseline_count = sum(m['movement_count'] for m in baseline_metrics.values())
        baseline_max = max(
            (m['largest_movement'] for m in baseline_metrics.values()),
            default=0.0,
        )
        self._post_bank_movement('2026-01-05', 750.0, inflow=True)
        self._post_bank_movement('2026-01-06', 320.0, inflow=False)
        self._post_bank_movement('2026-01-15', 200.0, inflow=True)
        metrics = self.common._fetch_bucket_metrics(
            self.company, [account_id], ranges,
        )
        total_count = sum(m['movement_count'] for m in metrics.values())
        self.assertEqual(total_count - baseline_count, 3)
        biggest = max(m['largest_movement'] for m in metrics.values())
        self.assertGreaterEqual(biggest, max(750.0, baseline_max))
