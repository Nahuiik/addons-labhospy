# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestFinancialHealth(TransactionCase):
    """Pruebas de indicadores de salud financiera."""

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
        cls.health = cls.env['banks.financial.health']
        cls.dashboard = cls.env['banks.weekly.balance.dashboard']
        cls.wizard_model = cls.env['banks.weekly.balance.report']
        cls.offset_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('expense', 'expense_direct_cost', 'asset_current')),
        ], limit=1)
        assert cls.offset_account, 'Se requiere una cuenta de contrapartida.'

    def _post_bank_movement(self, move_date, amount, inflow=True):
        liquidity = self.bank_journal.default_account_id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': move_date,
            'journal_id': self.bank_journal.id,
            'line_ids': [
                (0, 0, {
                    'account_id': liquidity.id,
                    'debit': amount if inflow else 0.0,
                    'credit': 0.0 if inflow else amount,
                }),
                (0, 0, {
                    'account_id': self.offset_account.id,
                    'debit': 0.0 if inflow else amount,
                    'credit': amount if inflow else 0.0,
                }),
            ],
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

    def _payload(self, **extra):
        wizard = self._wizard(**extra)
        try:
            return self.health.build_payload(wizard, {'group_by': 'week'})
        finally:
            wizard.unlink()

    def test_executive_summary_structure(self):
        payload = self._payload(month='1', year=2026)
        summary = payload.get('executive_summary') or {}
        for key in ('title', 'message', 'main_risk', 'recommended_action', 'severity'):
            self.assertIn(key, summary)

    def test_liquidity_score_with_label_and_components(self):
        self._post_bank_movement('2026-01-11', 600.0, inflow=True)
        payload = self._payload(month='1', year=2026)
        score = payload['liquidity_score']
        self.assertIn('label', score)
        self.assertTrue(score.get('components'))
        for comp in score['components']:
            self.assertIn('weight', comp)
            self.assertIn('message', comp)

    def test_liquidity_risk_drivers(self):
        self._post_bank_movement('2026-01-09', 200.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        risk = payload['liquidity_risk']
        self.assertIn('negative_drivers', risk)
        self.assertIn('positive_drivers', risk)
        self.assertIn(risk['level'], ('green', 'yellow', 'red'))

    def test_cash_forecast_historical_and_projected(self):
        self._post_bank_movement('2026-01-05', 1000.0, inflow=True)
        self._post_bank_movement('2026-01-10', 400.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        forecast = payload['cash_forecast']
        self.assertIn('historical_series', forecast)
        self.assertIn('projected_series', forecast)
        self.assertIn('message', forecast)
        self.assertIn(forecast['trend'], ('improving', 'stable', 'deteriorating'))

    def test_cash_runway_coverage_days(self):
        # Seed enough opening balance so the final balance stays positive
        # regardless of pre-existing data in the database.
        self._post_bank_movement('2026-01-02', 1_000_000.0, inflow=True)
        self._post_bank_movement('2026-01-06', 3000.0, inflow=True)
        self._post_bank_movement('2026-01-08', 300.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        runway = payload['cash_runway']
        self.assertGreater(runway.get('daily_outflow_average', 0.0), 0.0)
        self.assertGreater(runway.get('coverage_days', 0.0), 0.0)

    def test_bank_concentration_absolute_percentages(self):
        self._post_bank_movement('2026-01-07', 800.0, inflow=True)
        payload = self._payload(month='1', year=2026)
        concentration = payload['bank_concentration']
        self.assertIn('balance_distribution', concentration)
        self.assertIn('recommendation', concentration)
        for row in concentration['balance_distribution']:
            self.assertGreaterEqual(row['percentage'], 0.0)
            self.assertLessEqual(row['percentage'], 100.0)

    def test_financial_ratios_group(self):
        payload = self._payload(month='1', year=2026)
        ratios = payload['financial_ratios']
        for key in ('current_ratio', 'quick_ratio', 'working_capital', 'cash_flow_coverage'):
            self.assertIn(key, ratios)
            self.assertIn('healthy_range', ratios[key])
        for key in ('current_ratio', 'quick_ratio', 'cash_flow_coverage'):
            self.assertIn('thresholds', ratios[key])
            self.assertIn('risk', ratios[key]['thresholds'])
            self.assertIn('warning', ratios[key]['thresholds'])

    def test_historical_comparison_structure(self):
        payload = self._payload(month='1', year=2026)
        hist = payload['historical_comparison']
        self.assertIn('available', hist)
        self.assertIn('comparisons', hist)

    def test_recommendations_generated(self):
        self._post_bank_movement('2026-01-04', 5000.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        self.assertTrue(isinstance(payload.get('recommendations'), list))

    def test_smart_alerts_generated(self):
        payload = self._payload(month='1', year=2026)
        alerts = payload.get('smart_alerts') or []
        self.assertTrue(isinstance(alerts, list))
        for alert in alerts:
            self.assertIn('severity', alert)
            self.assertIn('title', alert)

    def test_financial_timeline_ordered_with_severity(self):
        self._post_bank_movement('2026-01-03', 900.0, inflow=True)
        self._post_bank_movement('2026-01-04', 500.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        timeline = payload['financial_timeline']
        if len(timeline) >= 2:
            self.assertGreaterEqual(timeline[0]['date'], timeline[1]['date'])
        if timeline:
            self.assertIn('severity', timeline[0])

    def test_rpc_get_bank_financial_health_data(self):
        filters = {
            'company_id': self.company.id,
            'year': 2026,
            'month': '1',
            'journal_ids': self.bank_journal.ids,
            'compare_previous': False,
            'group_by': 'week',
        }
        data = self.dashboard.get_bank_financial_health_data(filters)
        self.assertIn('executive_summary', data)
        self.assertIn('financial_ratios', data)
        self.assertIn('recommendations', data)

    def test_empty_payload_unavailable_ratios(self):
        payload = self.health._empty_payload()
        self.assertFalse(payload['financial_ratios'])
        self.assertFalse(payload['historical_comparison']['available'])
        # El payload vacío también debe ofrecer una estructura de gauges segura
        # para que el frontend no truene sin datos.
        self.assertEqual(payload['indicator_gauges'], {'groups': [], 'gauges': []})

    def test_indicator_gauges_payload_structure(self):
        self._post_bank_movement('2026-01-03', 1500.0, inflow=True)
        self._post_bank_movement('2026-01-05', 400.0, inflow=False)
        payload = self._payload(month='1', year=2026)
        gauges = payload.get('indicator_gauges') or {}
        self.assertIn('groups', gauges)
        self.assertIn('gauges', gauges)
        groups_by_id = {g['id']: g for g in gauges['groups']}
        self.assertIn('liquidity', groups_by_id)
        self.assertIn('cycle', groups_by_id)
        self.assertIn('quality', groups_by_id)
        self.assertIn('projection', groups_by_id)
        projection_ids = {g['id'] for g in groups_by_id['projection']['gauges']}
        self.assertIn('days_to_zero', projection_ids)
        self.assertIn('balance_variation', projection_ids)
        self.assertIn('flow_variation', projection_ids)
        liquidity_ids = {g['id'] for g in groups_by_id['liquidity']['gauges']}
        self.assertIn('liquidity_score', liquidity_ids)
        self.assertIn('cash_runway', liquidity_ids)
        self.assertIn('current_ratio', liquidity_ids)
        self.assertIn('quick_ratio', liquidity_ids)
        self.assertIn('cash_ratio', liquidity_ids)
        self.assertIn('bank_concentration', liquidity_ids)
        cycle_ids = {g['id'] for g in groups_by_id['cycle']['gauges']}
        self.assertEqual(cycle_ids, {'dso', 'dpo', 'dio', 'ccc'})
        quality_ids = {g['id'] for g in groups_by_id['quality']['gauges']}
        self.assertEqual(quality_ids, {'reconciliation_pending', 'analytic_missing'})
        for g in gauges['gauges']:
            self.assertIn('status', g)
            self.assertIn('thresholds', g)
            self.assertIn('available', g)

    def test_cash_ratio_when_no_liabilities(self):
        # Sin pasivos circulantes el cash ratio debe quedar como 'unavailable'
        # para que el gauge salga gris en lugar de mostrar valores falsos.
        payload = self._payload(month='1', year=2026)
        cash_ratio = payload.get('cash_ratio') or {}
        if not cash_ratio.get('available'):
            self.assertEqual(cash_ratio.get('status'), 'unavailable')
            self.assertIsNone(cash_ratio.get('value'))


@tagged('post_install', '-at_install')
class TestFinancialHealthSnapshot(TransactionCase):
    """Pruebas del snapshot ligero de salud financiera (refactor performance)."""

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
        cls.health = cls.env['banks.financial.health']
        cls.wizard_model = cls.env['banks.weekly.balance.report']
        cls.offset_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'in', ('expense', 'expense_direct_cost', 'asset_current')),
        ], limit=1)
        assert cls.offset_account, 'Se requiere una cuenta de contrapartida.'

    def _post_bank_movement(self, move_date, amount, inflow=True):
        liquidity = self.bank_journal.default_account_id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': move_date,
            'journal_id': self.bank_journal.id,
            'line_ids': [
                (0, 0, {
                    'account_id': liquidity.id,
                    'debit': amount if inflow else 0.0,
                    'credit': 0.0 if inflow else amount,
                }),
                (0, 0, {
                    'account_id': self.offset_account.id,
                    'debit': 0.0 if inflow else amount,
                    'credit': amount if inflow else 0.0,
                }),
            ],
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

    def test_compute_month_snapshot_basic(self):
        baseline = self.health._compute_month_snapshot(
            self.company, self.bank_journal, 2026, 2, self.common,
        )
        self._post_bank_movement('2026-02-05', 1500.0, inflow=True)
        self._post_bank_movement('2026-02-12', 400.0, inflow=False)
        snapshot = self.health._compute_month_snapshot(
            self.company, self.bank_journal, 2026, 2, self.common,
        )
        self.assertIsNotNone(snapshot)
        self.assertAlmostEqual(
            snapshot['total_inflows'] - baseline['total_inflows'],
            1500.0, places=2,
        )
        self.assertAlmostEqual(
            snapshot['total_outflows'] - baseline['total_outflows'],
            400.0, places=2,
        )
        self.assertAlmostEqual(
            snapshot['net_flow'] - baseline['net_flow'],
            1100.0, places=2,
        )
        self.assertIn('coverage_days', snapshot)
        self.assertIn('final_balance', snapshot)

    def test_compute_month_snapshot_no_journal(self):
        empty_journals = self.env['account.journal'].browse()
        snapshot = self.health._compute_month_snapshot(
            self.company, empty_journals, 2026, 1, self.common,
        )
        self.assertIsNone(snapshot)

    def test_historical_comparison_query_count(self):
        for day in (3, 8, 14, 21, 28):
            self._post_bank_movement(f'2026-02-{day:02d}', 100.0 + day, inflow=True)
        wizard = self._wizard(month='2', year=2026)
        try:
            self.env.flush_all()
            self.env.invalidate_all()
            count_before = self.cr.sql_log_count
            self.health._compute_historical_comparison(
                wizard,
                {'group_by': 'week'},
                {'final_balance': 0.0, 'net_flow': 0.0,
                 'total_inflows': 0.0, 'total_outflows': 0.0,
                 'coverage_days': None,
                 'liquidity_score': 0,
                 'concentration_pct': 0.0},
                self.common,
            )
            self.env.flush_all()
            queries = self.cr.sql_log_count - count_before
            self.assertLess(
                queries, 30,
                'Historical comparison should issue fewer than 30 queries '
                'after switching to lightweight monthly snapshots (got %s).'
                % queries,
            )
        finally:
            wizard.unlink()
