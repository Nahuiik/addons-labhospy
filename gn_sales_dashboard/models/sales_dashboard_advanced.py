# -*- coding: utf-8 -*-
"""Fase 3: health score, forecast, RFM, Pareto, cohortes, alertas, metas."""

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SalesDashboardAdvanced(models.AbstractModel):
    _inherit = 'sales.dashboard.service'

    ADVANCED_KEYS = (
        'health', 'goal_tracker', 'forecast', 'waterfall', 'alerts',
        'rfm', 'pareto_customers', 'pareto_products', 'cohorts',
    )

    @api.model
    def get_dashboard_advanced(self, filters=None, keys=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        cache = {}
        requested = keys or list(self.ADVANCED_KEYS)
        compare = self._comparison_parsed(parsed)
        metrics = prev_metrics = None
        if set(requested) & {'health', 'goal_tracker', 'alerts', 'waterfall', 'forecast'}:
            metrics = self._compute_metrics(parsed, cache)
            if compare:
                prev_metrics = self._compute_metrics(compare, cache)

        builders = {
            'health': lambda p: self._build_health_score(
                p, cache, metrics=metrics, prev_metrics=prev_metrics,
            ),
            'goal_tracker': lambda p: self._build_goal_tracker(p, cache, metrics=metrics),
            'forecast': lambda p: self._build_forecast(p, cache),
            'waterfall': lambda p: self._build_waterfall(p, cache),
            'alerts': lambda p: self._build_alerts(
                p, cache, metrics=metrics, prev_metrics=prev_metrics,
            ),
            'rfm': lambda p: self._build_rfm(p, cache),
            'pareto_customers': lambda p: self._build_pareto(p, 'customers', cache=cache),
            'pareto_products': lambda p: self._build_pareto(p, 'products', cache=cache),
            'cohorts': self._build_cohorts,
        }
        out = {}
        for key in requested:
            fn = builders.get(key)
            if fn:
                out[key] = fn(parsed)
        return {'success': True, 'advanced': out}

    @api.model
    def _build_summary_advanced(self, parsed, cache, metrics=None, prev_metrics=None):
        """Health + meta + alertas reutilizando métricas ya calculadas."""
        if metrics is None:
            metrics = self._compute_metrics(parsed, cache)
        if prev_metrics is None:
            compare = self._comparison_parsed(parsed)
            prev_metrics = self._compute_metrics(compare, cache) if compare else {}
        return {
            'health': self._build_health_score(
                parsed, cache, metrics=metrics, prev_metrics=prev_metrics,
            ),
            'goal_tracker': self._build_goal_tracker(parsed, cache, metrics=metrics),
            'alerts': self._build_alerts(
                parsed, cache, metrics=metrics, prev_metrics=prev_metrics,
            ),
        }

    @api.model
    def _dashboard_config(self, parsed):
        return self.env['sales.dashboard.config'].get_for_company(parsed['company'])

    # ------------------------------------------------------------------
    # Metas propias
    # ------------------------------------------------------------------

    @api.model
    def _resolve_targets(self, parsed):
        Target = self.env['sales.dashboard.target']
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('date_from', '<=', parsed['date_to']),
            ('date_to', '>=', parsed['date_from']),
        ]
        if parsed.get('branch_id'):
            domain.append(('branch_id', 'in', [False, parsed['branch_id']]))
        if parsed.get('team_id'):
            domain.append(('team_id', 'in', [False, parsed['team_id']]))
        if parsed.get('user_id'):
            domain.append(('user_id', 'in', [False, parsed['user_id']]))
        targets = Target.search(domain)
        amount = sum(targets.mapped('target_sales'))
        if amount:
            return amount, 'sales.dashboard.target'
        ct_amount, _ = self._target_for_period(parsed, 0.0)
        if ct_amount:
            return ct_amount, 'commission.target'
        return 0.0, None

    @api.model
    def _build_goal_tracker(self, parsed, cache=None, metrics=None):
        if metrics is None:
            metrics = self._compute_metrics(parsed, cache)
        net = metrics['net_sales']['value']
        target, source = self._resolve_targets(parsed)
        today = parsed['date_to']
        days_total = (parsed['date_to'] - parsed['date_from']).days + 1
        days_elapsed = max(1, (today - parsed['date_from']).days + 1)
        days_remaining = max(0, days_total - days_elapsed)
        achievement = (net / target * 100.0) if target else 0.0
        daily_actual = net / days_elapsed
        required_daily = ((target - net) / days_remaining) if days_remaining and target > net else 0.0
        projection = net + daily_actual * days_remaining
        risk = 'ok'
        if target and achievement < 70 and days_remaining < days_total * 0.4:
            risk = 'critical'
        elif target and achievement < 85:
            risk = 'warning'
        message = _('La meta del período está encaminada.')
        if target and projection < target:
            message = _(
                'La proyección indica un cierre de %(proj)s por debajo de la meta (%(target)s).',
                proj=self._fmt_currency(projection, parsed),
                target=self._fmt_currency(target, parsed),
            )
        elif target and required_daily > daily_actual * 1.1:
            message = _(
                'Se necesitan ventas promedio de %(req)s por día para alcanzar la meta.',
                req=self._fmt_currency(required_daily, parsed),
            )
        return {
            'target': target,
            'actual': net,
            'achievement': achievement,
            'projection': projection,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'required_daily': required_daily,
            'daily_actual': daily_actual,
            'risk': risk,
            'message': message,
            'source': source or _('Sin meta configurada'),
        }

    @api.model
    def _fmt_currency(self, amount, parsed):
        cur = parsed['company'].currency_id
        return f'{cur.symbol} {amount:,.2f}'

    # ------------------------------------------------------------------
    # Sales Health Score
    # ------------------------------------------------------------------

    @api.model
    def _build_health_score(self, parsed, cache=None, metrics=None, prev_metrics=None):
        cfg = self._dashboard_config(parsed)
        if metrics is None:
            metrics = self._compute_metrics(parsed, cache)
        if prev_metrics is None:
            compare = self._comparison_parsed(parsed)
            prev_metrics = self._compute_metrics(compare, cache) if compare else {}

        net = metrics['net_sales']['value']
        prev_net = prev_metrics.get('net_sales', {}).get('value', 0.0)
        growth = self._variation_pct(net, prev_net)
        margin_pct = metrics['margin_pct']['value']
        conversion = metrics['conversion_rate']['value']
        credits = metrics['credit_notes']['value']
        returns_pct = (credits / net * 100.0) if net else 0.0
        target, _src = self._resolve_targets(parsed)
        target_pct = (net / target * 100.0) if target else 100.0

        pareto = self._build_pareto(parsed, 'customers', cache=cache)
        top_share = pareto.get('top_share_pct', 0.0)

        pipeline = metrics['pipeline_open']['value']
        pipeline_ratio = (pipeline / net) if net else 0.0

        recurring = metrics['active_customers']['value'] - metrics['new_customers']['value']
        recurring_ratio = (recurring / max(metrics['active_customers']['value'], 1)) * 100.0

        ticket = metrics['avg_ticket']['value']
        prev_ticket = prev_metrics.get('avg_ticket', {}).get('value', ticket)
        ticket_trend = self._variation_pct(ticket, prev_ticket)

        factors = [
            {
                'key': 'growth', 'label': _('Crecimiento de ventas'), 'weight': cfg.weight_growth,
                'score': self._score_linear(growth, -20, 30),
                'value': growth, 'unit': '%',
            },
            {
                'key': 'target', 'label': _('Cumplimiento de meta'), 'weight': cfg.weight_target,
                'score': min(100.0, target_pct), 'value': target_pct, 'unit': '%',
            },
            {
                'key': 'margin', 'label': _('Margen bruto'), 'weight': cfg.weight_margin,
                'score': self._score_linear(margin_pct, cfg.margin_min_pct, 40),
                'value': margin_pct, 'unit': '%',
            },
            {
                'key': 'conversion', 'label': _('Conversión CRM'), 'weight': cfg.weight_conversion,
                'score': min(100.0, conversion * 2), 'value': conversion, 'unit': '%',
            },
            {
                'key': 'concentration', 'label': _('Diversificación clientes'), 'weight': cfg.weight_concentration,
                'score': max(0.0, 100.0 - top_share * 2),
                'value': top_share, 'unit': '%',
            },
            {
                'key': 'returns', 'label': _('Control devoluciones'), 'weight': cfg.weight_returns,
                'score': max(0.0, 100.0 - returns_pct * 5),
                'value': returns_pct, 'unit': '%',
            },
            {
                'key': 'pipeline', 'label': _('Cobertura pipeline'), 'weight': cfg.weight_pipeline,
                'score': min(100.0, pipeline_ratio * 50),
                'value': pipeline_ratio, 'unit': 'x',
            },
            {
                'key': 'recurring', 'label': _('Clientes recurrentes'), 'weight': cfg.weight_recurring,
                'score': min(100.0, recurring_ratio),
                'value': recurring_ratio, 'unit': '%',
            },
            {
                'key': 'ticket', 'label': _('Tendencia ticket'), 'weight': cfg.weight_ticket,
                'score': self._score_linear(ticket_trend, -15, 15),
                'value': ticket_trend, 'unit': '%',
            },
        ]
        total_weight = sum(f['weight'] for f in factors) or 100.0
        score = sum(f['score'] * f['weight'] for f in factors) / total_weight
        score = max(0.0, min(100.0, score))
        status = _('Excelente') if score >= 80 else _('Bueno') if score >= 60 else _('Regular') if score >= 40 else _('Crítico')
        prev_score = score - growth * 0.1  # aproximación comparativa
        recommendations = []
        if margin_pct < cfg.margin_min_pct:
            recommendations.append(_('Revisar precios o costos: margen por debajo del umbral.'))
        if top_share > cfg.concentration_max_pct:
            recommendations.append(_('Alta concentración en pocos clientes: diversificar cartera.'))
        if target and target_pct < 80:
            recommendations.append(_('Meta en riesgo: intensificar actividad comercial.'))
        return {
            'score': round(score, 1),
            'previous_score': round(prev_score, 1),
            'status': status,
            'factors': factors,
            'recommendations': recommendations,
        }

    @staticmethod
    def _score_linear(value, low, high):
        if high <= low:
            return 50.0
        pct = (value - low) / (high - low) * 100.0
        return max(0.0, min(100.0, pct))

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------

    @api.model
    def _build_forecast(self, parsed, cache=None):
        cfg = self._dashboard_config(parsed)
        by_day = self._daily_net_sales_map(parsed, cache)
        if len(by_day) < 3:
            return {
                'method': cfg.forecast_method,
                'method_label': dict(cfg._fields['forecast_method'].selection).get(cfg.forecast_method),
                'insufficient_data': True,
                'message': _('Datos históricos insuficientes para pronosticar.'),
                'series': [], 'confidence': 0,
            }
        values = list(by_day.values())
        method = cfg.forecast_method
        horizon = min(30, max(7, (parsed['date_to'] - parsed['date_from']).days // 3))
        if method == 'moving_avg':
            window = min(7, len(values))
            base = sum(values[-window:]) / window
            forecast_vals = [base] * horizon
        elif method == 'exp_smoothing':
            alpha = 0.3
            smoothed = values[0]
            for v in values[1:]:
                smoothed = alpha * v + (1 - alpha) * smoothed
            forecast_vals = [smoothed] * horizon
        elif method == 'daily_pace':
            days = (parsed['date_to'] - parsed['date_from']).days + 1
            pace = sum(values) / max(days, 1)
            forecast_vals = [pace] * horizon
        else:  # linear
            n = len(values)
            x_mean = (n - 1) / 2.0
            y_mean = sum(values) / n
            num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
            den = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
            slope = num / den
            intercept = y_mean - slope * x_mean
            forecast_vals = [max(0.0, intercept + slope * (n + i)) for i in range(horizon)]

        hist_labels = sorted(by_day.keys())[-30:]
        hist_data = [by_day[k] for k in hist_labels]
        last_date = parsed['date_to']
        fc_labels = []
        for i in range(1, horizon + 1):
            fc_labels.append(fields.Date.to_string(last_date + timedelta(days=i)))
        mape = self._forecast_mape(values, method)
        return {
            'method': method,
            'method_label': dict(cfg._fields['forecast_method'].selection).get(method),
            'insufficient_data': False,
            'historical_labels': hist_labels,
            'historical_data': hist_data,
            'forecast_labels': fc_labels,
            'forecast_data': forecast_vals,
            'confidence': max(0, min(100, 100 - mape)),
            'mape': mape,
            'message': _('Pronóstico basado en ventas netas facturadas. No utiliza IA.'),
        }

    @api.model
    def _forecast_mape(self, values, method):
        if len(values) < 5:
            return 50.0
        errors = []
        for i in range(3, len(values)):
            train = values[:i]
            actual = values[i]
            if method == 'moving_avg':
                pred = sum(train[-3:]) / 3
            else:
                pred = sum(train) / len(train)
            if actual:
                errors.append(abs(actual - pred) / abs(actual) * 100.0)
        return sum(errors) / len(errors) if errors else 25.0

    # ------------------------------------------------------------------
    # Waterfall
    # ------------------------------------------------------------------

    @api.model
    def _build_waterfall(self, parsed, cache=None):
        inv_agg = self._aggregate_invoices(self._invoices_in_period(parsed, cache), cache)
        gross = inv_agg['gross_invoicing']
        credits = inv_agg['credit_notes']
        net = inv_agg['net_sales']
        margin = inv_agg['gross_margin']
        invoices = self._invoices_in_period(parsed, cache)
        tax = sum((i.amount_total - i.amount_untaxed) for i in invoices if i.move_type == 'out_invoice')
        tax -= sum((i.amount_total - i.amount_untaxed) for i in invoices if i.move_type == 'out_refund')
        steps = [
            {'label': _('Venta bruta'), 'value': gross, 'type': 'positive'},
            {'label': _('Notas de crédito'), 'value': -credits, 'type': 'negative'},
            {'label': _('Venta neta'), 'value': net, 'type': 'subtotal'},
            {'label': _('Impuestos'), 'value': tax, 'type': 'neutral'},
            {'label': _('Costo'), 'value': -(net - margin), 'type': 'negative'},
            {'label': _('Margen bruto'), 'value': margin, 'type': 'total'},
        ]
        return {'steps': steps, 'source': 'invoice'}

    # ------------------------------------------------------------------
    # Alertas
    # ------------------------------------------------------------------

    @api.model
    def _build_alerts(self, parsed, cache=None, metrics=None, prev_metrics=None):
        cfg = self._dashboard_config(parsed)
        if metrics is None:
            metrics = self._compute_metrics(parsed, cache)
        if prev_metrics is None:
            compare = self._comparison_parsed(parsed)
            prev_metrics = self._compute_metrics(compare, cache) if compare else {}
        alerts = []

        net = metrics['net_sales']['value']
        prev_net = prev_metrics.get('net_sales', {}).get('value', net)
        drop = self._variation_pct(net, prev_net)
        if drop <= -15:
            alerts.append(self._alert('critical', _('Caída significativa de ventas'),
                _('Las ventas netas cayeron %(pct).1f%% vs el período anterior.', pct=drop),
                net, prev_net, 'net_sales'))

        margin_pct = metrics['margin_pct']['value']
        if margin_pct < cfg.margin_min_pct:
            alerts.append(self._alert('warning', _('Margen por debajo del umbral'),
                _('Margen actual %(m).1f%% · umbral %(u).1f%%.', m=margin_pct, u=cfg.margin_min_pct),
                margin_pct, cfg.margin_min_pct, 'margin_pct'))

        goal = self._build_goal_tracker(parsed, cache, metrics=metrics)
        if goal['target'] and goal['risk'] == 'critical':
            alerts.append(self._alert('critical', _('Meta en riesgo'), goal['message'],
                goal['achievement'], 100.0, 'target_achievement'))

        pareto = self._build_pareto(parsed, 'customers', cache=cache)
        if pareto.get('top_share_pct', 0) > cfg.concentration_max_pct:
            alerts.append(self._alert('warning', _('Alta concentración de clientes'),
                _('Top clientes concentran %(p).1f%% de ventas.', p=pareto['top_share_pct']),
                pareto['top_share_pct'], cfg.concentration_max_pct, 'pareto_customers'))

        credits = metrics['credit_notes']['value']
        if net and credits / net > 0.1:
            alerts.append(self._alert('warning', _('Incremento de devoluciones'),
                _('Notas de crédito representan %(p).1f%% de ventas.', p=credits / net * 100),
                credits, net * 0.1, 'credit_notes'))

        pipeline = metrics['pipeline_open']['value']
        if net and pipeline < net * 0.5:
            alerts.append(self._alert('info', _('Pipeline insuficiente'),
                _('Pipeline abierto cubre menos del 50%% de ventas del período.'),
                pipeline, net * 0.5, 'pipeline_open'))

        stalled_days = cfg.stalled_opportunity_days
        stale = self.env['crm.lead'].search_count(
            self._crm_domain(parsed, [
                ('probability', '<', 100),
                ('date_last_stage_update', '<',
                 fields.Datetime.now() - timedelta(days=stalled_days)),
            ])
        ) if 'date_last_stage_update' in self.env['crm.lead']._fields else 0
        if stale:
            alerts.append(self._alert('info', _('Oportunidades estancadas'),
                _('%(n)s oportunidades sin avance en %(d)s+ días.', n=stale, d=stalled_days),
                stale, 0, 'pipeline_open'))

        unpaid = self.env['account.move'].search_count([
            ('company_id', '=', parsed['company'].id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date', '>=', parsed['date_from']),
            ('invoice_date', '<=', parsed['date_to']),
        ])
        if unpaid > 10:
            alerts.append(self._alert('info', _('Facturación pendiente de cobro'),
                _('%(n)s facturas con saldo pendiente en el período.', n=unpaid),
                unpaid, 10, 'invoice_count'))

        return {'items': alerts, 'unread_count': len(alerts)}

    @api.model
    def _alert(self, severity, title, explanation, value, threshold, metric):
        return {
            'severity': severity,
            'title': title,
            'explanation': explanation,
            'value': value,
            'threshold': threshold,
            'metric': metric,
            'read': False,
        }

    # ------------------------------------------------------------------
    # RFM
    # ------------------------------------------------------------------

    @api.model
    def _build_rfm(self, parsed, cache=None):
        cfg = self._dashboard_config(parsed)
        invoices = self._invoices_in_period(parsed, cache)
        today = parsed['date_to']
        partner_data = defaultdict(lambda: {'sales': 0.0, 'count': 0, 'last': None})
        for inv in invoices:
            p = inv.partner_id.commercial_partner_id
            if not p:
                continue
            pid = p.id
            partner_data[pid]['sales'] += self._invoice_signed_untaxed(inv)
            partner_data[pid]['count'] += 1
            d = inv.invoice_date
            if d and (not partner_data[pid]['last'] or d > partner_data[pid]['last']):
                partner_data[pid]['last'] = d

        rows = []
        for pid, d in partner_data.items():
            recency = (today - d['last']).days if d['last'] else 999
            rows.append({
                'partner_id': pid,
                'name': self.env['res.partner'].browse(pid).display_name,
                'recency_days': recency,
                'frequency': d['count'],
                'monetary': d['sales'],
            })
        if not rows:
            return {'segments': [], 'rows': [], 'insufficient_data': True}

        rows.sort(key=lambda r: r['monetary'], reverse=True)
        for r in rows:
            r['r_score'] = 5 if r['recency_days'] <= 30 else 4 if r['recency_days'] <= 60 else 3 if r['recency_days'] <= cfg.rfm_recency_days else 2 if r['recency_days'] <= 180 else 1
            r['f_score'] = min(5, max(1, r['frequency']))
            r['m_score'] = self._rfm_monetary_score(r['monetary'], rows)
            r['rfm'] = f"{r['r_score']}{r['f_score']}{r['m_score']}"
            r['segment'] = self._rfm_segment(r['r_score'], r['f_score'], r['m_score'])

        segments = defaultdict(lambda: {'count': 0, 'value': 0.0})
        for r in rows:
            segments[r['segment']]['count'] += 1
            segments[r['segment']]['value'] += r['monetary']
        seg_list = [{'segment': k, 'count': v['count'], 'value': v['value']} for k, v in segments.items()]
        seg_list.sort(key=lambda s: s['value'], reverse=True)
        return {'segments': seg_list, 'rows': rows[:50], 'insufficient_data': False}

    @staticmethod
    def _rfm_monetary_score(monetary, all_rows):
        if not all_rows:
            return 1
        vals = sorted(r['monetary'] for r in all_rows)
        idx = vals.index(monetary) if monetary in vals else 0
        pct = idx / max(len(vals) - 1, 1)
        return min(5, max(1, int(pct * 5) + 1))

    @staticmethod
    def _rfm_segment(r, f, m):
        avg = (r + f + m) / 3.0
        if r >= 4 and f >= 4 and m >= 4:
            return 'VIP'
        if r >= 3 and f >= 3:
            return _('Frecuente')
        if r <= 2 and f >= 3:
            return _('En riesgo')
        if r <= 2:
            return _('Inactivo')
        if f <= 1:
            return _('Nuevo')
        return _('En crecimiento')

    # ------------------------------------------------------------------
    # Pareto
    # ------------------------------------------------------------------

    @api.model
    def _build_pareto(self, parsed, kind='customers', cache=None):
        if kind == 'products':
            data = self._build_top_products(parsed, limit=100, cache=cache)
            rows = [{'id': r['product_id'], 'name': r['name'], 'value': r['sales']} for r in data['rows']]
        else:
            data = self._build_top_customers(parsed, limit=100, cache=cache)
            rows = [{'id': r['partner_id'], 'name': r['name'], 'value': r['sales']} for r in data['rows']]
        total = sum(r['value'] for r in rows) or 1.0
        cumulative = 0.0
        eighty_count = 0
        chart = []
        for i, row in enumerate(rows):
            cumulative += row['value']
            pct = cumulative / total * 100.0
            chart.append({'name': row['name'], 'value': row['value'], 'cumulative_pct': pct})
            if pct <= 80:
                eighty_count = i + 1
        top_share = (rows[0]['value'] / total * 100.0) if rows else 0.0
        if len(rows) >= 3:
            top3 = sum(r['value'] for r in rows[:3]) / total * 100.0
            top_share = top3
        return {
            'kind': kind,
            'rows': chart[:20],
            'eighty_count': eighty_count,
            'top_share_pct': top_share,
            'total': total,
            'risk': top_share > self._dashboard_config(parsed).concentration_max_pct,
        }

    # ------------------------------------------------------------------
    # Cohortes
    # ------------------------------------------------------------------

    @api.model
    def _build_cohorts(self, parsed):
        Move = self.env['account.move']
        base = [
            ('company_id', '=', parsed['company'].id),
            ('move_type', 'in', ('out_invoice', 'out_receipt')),
            ('state', '=', 'posted'),
        ]
        partners = self.env['res.partner'].search([('customer_rank', '>', 0)], limit=500)
        if not partners:
            return {'matrix': [], 'insufficient_data': True}

        first_purchase = {}
        for p in partners:
            inv = Move.search(base + [('partner_id', 'child_of', p.id)], order='invoice_date asc, id asc', limit=1)
            if inv and inv.invoice_date:
                key = inv.invoice_date.strftime('%Y-%m')
                first_purchase[p.id] = key

        cohorts = defaultdict(lambda: defaultdict(int))
        for pid, cohort_month in first_purchase.items():
            invs = Move.search(base + [
                ('partner_id', 'child_of', pid),
                ('invoice_date', '>=', parsed['date_from']),
                ('invoice_date', '<=', parsed['date_to']),
            ])
            for inv in invs:
                if inv.invoice_date:
                    activity_month = inv.invoice_date.strftime('%Y-%m')
                    cohorts[cohort_month][activity_month] += 1

        matrix = []
        for cohort, activities in sorted(cohorts.items())[-12:]:
            matrix.append({
                'cohort': cohort,
                'size': sum(activities.values()),
                'months': dict(activities),
            })
        return {'matrix': matrix, 'insufficient_data': len(matrix) < 2}
