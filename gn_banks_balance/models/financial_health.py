# -*- coding: utf-8 -*-
"""Strategic liquidity and financial health indicators for the weekly balance dashboard."""
from datetime import date, timedelta

from odoo import _, api, fields, models


_CURRENT_ASSET_TYPES = (
    'asset_cash',
    'asset_current',
    'asset_receivable',
    'asset_prepayments',
)
_QUICK_ASSET_TYPES = (
    'asset_cash',
    'asset_receivable',
    'asset_prepayments',
)
_CURRENT_LIABILITY_TYPES = (
    'liability_current',
    'liability_payable',
    'liability_credit_card',
)
_CASH_TYPES = ('asset_cash',)
_RECEIVABLE_TYPES = ('asset_receivable',)
_PAYABLE_TYPES = ('liability_payable',)
_PREPAYMENT_TYPES = ('asset_prepayments',)
_COGS_TYPES = ('expense_direct_cost',)

class BanksFinancialHealth(models.AbstractModel):
    _name = 'banks.financial.health'
    _description = 'Financial health indicators for bank weekly balance dashboard'

    def _score_labels(self):
        """Return localized score labels.

        Implemented as instance method (not module-level) so the translate
        machinery can pick up ``self.env`` and resolve the active language.
        """
        return {
            'excellent': _('Excelente'),
            'good': _('Bueno'),
            'warning': _('Atención'),
            'risk': _('Riesgo'),
        }

    def _round2(self, value):
        return round(float(value or 0.0), 2)

    def _pct_abs(self, part, total):
        if not total:
            return 0.0
        return self._round2(abs(part) / abs(total) * 100.0)

    def _empty_payload(self, dash=None):
        dash = dash or {}
        unavailable_ratio = {
            'available': False,
            'status': 'unavailable',
            'message': _('No hay datos disponibles.'),
        }
        return {
            'has_data': False,
            'error_message': dash.get('error_message') or _('No hay datos disponibles.'),
            'period': dash.get('period') or {},
            'currency': dash.get('currency') or {},
            'executive_summary': {},
            'liquidity_score': {},
            'liquidity_risk': {},
            'cash_forecast': {'available': False},
            'cash_runway': {'available': False},
            'liquidity_trend': {'available': False, 'series': []},
            'financial_ratios': {},
            'bank_concentration': {'available': False},
            'historical_comparison': {'available': False},
            'smart_alerts': [],
            'recommendations': [],
            'financial_timeline': [],
            'current_ratio': unavailable_ratio,
            'quick_ratio': unavailable_ratio,
            'working_capital': unavailable_ratio,
            'cash_flow_coverage': unavailable_ratio,
            'cash_ratio': {'available': False, 'status': 'unavailable'},
            'cash_cycle': {
                'dso': {'available': False, 'status': 'unavailable'},
                'dpo': {'available': False, 'status': 'unavailable'},
                'dio': {'available': False, 'status': 'unavailable'},
                'ccc': {'available': False, 'status': 'unavailable'},
            },
            'operational_quality': {
                'reconciliation_pending': {'available': False, 'status': 'unavailable'},
                'analytic_missing': {'available': False, 'status': 'unavailable'},
            },
            'indicator_gauges': {'groups': [], 'gauges': []},
        }

    @api.model
    def _period_day_count(self, period_start, period_end):
        if not period_start or not period_end:
            return 1
        return max((period_end - period_start).days + 1, 1)

    @api.model
    def _accounts_for_types(self, company, account_types):
        return self.env['account.account'].search([
            ('company_ids', 'in', company.id),
            ('account_type', 'in', list(account_types)),
        ])

    def _sum_account_type_balance(self, company, account_types, as_of_date, common):
        accounts = self._accounts_for_types(company, account_types)
        if not accounts:
            return None, 0.0
        sums = common._sums_through_date(company, accounts.ids, as_of_date)
        total = 0.0
        for account in accounts:
            bal = float(sums.get(account.id, 0.0))
            if account.internal_group == 'liability':
                total += abs(bal)
            else:
                total += bal
        return accounts, self._round2(total)

    def _ratio_status(self, value, healthy_min, warning_min, higher_is_better=True):
        if value is None:
            return 'unavailable'
        if higher_is_better:
            if value > healthy_min:
                return 'healthy'
            if value >= warning_min:
                return 'warning'
            return 'risk'
        if value < healthy_min:
            return 'healthy'
        if value <= warning_min:
            return 'warning'
        return 'risk'

    def _build_ratio_detail(
        self, key, title, value, available, status, message,
        formula, healthy_range, numerator=None, denominator=None,
        value_is_money=False, thresholds=None,
    ):
        status_labels = {
            'healthy': _('Saludable'),
            'warning': _('Atención'),
            'risk': _('Riesgo'),
            'positive': _('Positivo'),
            'negative': _('Negativo'),
            'neutral': _('Neutro'),
            'unavailable': _('No disponible'),
        }
        detail = {
            'id': key,
            'title': title,
            'value': value,
            'available': available,
            'status': status,
            'status_label': status_labels.get(status, status),
            'message': message,
            'formula': formula,
            'healthy_range': healthy_range,
            'numerator': numerator,
            'denominator': denominator,
            'value_is_money': value_is_money,
        }
        if thresholds:
            detail['thresholds'] = thresholds
        return detail

    def _compute_cash_runway(self, final_balance, total_outflows, period_days):
        daily_out = self._round2(total_outflows / period_days) if period_days else 0.0
        if daily_out <= 0:
            return {
                'available': True,
                'daily_outflow_average': daily_out,
                'coverage_days': None,
                'message': _('No hay salidas registradas para calcular días de cobertura.'),
                'empty_reason': 'no_outflows',
            }
        if final_balance <= 0:
            return {
                'available': True,
                'daily_outflow_average': daily_out,
                'coverage_days': 0.0,
                'message': _('Saldo final no positivo; cobertura de 0 días.'),
                'empty_reason': None,
            }
        coverage = self._round2(final_balance / daily_out)
        return {
            'available': True,
            'daily_outflow_average': daily_out,
            'coverage_days': coverage,
            'message': _(
                'Con el ritmo de salidas del período, el efectivo cubre %(days).2f días.'
            ) % {'days': coverage},
            'empty_reason': None,
        }

    def _compute_cash_forecast(self, final_balance, net_flow, period_days, period_end, weeks):
        daily_avg = self._round2(net_flow / period_days) if period_days else 0.0
        p7 = self._round2(final_balance + daily_avg * 7)
        p15 = self._round2(final_balance + daily_avg * 15)
        p30 = self._round2(final_balance + daily_avg * 30)
        risk_date = None
        if daily_avg < 0 and final_balance > 0:
            days_to_zero = int(final_balance / abs(daily_avg))
            risk_date = (period_end + timedelta(days=days_to_zero)).isoformat()
        elif final_balance <= 0:
            risk_date = period_end.isoformat() if period_end else None

        trend = 'stable'
        if daily_avg > 0:
            trend = 'improving'
        elif daily_avg < 0:
            trend = 'deteriorating'

        historical_series = [
            {
                'label': w.get('label') or w.get('key', ''),
                'value': self._round2(w.get('final_balance', 0.0)),
                'date': w.get('date_to') or w.get('date_from'),
            }
            for w in weeks
        ]
        projected_series = []
        for days, label in ((7, _('7 días')), (15, _('15 días')), (30, _('30 días'))):
            balance = self._round2(final_balance + daily_avg * days)
            projected_date = (period_end + timedelta(days=days)).isoformat() if period_end else None
            projected_series.append({
                'label': label,
                'value': balance,
                'date': projected_date,
                'days_ahead': days,
            })

        all_negative = all(v < 0 for v in (p7, p15, p30))
        if all_negative:
            message = _(
                'El saldo proyectado permanece negativo durante los próximos 30 días.'
            )
        elif trend == 'improving':
            message = _('La proyección muestra recuperación de caja al ritmo actual.')
        elif trend == 'deteriorating':
            message = _('La proyección indica presión de caja en las próximas semanas.')
        else:
            message = _('La proyección se mantiene estable al ritmo actual del período.')

        return {
            'available': bool(weeks or final_balance or net_flow),
            'daily_average_net_flow': daily_avg,
            'projected_7_days': p7,
            'projected_15_days': p15,
            'projected_30_days': p30,
            'risk_date': risk_date,
            'trend': trend,
            'message': message,
            'historical_series': historical_series,
            'projected_series': projected_series,
            'all_negative_projection': all_negative,
        }

    def _distribution_rows(self, journals, values_map, pct_map):
        rows = []
        for journal in journals:
            aid = journal.default_account_id.id
            rows.append({
                'bank_id': journal.bank_id.id if journal.bank_id else False,
                'bank_name': journal.name or '',
                'journal_id': journal.id,
                'amount': self._round2(values_map.get(aid, 0.0)),
                'percentage': pct_map.get(aid, 0.0),
            })
        return sorted(rows, key=lambda r: r['percentage'], reverse=True)

    def _compute_bank_concentration(self, journals, end_bal, agg_debit, agg_credit,
                                    company=None):
        """Concentración bancaria normalizada en moneda de la company.

        ``end_bal``/``agg_debit``/``agg_credit`` ya vienen en moneda de la
        company (se calculan sobre ``account.move.line.balance/debit/credit``).
        Se aplica ``company.currency_id.round`` para evitar drift en sumatorios
        y se expone ``mixed_currency``/``foreign_currency_journals`` para que
        el frontend pueda advertir al usuario cuando la composición incluye
        diarios con moneda distinta.
        """
        currency = (company.currency_id if company else None)
        round_amt = currency.round if currency else (lambda v: v)

        abs_balances = {
            j.default_account_id.id: round_amt(abs(end_bal.get(j.default_account_id.id, 0.0)))
            for j in journals
        }
        abs_inflows = {
            j.default_account_id.id: round_amt(abs(agg_debit.get(j.default_account_id.id, 0.0)))
            for j in journals
        }
        abs_outflows = {
            j.default_account_id.id: round_amt(abs(agg_credit.get(j.default_account_id.id, 0.0)))
            for j in journals
        }
        abs_movements = {
            aid: round_amt(abs_inflows.get(aid, 0.0) + abs_outflows.get(aid, 0.0))
            for aid in abs_balances
        }

        total_balance = round_amt(sum(abs_balances.values()))
        total_in = round_amt(sum(abs_inflows.values()))
        total_out = round_amt(sum(abs_outflows.values()))
        total_mov = round_amt(sum(abs_movements.values()))

        bal_pct = {aid: self._pct_abs(v, total_balance) for aid, v in abs_balances.items()}
        in_pct = {aid: self._pct_abs(v, total_in) for aid, v in abs_inflows.items()}
        out_pct = {aid: self._pct_abs(v, total_out) for aid, v in abs_outflows.items()}
        mov_pct = {aid: self._pct_abs(v, total_mov) for aid, v in abs_movements.items()}

        balance_distribution = self._distribution_rows(journals, end_bal, bal_pct)
        inflow_distribution = self._distribution_rows(journals, agg_debit, in_pct)
        outflow_distribution = self._distribution_rows(journals, agg_credit, out_pct)
        movement_distribution = self._distribution_rows(journals, abs_movements, mov_pct)

        mixed_currency = False
        foreign_currency_journals = []
        if currency:
            for j in journals:
                if j.currency_id and j.currency_id != currency:
                    mixed_currency = True
                    foreign_currency_journals.append({
                        'journal_id': j.id,
                        'name': j.name or '',
                        'currency_id': j.currency_id.id,
                        'currency_name': j.currency_id.name,
                    })

        dominant = balance_distribution[0] if balance_distribution else {}
        bal_dom_pct = dominant.get('percentage', 0.0)
        if bal_dom_pct > 70:
            risk_level = 'high'
            recommendation = _('Considere redistribuir liquidez entre bancos.')
        elif bal_dom_pct >= 50:
            risk_level = 'medium'
            recommendation = _('Evalúe diversificar saldos entre instituciones bancarias.')
        else:
            risk_level = 'low'
            recommendation = _('La distribución bancaria está diversificada.')

        journal_account = {j.id: j.default_account_id.id for j in journals}
        banks_legacy = []
        for row in balance_distribution:
            aid = journal_account.get(row['journal_id'])
            banks_legacy.append({
                'bank_id': row['bank_id'],
                'bank_name': row['bank_name'],
                'journal_id': row['journal_id'],
                'ending_balance': row['amount'],
                'balance_percentage': row['percentage'],
                'inflow_percentage': in_pct.get(aid, 0.0),
                'outflow_percentage': out_pct.get(aid, 0.0),
                'movement_percentage': mov_pct.get(aid, 0.0),
            })

        return {
            'available': bool(journals),
            'dominant_bank': {
                'bank_id': dominant.get('bank_id'),
                'bank_name': dominant.get('bank_name', ''),
                'journal_id': dominant.get('journal_id'),
                'balance_percentage': bal_dom_pct,
                'movement_percentage': (
                    movement_distribution[0]['percentage'] if movement_distribution else 0.0
                ),
            },
            'risk_level': risk_level,
            'recommendation': recommendation,
            'balance_distribution': balance_distribution,
            'movement_distribution': movement_distribution,
            'inflow_distribution': inflow_distribution,
            'outflow_distribution': outflow_distribution,
            'banks': banks_legacy,
            'currency_id': currency.id if currency else False,
            'mixed_currency': mixed_currency,
            'foreign_currency_journals': foreign_currency_journals,
        }

    def _compute_liquidity_trend(self, weeks, kpis):
        if not weeks:
            return {
                'available': False,
                'status': 'stable',
                'percentage_change': 0.0,
                'message': _('No hay movimientos suficientes para calcular tendencia.'),
                'series': [],
                'empty_reason': 'no_weeks',
            }
        series = [
            {
                'label': w.get('label') or w.get('key', ''),
                'value': self._round2(w.get('final_balance', 0.0)),
            }
            for w in weeks[-3:]
        ]
        if len(weeks) >= 2:
            last_net = weeks[-1].get('net_flow', 0.0)
            prev_net = weeks[-2].get('net_flow', 0.0)
            last_bal = weeks[-1].get('final_balance', 0.0)
            prev_bal = weeks[-2].get('final_balance', 0.0)
            pct = self._round2(
                ((last_bal - prev_bal) / abs(prev_bal) * 100.0) if prev_bal else 0.0
            )
        else:
            last_net = weeks[-1].get('net_flow', 0.0)
            prev_net = 0.0
            pct = kpis.get('variation_period') or 0.0

        if last_net > prev_net and pct >= 0:
            status = 'improving'
            message = _('La liquidez muestra tendencia positiva en las últimas semanas.')
        elif last_net < prev_net and pct < 0:
            status = 'deteriorating'
            message = _('La liquidez muestra presión en las últimas semanas.')
        else:
            status = 'stable'
            message = _('La liquidez se mantiene estable en el período reciente.')

        return {
            'available': True,
            'status': status,
            'percentage_change': pct,
            'message': message,
            'series': series,
            'empty_reason': None,
        }

    def _compute_liquidity_risk(
        self, final_balance, min_balance, net_flow, coverage_days,
        current_ratio, quick_ratio, working_capital, bank_concentration,
    ):
        negative_drivers = []
        positive_drivers = []
        score = 100.0
        level = 'green'

        if final_balance < 0:
            negative_drivers.append(_('Saldo final negativo'))
            score -= 40
            level = 'red'
        elif min_balance < 0:
            negative_drivers.append(_('Saldo mínimo del período en negativo'))
            score -= 25
            level = 'yellow' if level != 'red' else level
        else:
            positive_drivers.append(_('Saldo final positivo'))

        cov = coverage_days if coverage_days is not None else 999.0
        if coverage_days is not None:
            if cov < 15:
                negative_drivers.append(_('Cobertura insuficiente (< 15 días)'))
                score -= 30
                level = 'red'
            elif cov < 30:
                negative_drivers.append(_('Cobertura moderada (15-30 días)'))
                score -= 15
                if level == 'green':
                    level = 'yellow'
            else:
                positive_drivers.append(_('Cobertura de efectivo amplia'))

        if net_flow < 0:
            negative_drivers.append(_('Flujo neto negativo en el período'))
            score -= 15
            if level == 'green':
                level = 'yellow'
        elif net_flow > 0:
            positive_drivers.append(_('Flujo neto positivo'))

        if bank_concentration.get('risk_level') == 'high':
            negative_drivers.append(_('Alta concentración bancaria'))
            score -= 10
            if level == 'green':
                level = 'yellow'
        elif bank_concentration.get('risk_level') == 'low':
            positive_drivers.append(_('Distribución bancaria diversificada'))

        if current_ratio.get('available'):
            if current_ratio.get('status') == 'risk':
                negative_drivers.append(_('Liquidez corriente en zona de riesgo'))
                score -= 10
                if level == 'green':
                    level = 'yellow'
            elif current_ratio.get('status') == 'healthy':
                positive_drivers.append(_('Liquidez corriente saludable'))

        if quick_ratio.get('available') and quick_ratio.get('status') == 'healthy':
            positive_drivers.append(_('Prueba ácida saludable'))

        if working_capital.get('available') and working_capital.get('status') == 'positive':
            positive_drivers.append(_('Capital de trabajo positivo'))
        elif working_capital.get('available') and working_capital.get('status') == 'negative':
            negative_drivers.append(_('Capital de trabajo negativo'))

        score = max(0, min(100, int(round(score))))
        labels = {'green': _('Saludable'), 'yellow': _('Atención'), 'red': _('Riesgo')}
        if level == 'green':
            message = _('Liquidez sólida con señales favorables predominantes.')
        elif level == 'red':
            message = _('Se detectan señales críticas de liquidez que requieren acción.')
        else:
            message = _('Liquidez aceptable pero con factores que requieren seguimiento.')

        return {
            'level': level,
            'label': labels[level],
            'score': score,
            'message': message,
            'negative_drivers': negative_drivers,
            'positive_drivers': positive_drivers,
            'drivers': negative_drivers,
        }

    def _compute_liquidity_score(
        self, kpis, cash_runway, bank_concentration, liquidity_trend,
        current_ratio, quick_ratio, cash_flow_coverage,
    ):
        components = []
        weights = {
            'net_flow': 0.15,
            'final_balance': 0.10,
            'coverage': 0.15,
            'trend': 0.10,
            'concentration': 0.10,
            'current_ratio': 0.15,
            'quick_ratio': 0.10,
            'cash_flow_coverage': 0.15,
        }

        def _add(name, raw_score, weight, message):
            components.append({
                'name': name,
                'score': int(max(0, min(100, round(raw_score)))),
                'weight': weight,
                'message': message,
            })

        net = kpis.get('net_flow') or 0.0
        _add(
            _('Flujo neto'),
            80 if net > 0 else (40 if net == 0 else 10),
            weights['net_flow'],
            _('Flujo neto positivo.') if net > 0 else _('Flujo neto negativo afecta el score.'),
        )

        final = kpis.get('final_balance') or 0.0
        _add(
            _('Saldo final'),
            90 if final > 0 else 20,
            weights['final_balance'],
            _('Saldo positivo al cierre.') if final > 0 else _('Saldo bajo presión.'),
        )

        cov = cash_runway.get('coverage_days')
        if cov is None:
            cov_score, cov_msg = 70, _('Sin salidas de referencia en el período.')
        elif cov >= 30:
            cov_score, cov_msg = 95, _('Cobertura amplia (> 30 días).')
        elif cov >= 15:
            cov_score, cov_msg = 60, _('Cobertura moderada (15-30 días).')
        else:
            cov_score, cov_msg = 25, _('Cobertura limitada (< 15 días).')
        _add(_('Días de cobertura'), cov_score, weights['coverage'], cov_msg)

        trend = liquidity_trend.get('status', 'stable')
        trend_scores = {'improving': 90, 'stable': 65, 'deteriorating': 25}
        _add(
            _('Tendencia'),
            trend_scores.get(trend, 65),
            weights['trend'],
            liquidity_trend.get('message', ''),
        )

        conc_risk = bank_concentration.get('risk_level', 'low')
        conc_scores = {'low': 85, 'medium': 55, 'high': 25}
        _add(
            _('Concentración bancaria'),
            conc_scores.get(conc_risk, 55),
            weights['concentration'],
            _('Riesgo %(level)s de concentración.') % {'level': conc_risk},
        )

        for ratio, weight, label in (
            (current_ratio, weights['current_ratio'], _('Liquidez corriente')),
            (quick_ratio, weights['quick_ratio'], _('Prueba ácida')),
            (cash_flow_coverage, weights['cash_flow_coverage'], _('Cobertura de flujo')),
        ):
            if ratio.get('available'):
                status = ratio.get('status', 'warning')
                ratio_scores = {'healthy': 90, 'warning': 55, 'risk': 20, 'positive': 90, 'negative': 20}
                _add(label, ratio_scores.get(status, 55), weight, ratio.get('message', ''))
            else:
                _add(label, 50, weight, _('No disponible — verifique cuentas contables.'))

        total = sum(c['score'] * c['weight'] for c in components)
        score = int(round(total))
        if score >= 80:
            level = 'excellent'
        elif score >= 65:
            level = 'good'
        elif score >= 45:
            level = 'warning'
        else:
            level = 'risk'

        level_messages = {
            'excellent': _('Excelente salud de liquidez.'),
            'good': _('Buena posición de liquidez con áreas de mejora.'),
            'warning': _('Liquidez en zona de atención.'),
            'risk': _('Riesgo elevado de liquidez.'),
        }
        return {
            'score': score,
            'level': level,
            'label': self._score_labels()[level],
            'message': level_messages[level],
            'components': components,
        }

    def _compute_month_snapshot(self, company, journals, year, month, common):
        """Lightweight monthly snapshot for historical comparison (2 queries).

        Avoids building the full dashboard payload: only computes the metrics
        needed by the comparison block (final_balance, totals, net_flow,
        coverage_days). Returns None if there are no eligible journals.
        """
        import calendar as cal_mod
        journals = journals.filtered(lambda j: j.default_account_id)
        if not journals:
            return None
        account_ids = journals.mapped('default_account_id').ids
        last_day = cal_mod.monthrange(year, month)[1]
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
        period_days = self._period_day_count(period_start, period_end)

        end_map = common._sums_through_date(company, account_ids, period_end)
        final_balance = sum(end_map.get(aid, 0.0) for aid in account_ids)

        aml = self.env['account.move.line']
        period_agg = aml._read_group(
            domain=common._ml_domain_base(company, account_ids)
                + [('date', '>=', period_start), ('date', '<=', period_end)],
            groupby=[],
            aggregates=['debit:sum', 'credit:sum'],
        )
        if period_agg:
            total_in = float(period_agg[0][0] or 0.0)
            total_out = float(period_agg[0][1] or 0.0)
        else:
            total_in = 0.0
            total_out = 0.0

        runway = self._compute_cash_runway(
            final_balance, total_out, period_days,
        )
        return {
            'final_balance': self._round2(final_balance),
            'net_flow': self._round2(total_in - total_out),
            'total_inflows': self._round2(total_in),
            'total_outflows': self._round2(total_out),
            'coverage_days': runway.get('coverage_days'),
        }

    def _compute_historical_comparison(self, wizard, options, current_metrics, common):
        company = wizard.company_id
        journal_ids = wizard.journal_ids.ids
        month = int(wizard.month)
        year = int(wizard.year)
        journals = common.search_balance_journals(company.id, journal_ids)

        # The previous-period, trailing-3-month and same-month-last-year blocks
        # request overlapping months; memoize so each month is computed once.
        snapshot_cache = {}

        def _snapshot(snap_year, snap_month):
            cache_key = (snap_year, snap_month)
            if cache_key not in snapshot_cache:
                snapshot_cache[cache_key] = self._compute_month_snapshot(
                    company, journals, snap_year, snap_month, common,
                )
            return snapshot_cache[cache_key]

        if month == 1:
            previous_period = _snapshot(year - 1, 12)
        else:
            previous_period = _snapshot(year, month - 1)

        three_month_snaps = []
        cursor_month, cursor_year = month, year
        for _i in range(3):
            snap = _snapshot(cursor_year, cursor_month)
            if snap:
                three_month_snaps.append(snap)
            cursor_month -= 1
            if cursor_month < 1:
                cursor_month = 12
                cursor_year -= 1

        three_month_average = None
        if three_month_snaps:
            keys = ('final_balance', 'net_flow', 'total_inflows', 'total_outflows', 'coverage_days')
            three_month_average = {}
            for key in keys:
                vals = [s[key] for s in three_month_snaps if s.get(key) is not None]
                three_month_average[key] = self._round2(sum(vals) / len(vals)) if vals else None

        same_month_last_year = _snapshot(year - 1, month)

        def _delta(current, base, key):
            cv = current.get(key)
            bv = (base or {}).get(key)
            if cv is None or bv is None:
                return None
            diff = self._round2(cv - bv)
            pct = self._round2((diff / abs(bv) * 100.0) if bv else 0.0)
            return {'value': cv, 'base': bv, 'delta': diff, 'delta_pct': pct}

        insights = []
        if previous_period:
            d = _delta(current_metrics, previous_period, 'final_balance')
            if d and d['delta_pct'] is not None:
                insights.append({
                    'metric': 'final_balance',
                    'message': _(
                        'Saldo final %(dir)s %(pct).2f%% vs período anterior.'
                    ) % {
                        'dir': _('subió') if d['delta'] >= 0 else _('bajó'),
                        'pct': abs(d['delta_pct']),
                    },
                })

        available = bool(previous_period or three_month_average or same_month_last_year)
        return {
            'available': available,
            'previous_period': previous_period,
            'three_month_average': three_month_average,
            'same_month_last_year': same_month_last_year,
            'current': current_metrics,
            'insights': insights,
            'comparisons': {
                'final_balance': _delta(current_metrics, previous_period, 'final_balance'),
                'net_flow': _delta(current_metrics, previous_period, 'net_flow'),
                'total_inflows': _delta(current_metrics, previous_period, 'total_inflows'),
                'total_outflows': _delta(current_metrics, previous_period, 'total_outflows'),
                'coverage_days': _delta(current_metrics, previous_period, 'coverage_days'),
            },
        }

    def _compute_executive_summary(
        self, liquidity_score, liquidity_risk, cash_forecast,
        bank_concentration, cash_runway,
    ):
        level = liquidity_score.get('level', 'warning')
        severity_map = {
            'excellent': 'success',
            'good': 'success',
            'warning': 'warning',
            'risk': 'danger',
        }
        severity = severity_map.get(level, 'info')

        if level in ('risk', 'warning'):
            title = _('Liquidez en zona de atención')
        elif level == 'excellent':
            title = _('Liquidez sólida')
        else:
            title = _('Liquidez en niveles aceptables')

        main_risk = (
            liquidity_risk.get('negative_drivers') or ['']
        )[0] or _('Sin riesgos críticos detectados')

        if cash_forecast.get('all_negative_projection'):
            recommended = _(
                'Revise salidas proyectadas, priorice cobros y evalúe redistribución bancaria.'
            )
            message = cash_forecast.get('message', '')
        elif liquidity_risk.get('level') == 'red':
            recommended = _('Prepare plan de liquidez inmediata y revise pagos críticos.')
            message = liquidity_risk.get('message', '')
        elif bank_concentration.get('risk_level') == 'high':
            recommended = bank_concentration.get('recommendation', '')
            message = _('Alta dependencia de un solo banco detectada.')
        elif cash_runway.get('coverage_days') is not None and cash_runway['coverage_days'] < 15:
            recommended = _('Acelere cobros y reduzca compromisos de corto plazo.')
            message = cash_runway.get('message', '')
        else:
            recommended = _('Mantenga monitoreo semanal de flujo y saldos bancarios.')
            message = liquidity_score.get('message', '')

        return {
            'title': title,
            'message': message,
            'main_risk': main_risk,
            'recommended_action': recommended,
            'severity': severity,
            'score': liquidity_score.get('score'),
            'risk_level': liquidity_risk.get('level'),
        }

    def _compute_recommendations(
        self, liquidity_score, bank_concentration, kpis,
        cash_runway, cash_forecast, current_ratio,
    ):
        recs = []
        score = liquidity_score.get('score', 100)

        if score < 70:
            recs.append({
                'severity': 'warning',
                'title': _('Reducir riesgo de liquidez'),
                'message': _('Revise salidas proyectadas y priorice cobros.'),
                'action_type': 'review_collections',
                'action_context': {},
            })

        if bank_concentration.get('risk_level') == 'high':
            recs.append({
                'severity': 'warning',
                'title': _('Diversificar bancos'),
                'message': bank_concentration.get('recommendation', ''),
                'action_type': 'redistribute_banks',
                'action_context': {},
            })

        if (kpis.get('net_flow') or 0.0) < 0:
            recs.append({
                'severity': 'danger',
                'title': _('Analizar egresos'),
                'message': _('Analice egresos extraordinarios del período.'),
                'action_type': 'review_payments',
                'action_context': {},
            })

        cov = cash_runway.get('coverage_days')
        if cov is not None and cov < 15:
            recs.append({
                'severity': 'danger',
                'title': _('Plan de liquidez inmediata'),
                'message': _('Los días de cobertura están por debajo de 15.'),
                'action_type': 'review_payments',
                'action_context': {},
            })

        if (
            current_ratio.get('available')
            and current_ratio.get('status') == 'healthy'
            and (kpis.get('final_balance') or 0.0) < 0
        ):
            recs.append({
                'severity': 'warning',
                'title': _('Revisar timing de caja'),
                'message': _('Ratios saludables pero caja bancaria bajo presión.'),
                'action_type': 'review_collections',
                'action_context': {},
            })

        if cash_forecast.get('all_negative_projection'):
            recs.append({
                'severity': 'danger',
                'title': _('Proyección negativa sostenida'),
                'message': _('El saldo proyectado no se recupera en 30 días.'),
                'action_type': 'review_payments',
                'action_context': {},
            })

        if not current_ratio.get('available'):
            recs.append({
                'severity': 'info',
                'title': _('Configurar cuentas contables'),
                'message': _(
                    'Clasifique cuentas circulantes para habilitar ratios financieros.'
                ),
                'action_type': 'configure_accounts',
                'action_context': {},
            })

        return recs

    def _compute_smart_alerts(
        self, kpis, cash_forecast, bank_concentration,
        cash_runway, liquidity_trend, current_ratio, quick_ratio,
    ):
        alerts = []
        if cash_forecast.get('all_negative_projection'):
            alerts.append({
                'severity': 'danger',
                'title': _('Saldo negativo proyectado'),
                'message': cash_forecast.get('message', ''),
                'metric': 'cash_forecast',
                'value': cash_forecast.get('projected_30_days'),
            })
        if (kpis.get('net_flow') or 0.0) < 0:
            alerts.append({
                'severity': 'warning',
                'title': _('Flujo neto negativo'),
                'message': _('Las salidas superaron a los ingresos en el período.'),
                'metric': 'net_flow',
                'value': kpis.get('net_flow'),
            })
        if bank_concentration.get('risk_level') == 'high':
            dom = bank_concentration.get('dominant_bank') or {}
            alerts.append({
                'severity': 'warning',
                'title': _('Concentración bancaria alta'),
                'message': _(
                    '%(bank)s concentra %(pct).2f%% del saldo.'
                ) % {'bank': dom.get('bank_name', ''), 'pct': dom.get('balance_percentage', 0.0)},
                'metric': 'bank_concentration',
                'value': dom.get('balance_percentage'),
            })
        if liquidity_trend.get('status') == 'deteriorating':
            alerts.append({
                'severity': 'warning',
                'title': _('Deterioro de liquidez'),
                'message': liquidity_trend.get('message', ''),
                'metric': 'liquidity_trend',
                'value': liquidity_trend.get('percentage_change'),
            })
        cov = cash_runway.get('coverage_days')
        if cov is not None and cov < 15:
            alerts.append({
                'severity': 'danger',
                'title': _('Cobertura insuficiente'),
                'message': cash_runway.get('message', ''),
                'metric': 'coverage_days',
                'value': cov,
            })
        if not current_ratio.get('available'):
            alerts.append({
                'severity': 'info',
                'title': _('Ratio no disponible'),
                'message': current_ratio.get('message', ''),
                'metric': 'current_ratio',
                'value': None,
            })
        if quick_ratio.get('available') and quick_ratio.get('status') == 'risk':
            alerts.append({
                'severity': 'warning',
                'title': _('Prueba ácida en riesgo'),
                'message': quick_ratio.get('message', ''),
                'metric': 'quick_ratio',
                'value': quick_ratio.get('value'),
            })
        return alerts

    def _compute_financial_timeline(
        self, weeks, kpis, bank_concentration, cash_forecast,
        current_ratio, liquidity_trend,
    ):
        events = []
        if not weeks:
            return events

        max_in_week = max(weeks, key=lambda w: w.get('inflows', 0.0))
        if max_in_week.get('inflows', 0.0) > 0:
            events.append({
                'date': max_in_week.get('date_to') or max_in_week.get('date_from'),
                'type': 'inflow',
                'severity': 'success',
                'icon': 'fa-arrow-down',
                'title': _('Mayor ingreso semanal'),
                'description': _('%(label)s registró el mayor ingreso del período.') % {
                    'label': max_in_week.get('label', ''),
                },
                'amount': self._round2(max_in_week.get('inflows', 0.0)),
                'bank_name': max_in_week.get('main_bank') or '',
            })

        max_out_week = max(weeks, key=lambda w: w.get('outflows', 0.0))
        if max_out_week.get('outflows', 0.0) > 0:
            events.append({
                'date': max_out_week.get('date_to') or max_out_week.get('date_from'),
                'type': 'outflow',
                'severity': 'warning',
                'icon': 'fa-arrow-up',
                'title': _('Mayor salida semanal'),
                'description': _('%(label)s concentró la mayor salida del período.') % {
                    'label': max_out_week.get('label', ''),
                },
                'amount': self._round2(max_out_week.get('outflows', 0.0)),
                'bank_name': max_out_week.get('main_bank') or '',
            })

        critical = kpis.get('critical_week') or {}
        if critical.get('week_no') and critical['week_no'] <= len(weeks):
            w = weeks[critical['week_no'] - 1]
            events.append({
                'date': w.get('date_to'),
                'type': 'info',
                'severity': 'warning',
                'icon': 'fa-exclamation-triangle',
                'title': _('Semana crítica'),
                'description': _('Menor saldo final en %(label)s.') % {
                    'label': critical.get('label', ''),
                },
                'amount': self._round2(critical.get('value', 0.0)),
                'bank_name': '',
            })

        dominant = bank_concentration.get('dominant_bank') or {}
        if dominant.get('bank_name') and bank_concentration.get('risk_level') != 'low':
            events.append({
                'date': weeks[-1].get('date_to') if weeks else False,
                'type': 'concentration',
                'severity': 'warning' if bank_concentration.get('risk_level') == 'medium' else 'danger',
                'icon': 'fa-university',
                'title': _('Concentración bancaria alta'),
                'description': _('%(bank)s concentra %(pct).2f%% del saldo.') % {
                    'bank': dominant.get('bank_name'),
                    'pct': dominant.get('balance_percentage', 0.0),
                },
                'amount': None,
                'bank_name': dominant.get('bank_name', ''),
            })

        if cash_forecast.get('risk_date'):
            events.append({
                'date': cash_forecast.get('risk_date'),
                'type': 'forecast',
                'severity': 'danger',
                'icon': 'fa-line-chart',
                'title': _('Fecha de riesgo proyectado'),
                'description': _('Al ritmo actual, el saldo podría agotarse en esta fecha.'),
                'amount': cash_forecast.get('projected_30_days'),
                'bank_name': '',
            })

        if current_ratio.get('available') and current_ratio.get('status') in ('risk', 'warning'):
            events.append({
                'date': weeks[-1].get('date_to') if weeks else False,
                'type': 'ratio',
                'severity': 'warning' if current_ratio['status'] == 'warning' else 'danger',
                'icon': 'fa-balance-scale',
                'title': _('Liquidez corriente en atención'),
                'description': current_ratio.get('message', ''),
                'amount': current_ratio.get('value'),
                'bank_name': '',
            })

        if liquidity_trend.get('status') == 'deteriorating':
            events.append({
                'date': weeks[-1].get('date_to') if weeks else False,
                'type': 'risk',
                'severity': 'danger',
                'icon': 'fa-arrow-down',
                'title': _('Tendencia de liquidez negativa'),
                'description': liquidity_trend.get('message', ''),
                'amount': liquidity_trend.get('percentage_change'),
                'bank_name': '',
            })

        max_var_week = max(
            weeks[1:],
            key=lambda w: abs(w.get('difference_previous_week', 0.0)),
            default=None,
        ) if len(weeks) > 1 else None
        if max_var_week and abs(max_var_week.get('difference_previous_week', 0.0)) > 0:
            events.append({
                'date': max_var_week.get('date_to'),
                'type': 'info',
                'severity': 'info',
                'icon': 'fa-exchange',
                'title': _('Mayor variación semanal'),
                'description': _('Cambio de saldo vs semana anterior.'),
                'amount': self._round2(max_var_week.get('difference_previous_week', 0.0)),
                'bank_name': max_var_week.get('main_bank') or '',
            })

        events.sort(key=lambda e: e.get('date') or '', reverse=True)
        return events

    def _build_gauge(self, key, title, value, unit, available, status,
                     thresholds, healthy_range, message='',
                     formula='', extra=None):
        """Build a normalized gauge entry for the indicators panel.

        ``thresholds`` semantics depend on ``unit``:
        - higher_is_better: ``[risk, warning]`` (e.g. liquidity score 50/70)
        - lower_is_better:  ``[warning, risk]`` (e.g. concentración 60/80)
        - days_*: igual que arriba según corresponda
        """
        status_labels = {
            'healthy': _('Saludable'),
            'warning': _('Atención'),
            'risk': _('Riesgo'),
            'unavailable': _('No disponible'),
        }
        gauge = {
            'id': key,
            'title': title,
            'value': value,
            'unit': unit,
            'available': bool(available),
            'status': status,
            'status_label': status_labels.get(status, status),
            'thresholds': thresholds or {},
            'healthy_range': healthy_range,
            'message': message,
            'formula': formula,
        }
        if extra:
            gauge['extra'] = extra
        return gauge

    def _compute_cash_ratio(self, company, period_end, current_liabilities,
                            cl_accounts, common):
        """Cash Ratio = (Caja + bancos) / Pasivos corrientes.

        Más conservador que current_ratio y quick_ratio: sólo activos
        100% líquidos.
        """
        thresholds = {'risk': 0.20, 'warning': 0.40}
        unavailable = self._build_gauge(
            'cash_ratio', _('Cash ratio'), None, 'ratio', False, 'unavailable',
            thresholds, _('> 0.40'),
            message=_('No se encontraron cuentas de caja o pasivos corrientes.'),
            formula=_('(Caja + bancos) / Pasivos corrientes'),
        )
        if not cl_accounts or current_liabilities <= 0:
            return unavailable
        cash_accounts, cash_balance = self._sum_account_type_balance(
            company, _CASH_TYPES, period_end, common,
        )
        if not cash_accounts:
            return unavailable
        value = self._round2(cash_balance / current_liabilities)
        status = self._ratio_status(value, 0.40, 0.20)
        return self._build_gauge(
            'cash_ratio', _('Cash ratio'), value, 'ratio', True, status,
            thresholds, _('> 0.40'),
            message=_(
                'La caja cubre %(pct).0f%% de las obligaciones corrientes.'
            ) % {'pct': value * 100.0},
            formula=_('(Caja + bancos) / Pasivos corrientes'),
            extra={'numerator': cash_balance, 'denominator': current_liabilities},
        )

    def _sum_period_movement(self, company, account_types, d_from, d_to, common):
        """Return (debit_total, credit_total) for accounts of the given types."""
        accounts = self._accounts_for_types(company, account_types)
        if not accounts:
            return None, 0.0, 0.0
        deb_map, cre_map = common._period_debit_credit(
            company, accounts.ids, d_from, d_to,
        )
        return accounts, sum(deb_map.values()), sum(cre_map.values())

    def _compute_cash_cycle(self, company, period_start, period_end,
                            current_assets, current_liabilities,
                            ca_accounts, cl_accounts, common):
        """Cash Conversion Cycle = DSO + DIO - DPO.

        - DSO: Days Sales Outstanding (días promedio de cobro).
        - DPO: Days Payables Outstanding (días promedio de pago).
        - DIO: Days Inventory Outstanding (días en inventario).
        """
        period_days = self._period_day_count(period_start, period_end)
        # DSO/DPO/DIO escalan saldos por días del período; con rangos muy
        # cortos el resultado se distorsiona, así que lo señalizamos al frontend.
        short_period = period_days < 20

        ar_accounts, ar_balance = self._sum_account_type_balance(
            company, _RECEIVABLE_TYPES, period_end, common,
        )
        ap_accounts, ap_balance = self._sum_account_type_balance(
            company, _PAYABLE_TYPES, period_end, common,
        )
        ar_sales = 0.0
        if ar_accounts:
            _accs, ar_debit, _ar_credit = self._sum_period_movement(
                company, _RECEIVABLE_TYPES, period_start, period_end, common,
            )
            ar_sales = ar_debit
        ap_purchases = 0.0
        if ap_accounts:
            _accs, _ap_debit, ap_credit = self._sum_period_movement(
                company, _PAYABLE_TYPES, period_start, period_end, common,
            )
            ap_purchases = ap_credit
        cogs_total = 0.0
        cogs_accounts = None
        if _COGS_TYPES:
            cogs_accounts, cogs_debit, _cogs_credit = self._sum_period_movement(
                company, _COGS_TYPES, period_start, period_end, common,
            )
            cogs_total = cogs_debit

        cash_balance = 0.0
        if ca_accounts:
            _ca_only, cash_balance = self._sum_account_type_balance(
                company, _CASH_TYPES, period_end, common,
            )
        prepay_balance = 0.0
        _pp, prepay_balance = self._sum_account_type_balance(
            company, _PREPAYMENT_TYPES, period_end, common,
        ) or (None, 0.0)
        if _pp is None:
            prepay_balance = 0.0
        inventory_proxy = max(
            0.0,
            (current_assets or 0.0) - (cash_balance or 0.0)
            - (ar_balance or 0.0) - (prepay_balance or 0.0),
        )

        dso_thresholds = {'warning': 45.0, 'risk': 60.0}
        dpo_thresholds = {'warning': 30.0, 'risk': 60.0}
        dio_thresholds = {'warning': 60.0, 'risk': 90.0}
        ccc_thresholds = {'warning': 45.0, 'risk': 90.0}

        def status_lower(value, healthy, warning):
            if value is None:
                return 'unavailable'
            if value <= healthy:
                return 'healthy'
            if value <= warning:
                return 'warning'
            return 'risk'

        if ar_accounts and ar_sales > 0:
            dso_value = self._round2(ar_balance / ar_sales * period_days)
            dso = self._build_gauge(
                'dso', _('DSO (días de cobro)'), dso_value, 'days', True,
                status_lower(dso_value, 30.0, 45.0),
                dso_thresholds, _('< 30 días'),
                message=_('Promedio de %(d).1f días para cobrar a clientes.')
                % {'d': dso_value},
                formula=_('Cuentas por cobrar / Ventas a crédito × Días'),
                extra={'numerator': ar_balance, 'denominator': ar_sales,
                       'period_days': period_days, 'short_period': short_period},
            )
        else:
            dso = self._build_gauge(
                'dso', _('DSO (días de cobro)'), None, 'days', False, 'unavailable',
                dso_thresholds, _('< 30 días'),
                message=_('No se detectaron ventas a crédito en el período.'),
                formula=_('Cuentas por cobrar / Ventas a crédito × Días'),
            )

        if ap_accounts and ap_purchases > 0:
            dpo_value = self._round2(ap_balance / ap_purchases * period_days)
            dpo = self._build_gauge(
                'dpo', _('DPO (días de pago)'), dpo_value, 'days', True,
                status_lower(dpo_value, 20.0, 30.0),
                dpo_thresholds, _('20–45 días'),
                message=_('Promedio de %(d).1f días para pagar a proveedores.')
                % {'d': dpo_value},
                formula=_('Cuentas por pagar / Compras a crédito × Días'),
                extra={'numerator': ap_balance, 'denominator': ap_purchases,
                       'period_days': period_days, 'short_period': short_period},
            )
        else:
            dpo = self._build_gauge(
                'dpo', _('DPO (días de pago)'), None, 'days', False, 'unavailable',
                dpo_thresholds, _('20–45 días'),
                message=_('No se detectaron compras a crédito en el período.'),
                formula=_('Cuentas por pagar / Compras a crédito × Días'),
            )

        if cogs_accounts and cogs_total > 0 and inventory_proxy > 0:
            dio_value = self._round2(inventory_proxy / cogs_total * period_days)
            dio = self._build_gauge(
                'dio', _('DIO (días en inventario)'), dio_value, 'days', True,
                status_lower(dio_value, 30.0, 60.0),
                dio_thresholds, _('< 60 días'),
                message=_('Inventario rota cada %(d).1f días en promedio.')
                % {'d': dio_value},
                formula=_('Inventario / Costo de ventas × Días'),
                extra={'numerator': inventory_proxy, 'denominator': cogs_total,
                       'period_days': period_days, 'short_period': short_period,
                       'note': _('Inventario aproximado como Activo circulante neto de caja, AR y prepagos.')},
            )
        else:
            dio_value = None
            dio = self._build_gauge(
                'dio', _('DIO (días en inventario)'), None, 'days', False, 'unavailable',
                dio_thresholds, _('< 60 días'),
                message=_('No se detectó costo de ventas o inventario en el período.'),
                formula=_('Inventario / Costo de ventas × Días'),
            )

        ccc = self._build_gauge(
            'ccc', _('CCC (ciclo de conversión de efectivo)'), None, 'days',
            False, 'unavailable',
            ccc_thresholds, _('< 45 días'),
            message=_('Faltan datos de DSO/DPO para calcular el ciclo.'),
            formula=_('DSO + DIO − DPO'),
        )
        if dso.get('available') and dpo.get('available'):
            ccc_value = self._round2(
                (dso['value'] or 0.0) + (dio_value or 0.0) - (dpo['value'] or 0.0)
            )
            ccc = self._build_gauge(
                'ccc', _('CCC (ciclo de conversión de efectivo)'), ccc_value,
                'days', True, status_lower(ccc_value, 30.0, 45.0),
                ccc_thresholds, _('< 45 días'),
                message=_('Días que el efectivo tarda en regresar al negocio.'),
                formula=_('DSO + DIO − DPO'),
                extra={'dso': dso.get('value'), 'dpo': dpo.get('value'),
                       'dio': dio_value, 'period_days': period_days,
                       'short_period': short_period},
            )

        return {'dso': dso, 'dpo': dpo, 'dio': dio, 'ccc': ccc}

    def _compute_operational_quality(self, wizard, period_start, period_end):
        """Operational quality KPIs computed in a single pass each.

        - reconciliation_pct: extractos bancarios sin conciliar.
        - analytic_coverage_pct: líneas operativas sin distribución analítica.
        """
        company = wizard.company_id
        journals = wizard.journal_ids
        if not journals:
            common = self.env['banks.weekly.balance.common']
            journals = common.search_balance_journals(company.id, [])

        reconcile_thresholds = {'warning': 10.0, 'risk': 25.0}
        analytic_thresholds = {'warning': 15.0, 'risk': 30.0}

        recon_value = None
        recon_total = 0
        recon_unrec = 0
        if 'account.bank.statement.line' in self.env:
            BSL = self.env['account.bank.statement.line']
            recon_total = BSL.search_count([
                ('company_id', '=', company.id),
                ('journal_id', 'in', journals.ids),
                ('date', '>=', period_start),
                ('date', '<=', period_end),
            ])
            if recon_total:
                recon_unrec = BSL.search_count([
                    ('company_id', '=', company.id),
                    ('journal_id', 'in', journals.ids),
                    ('date', '>=', period_start),
                    ('date', '<=', period_end),
                    ('is_reconciled', '=', False),
                ])
                recon_value = self._round2(recon_unrec / recon_total * 100.0)

        if recon_value is None:
            reconciliation = self._build_gauge(
                'reconciliation_pending', _('% Extractos sin conciliar'),
                None, 'percent', False, 'unavailable',
                reconcile_thresholds, _('< 10%'),
                message=_('No hay extractos bancarios en el período.'),
                formula=_('Líneas no conciliadas / Total de líneas'),
            )
        else:
            status = (
                'healthy' if recon_value < 10.0
                else ('warning' if recon_value < 25.0 else 'risk')
            )
            reconciliation = self._build_gauge(
                'reconciliation_pending', _('% Extractos sin conciliar'),
                recon_value, 'percent', True, status,
                reconcile_thresholds, _('< 10%'),
                message=_('%(unrec)s de %(total)s líneas pendientes.')
                % {'unrec': recon_unrec, 'total': recon_total},
                formula=_('Líneas no conciliadas / Total de líneas'),
                extra={'unreconciled': recon_unrec, 'total': recon_total},
            )

        AML = self.env['account.move.line']
        op_domain = [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', period_start),
            ('date', '<=', period_end),
            ('account_id.internal_group', 'in', ('income', 'expense')),
        ]
        op_total = AML.search_count(op_domain)
        op_no_analytic = 0
        analytic_value = None
        if op_total:
            # ``analytic_distribution`` es JSON: contar directamente las líneas
            # sin distribución (NULL, dict vacío o string vacío) en vez de
            # restar el complemento, para no clasificar como "con analítica"
            # un ``{}`` vacío.
            op_no_analytic = AML.search_count(
                op_domain
                + [('analytic_distribution', 'in', [False, '{}', ''])]
            )
            analytic_value = self._round2(op_no_analytic / op_total * 100.0)

        if analytic_value is None:
            analytic = self._build_gauge(
                'analytic_missing', _('% Sin distribución analítica'),
                None, 'percent', False, 'unavailable',
                analytic_thresholds, _('< 15%'),
                message=_('No hay movimientos operativos en el período.'),
                formula=_('Líneas income/expense sin analítica / Total'),
            )
        else:
            status = (
                'healthy' if analytic_value < 15.0
                else ('warning' if analytic_value < 30.0 else 'risk')
            )
            analytic = self._build_gauge(
                'analytic_missing', _('% Sin distribución analítica'),
                analytic_value, 'percent', True, status,
                analytic_thresholds, _('< 15%'),
                message=_('%(no)s de %(total)s líneas operativas sin analítica.')
                % {'no': op_no_analytic, 'total': op_total},
                formula=_('Líneas income/expense sin analítica / Total'),
                extra={'missing': op_no_analytic, 'total': op_total},
            )

        return {
            'reconciliation_pending': reconciliation,
            'analytic_missing': analytic,
        }

    def _compute_projection_gauges(self, *, cash_forecast, cash_runway,
                                   period_end, historical_comparison):
        """Gauges de proyección y comparativos.

        - Días hasta saldo cero (proyección lineal del forecast).
        - Variación de saldo final vs período anterior.
        - Variación de flujo neto vs período anterior.
        """
        days_thresholds = {'risk': 15.0, 'warning': 30.0}
        zero_value = None
        if cash_forecast.get('available'):
            risk_date_iso = cash_forecast.get('risk_date')
            if risk_date_iso and period_end:
                try:
                    risk_d = fields.Date.from_string(risk_date_iso)
                    zero_value = float((risk_d - period_end).days)
                    zero_value = max(zero_value, 0.0)
                except (TypeError, ValueError):
                    zero_value = None
            elif cash_runway.get('coverage_days') is not None:
                zero_value = float(cash_runway['coverage_days'])
        zero_status = 'unavailable'
        if zero_value is not None:
            zero_status = (
                'healthy' if zero_value >= 30.0
                else ('warning' if zero_value >= 15.0 else 'risk')
            )
        days_to_zero = self._build_gauge(
            'days_to_zero', _('Días hasta saldo cero (proy.)'),
            zero_value, 'days', zero_value is not None, zero_status,
            days_thresholds, _('≥ 30 días'),
            message=(
                _('Al ritmo actual, el saldo llegaría a cero en %(d).0f días.')
                % {'d': zero_value} if zero_value is not None
                else _('Sin datos suficientes para proyectar.')
            ),
            formula=_('Días entre la fecha actual y el saldo proyectado = 0'),
        )

        comparisons = (historical_comparison or {}).get('comparisons') or {}
        var_thresholds = {'warning': 5.0, 'risk': 15.0}

        def _abs_pct_status(delta_pct, healthy_max, warning_max):
            if delta_pct is None:
                return 'unavailable'
            v = abs(delta_pct)
            if v <= healthy_max:
                return 'healthy'
            if v <= warning_max:
                return 'warning'
            return 'risk'

        balance_cmp = comparisons.get('final_balance') or {}
        balance_delta_pct = balance_cmp.get('delta_pct')
        balance_var = self._build_gauge(
            'balance_variation', _('Var. saldo final vs mes anterior'),
            balance_delta_pct if balance_delta_pct is not None else None,
            'percent',
            balance_delta_pct is not None,
            _abs_pct_status(balance_delta_pct, 5.0, 15.0),
            var_thresholds, _('|Δ| < 5%'),
            message=(
                _('Saldo final cambió %(pct).2f%% respecto al período anterior.')
                % {'pct': balance_delta_pct} if balance_delta_pct is not None
                else _('No hay período previo comparable.')
            ),
            formula=_('(Saldo actual − Saldo previo) / |Saldo previo| × 100'),
        )

        flow_cmp = comparisons.get('net_flow') or {}
        flow_delta_pct = flow_cmp.get('delta_pct')
        flow_var = self._build_gauge(
            'flow_variation', _('Var. flujo neto vs mes anterior'),
            flow_delta_pct if flow_delta_pct is not None else None,
            'percent',
            flow_delta_pct is not None,
            _abs_pct_status(flow_delta_pct, 10.0, 30.0),
            {'warning': 10.0, 'risk': 30.0}, _('|Δ| < 10%'),
            message=(
                _('Flujo neto cambió %(pct).2f%% respecto al período anterior.')
                % {'pct': flow_delta_pct} if flow_delta_pct is not None
                else _('No hay período previo comparable.')
            ),
            formula=_('(Flujo actual − Flujo previo) / |Flujo previo| × 100'),
        )

        return [days_to_zero, balance_var, flow_var]

    def _build_indicator_gauges(self, *, liquidity_score, cash_runway,
                                current_ratio, quick_ratio,
                                bank_concentration, cash_ratio, cash_cycle,
                                operational_quality, projection_gauges=None):
        """Group all gauges into the structure expected by the frontend.

        Returns ``{'groups': [...], 'gauges': [...]}`` so the UI can render
        either a flat list or grouped sections.
        """
        score_thresholds = {'risk': 50, 'warning': 70}
        runway_thresholds = {'risk': 15.0, 'warning': 30.0}
        cr_thresholds = {'risk': 1.00, 'warning': 1.50}
        qr_thresholds = {'risk': 0.70, 'warning': 1.00}
        conc_thresholds = {'warning': 60.0, 'risk': 80.0}

        liquidity_gauge = self._build_gauge(
            'liquidity_score', _('Score de liquidez'),
            liquidity_score.get('score'), 'score',
            liquidity_score.get('score') is not None,
            liquidity_score.get('level') or 'unavailable',
            score_thresholds, _('≥ 70 puntos'),
            message=liquidity_score.get('description') or '',
            formula=_('Promedio ponderado de salud financiera (0–100).'),
        )

        runway_value = cash_runway.get('coverage_days')
        runway_status = 'unavailable'
        if runway_value is not None:
            runway_status = (
                'healthy' if runway_value >= 30.0
                else ('warning' if runway_value >= 15.0 else 'risk')
            )
        runway_gauge = self._build_gauge(
            'cash_runway', _('Días de cobertura de caja'),
            runway_value, 'days',
            cash_runway.get('available') and runway_value is not None,
            runway_status,
            runway_thresholds, _('≥ 30 días'),
            message=cash_runway.get('message') or '',
            formula=_('Saldo final / Salidas diarias promedio'),
        )

        cr_gauge = self._build_gauge(
            'current_ratio', current_ratio.get('title') or _('Liquidez corriente'),
            current_ratio.get('value'), 'ratio',
            current_ratio.get('available'), current_ratio.get('status'),
            cr_thresholds, current_ratio.get('healthy_range') or _('> 1.50'),
            message=current_ratio.get('message') or '',
            formula=current_ratio.get('formula') or '',
        )
        qr_gauge = self._build_gauge(
            'quick_ratio', quick_ratio.get('title') or _('Prueba ácida'),
            quick_ratio.get('value'), 'ratio',
            quick_ratio.get('available'), quick_ratio.get('status'),
            qr_thresholds, quick_ratio.get('healthy_range') or _('> 1.00'),
            message=quick_ratio.get('message') or '',
            formula=quick_ratio.get('formula') or '',
        )
        dominant = bank_concentration.get('dominant_bank') or {}
        conc_value = dominant.get('balance_percentage')
        conc_status = 'unavailable'
        if conc_value is not None:
            conc_status = (
                'healthy' if conc_value < 60.0
                else ('warning' if conc_value < 80.0 else 'risk')
            )
        conc_gauge = self._build_gauge(
            'bank_concentration', _('Concentración bancaria'),
            conc_value, 'percent',
            conc_value is not None, conc_status,
            conc_thresholds, _('< 60%'),
            message=(_('Banco dominante: %(name)s') % {'name': dominant.get('bank_name', '—')}
                     if conc_value is not None else ''),
            formula=_('Saldo del banco principal / Saldo total bancos'),
        )

        liquidity_gauges = [
            liquidity_gauge, runway_gauge, cr_gauge, qr_gauge,
            cash_ratio, conc_gauge,
        ]
        cycle_gauges = [
            cash_cycle.get('dso'), cash_cycle.get('dpo'),
            cash_cycle.get('dio'), cash_cycle.get('ccc'),
        ]
        quality_gauges = [
            operational_quality.get('reconciliation_pending'),
            operational_quality.get('analytic_missing'),
        ]
        groups = [
            {'id': 'liquidity', 'title': _('Liquidez y reservas'),
             'gauges': liquidity_gauges},
            {'id': 'cycle', 'title': _('Ciclo de efectivo'),
             'gauges': cycle_gauges},
            {'id': 'quality', 'title': _('Calidad operativa'),
             'gauges': quality_gauges},
        ]
        if projection_gauges:
            groups.append({
                'id': 'projection',
                'title': _('Proyección y comparativos'),
                'gauges': [g for g in projection_gauges if g],
            })
        flat = [g for grp in groups for g in grp['gauges'] if g]
        return {'groups': groups, 'gauges': flat}

    def build_payload(self, wizard, options=None):
        """Build full financial health JSON reusing operational dashboard data."""
        options = dict(options or {})
        common = self.env['banks.weekly.balance.common']
        # This tab only consumes weeks + KPIs + aggregations; ask the common
        # builder to skip charts/insights/waterfall (and the per-bucket metric
        # query) to avoid recomputing data we never read here.
        dash = common.build_dashboard_payload(wizard, {**options, '_light': True})
        if not dash.get('has_data'):
            return self._empty_payload(dash)

        company = wizard.company_id
        journals = common.search_balance_journals(
            company.id, wizard.journal_ids.ids
        ).filtered('default_account_id').sorted(key=lambda j: j.name or '')
        account_ids_set = journals.mapped('default_account_id').ids
        period_start = fields.Date.from_string(dash['period']['date_from'])
        period_end = fields.Date.from_string(dash['period']['date_to'])
        period_days = self._period_day_count(period_start, period_end)

        aggregations = dash.get('_aggregations') or {}
        end_bal = aggregations.get('end_balance')
        if end_bal is None:
            end_bal = common._sums_through_date(
                company, account_ids_set, period_end,
            )
        agg_debit_src = aggregations.get('agg_debit')
        agg_credit_src = aggregations.get('agg_credit')
        if agg_debit_src is not None and agg_credit_src is not None:
            agg_debit = {aid: agg_debit_src.get(aid, 0.0) for aid in account_ids_set}
            agg_credit = {aid: agg_credit_src.get(aid, 0.0) for aid in account_ids_set}
        else:
            agg_debit = {aid: 0.0 for aid in account_ids_set}
            agg_credit = {aid: 0.0 for aid in account_ids_set}
            for wb in dash.get('week_blocks', []):
                in_row = next((r for r in wb['rows'] if r['row_type'] == 'inflow'), None)
                out_row = next((r for r in wb['rows'] if r['row_type'] == 'outflow'), None)
                for idx, journal in enumerate(journals):
                    aid = journal.default_account_id.id
                    if in_row:
                        agg_debit[aid] += in_row['amounts'][idx] if idx < len(in_row['amounts']) else 0.0
                    if out_row:
                        agg_credit[aid] += out_row['amounts'][idx] if idx < len(out_row['amounts']) else 0.0

        kpis = dash.get('kpis') or {}
        weeks = dash.get('weeks') or []
        final_balance = kpis.get('final_balance') or 0.0
        net_flow = kpis.get('net_flow') or 0.0
        total_out = kpis.get('total_outflows') or 0.0
        min_balance = min((w.get('final_balance', 0.0) for w in weeks), default=final_balance)

        cash_runway = self._compute_cash_runway(final_balance, total_out, period_days)
        cash_forecast = self._compute_cash_forecast(
            final_balance, net_flow, period_days, period_end, weeks,
        )
        bank_concentration = self._compute_bank_concentration(
            journals, end_bal, agg_debit, agg_credit, company=company,
        )
        liquidity_trend = self._compute_liquidity_trend(weeks, kpis)

        _ca_accounts, current_assets = self._sum_account_type_balance(
            company, _CURRENT_ASSET_TYPES, period_end, common,
        )
        _cl_accounts, current_liabilities = self._sum_account_type_balance(
            company, _CURRENT_LIABILITY_TYPES, period_end, common,
        )
        _qa_accounts, quick_assets = self._sum_account_type_balance(
            company, _QUICK_ASSET_TYPES, period_end, common,
        )

        _CR_THRESHOLDS = {'risk': 1.00, 'warning': 1.50}
        _QR_THRESHOLDS = {'risk': 0.70, 'warning': 1.00}
        _CF_THRESHOLDS = {'risk': 0.80, 'warning': 1.00}

        current_ratio = self._build_ratio_detail(
            'current_ratio', _('Liquidez corriente'), None, False, 'unavailable',
            _('No se encontraron cuentas clasificadas como circulantes.'),
            _('Activos circulantes / Pasivos circulantes'),
            _('> 1.50'),
            thresholds=_CR_THRESHOLDS,
        )
        if _ca_accounts and _cl_accounts and current_liabilities > 0:
            cr_value = self._round2(current_assets / current_liabilities)
            status = self._ratio_status(cr_value, 1.50, 1.00)
            current_ratio = self._build_ratio_detail(
                'current_ratio', _('Liquidez corriente'), cr_value, True, status,
                _('Capacidad de cubrir obligaciones de corto plazo.'),
                _('Activos circulantes / Pasivos circulantes'),
                _('> 1.50'),
                numerator=current_assets,
                denominator=current_liabilities,
                thresholds=_CR_THRESHOLDS,
            )

        quick_ratio = self._build_ratio_detail(
            'quick_ratio', _('Prueba ácida'), None, False, 'unavailable',
            _('No se pudieron clasificar activos rápidos o pasivos corrientes.'),
            _('Activos rápidos / Pasivos circulantes'),
            _('> 1.00'),
            thresholds=_QR_THRESHOLDS,
        )
        if _qa_accounts and _cl_accounts and current_liabilities > 0:
            qr_value = self._round2(quick_assets / current_liabilities)
            status = self._ratio_status(qr_value, 1.00, 0.70)
            quick_ratio = self._build_ratio_detail(
                'quick_ratio', _('Prueba ácida'), qr_value, True, status,
                _('Liquidez inmediata excluyendo inventario.'),
                _('Activos rápidos / Pasivos circulantes'),
                _('> 1.00'),
                numerator=quick_assets,
                denominator=current_liabilities,
                thresholds=_QR_THRESHOLDS,
            )

        working_capital = self._build_ratio_detail(
            'working_capital', _('Capital de trabajo'), None, False, 'unavailable',
            _('Requiere activos y pasivos circulantes clasificados.'),
            _('Activos circulantes − Pasivos circulantes'),
            _('> 0 positivo'),
            value_is_money=True,
        )
        if current_ratio.get('available'):
            wc_value = self._round2(current_assets - current_liabilities)
            wc_status = 'positive' if wc_value > 0 else ('neutral' if wc_value == 0 else 'negative')
            working_capital = self._build_ratio_detail(
                'working_capital', _('Capital de trabajo'), wc_value, True, wc_status,
                _('Margen operativo de corto plazo.'),
                _('Activos circulantes − Pasivos circulantes'),
                _('> 0 positivo'),
                numerator=current_assets,
                denominator=current_liabilities,
                value_is_money=True,
            )

        cash_flow_coverage = self._build_ratio_detail(
            'cash_flow_coverage', _('Cobertura de flujo'), None, False, 'unavailable',
            _('No hay pasivos corrientes identificables.'),
            _('Flujo neto / Pasivos corrientes'),
            _('> 1.00'),
            thresholds=_CF_THRESHOLDS,
        )
        if current_liabilities and _cl_accounts:
            cf_value = self._round2(net_flow / current_liabilities)
            status = self._ratio_status(cf_value, 1.00, 0.80)
            cash_flow_coverage = self._build_ratio_detail(
                'cash_flow_coverage', _('Cobertura de flujo'), cf_value, True, status,
                _('Capacidad del flujo del período para cubrir deuda corriente.'),
                _('Flujo neto / Pasivos corrientes'),
                _('> 1.00'),
                numerator=self._round2(net_flow),
                denominator=current_liabilities,
                thresholds=_CF_THRESHOLDS,
            )

        financial_ratios = {
            'current_ratio': current_ratio,
            'quick_ratio': quick_ratio,
            'working_capital': working_capital,
            'cash_flow_coverage': cash_flow_coverage,
        }

        liquidity_risk = self._compute_liquidity_risk(
            final_balance, min_balance, net_flow, cash_runway.get('coverage_days'),
            current_ratio, quick_ratio, working_capital, bank_concentration,
        )
        liquidity_score = self._compute_liquidity_score(
            kpis, cash_runway, bank_concentration, liquidity_trend,
            current_ratio, quick_ratio, cash_flow_coverage,
        )
        financial_timeline = self._compute_financial_timeline(
            weeks, kpis, bank_concentration, cash_forecast,
            current_ratio, liquidity_trend,
        )
        executive_summary = self._compute_executive_summary(
            liquidity_score, liquidity_risk, cash_forecast,
            bank_concentration, cash_runway,
        )
        recommendations = self._compute_recommendations(
            liquidity_score, bank_concentration, kpis,
            cash_runway, cash_forecast, current_ratio,
        )
        smart_alerts = self._compute_smart_alerts(
            kpis, cash_forecast, bank_concentration,
            cash_runway, liquidity_trend, current_ratio, quick_ratio,
        )

        current_metrics = {
            'final_balance': kpis.get('final_balance'),
            'net_flow': kpis.get('net_flow'),
            'total_inflows': kpis.get('total_inflows'),
            'total_outflows': kpis.get('total_outflows'),
            'coverage_days': cash_runway.get('coverage_days'),
            'liquidity_score': liquidity_score.get('score'),
            'concentration_pct': (
                bank_concentration.get('dominant_bank') or {}
            ).get('balance_percentage'),
        }
        historical_comparison = {'available': False}
        if not options.get('_skip_history'):
            historical_comparison = self._compute_historical_comparison(
                wizard, options, current_metrics, common,
            )

        cash_ratio = self._compute_cash_ratio(
            company, period_end, current_liabilities, _cl_accounts, common,
        )
        cash_cycle = self._compute_cash_cycle(
            company, period_start, period_end,
            current_assets, current_liabilities,
            _ca_accounts, _cl_accounts, common,
        )
        operational_quality = self._compute_operational_quality(
            wizard, period_start, period_end,
        )
        projection_gauges = self._compute_projection_gauges(
            cash_forecast=cash_forecast,
            cash_runway=cash_runway,
            period_end=period_end,
            historical_comparison=historical_comparison,
        )
        indicator_gauges = self._build_indicator_gauges(
            liquidity_score=liquidity_score,
            cash_runway=cash_runway,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            bank_concentration=bank_concentration,
            cash_ratio=cash_ratio,
            cash_cycle=cash_cycle,
            operational_quality=operational_quality,
            projection_gauges=projection_gauges,
        )

        return {
            'has_data': True,
            'error_message': '',
            'period': dash.get('period') or {},
            'currency': dash.get('currency') or {},
            'executive_summary': executive_summary,
            'liquidity_score': liquidity_score,
            'liquidity_risk': liquidity_risk,
            'cash_forecast': cash_forecast,
            'cash_runway': cash_runway,
            'liquidity_trend': liquidity_trend,
            'financial_ratios': financial_ratios,
            'bank_concentration': bank_concentration,
            'historical_comparison': historical_comparison,
            'smart_alerts': smart_alerts,
            'recommendations': recommendations,
            'financial_timeline': financial_timeline,
            'current_ratio': current_ratio,
            'quick_ratio': quick_ratio,
            'working_capital': working_capital,
            'cash_flow_coverage': cash_flow_coverage,
            'cash_ratio': cash_ratio,
            'cash_cycle': cash_cycle,
            'operational_quality': operational_quality,
            'indicator_gauges': indicator_gauges,
        }
