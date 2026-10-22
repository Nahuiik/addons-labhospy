# -*- coding: utf-8 -*-
"""Capa de presentación gerencial: semántica KPI, insights y resumen enriquecido."""

from odoo import _, api, models

PRIMARY_KPI_KEYS = (
    'net_sales', 'gross_margin', 'target_achievement',
    'avg_ticket', 'active_customers', 'pipeline_open',
)

KPI_SEMANTICS = {
    'net_sales': {'direction': 'up', 'tier': 'primary'},
    'gross_margin': {'direction': 'up', 'tier': 'primary'},
    'target_achievement': {'direction': 'up', 'tier': 'primary'},
    'avg_ticket': {'direction': 'up', 'tier': 'primary'},
    'active_customers': {'direction': 'up', 'tier': 'primary'},
    'pipeline_open': {'direction': 'up', 'tier': 'primary'},
    'growth': {'direction': 'up', 'tier': 'secondary'},
    'forecast_close': {'direction': 'up', 'tier': 'secondary'},
    'gross_invoicing': {'direction': 'up', 'tier': 'secondary'},
    'credit_notes': {'direction': 'down', 'tier': 'secondary'},
    'returns': {'direction': 'down', 'tier': 'secondary'},
    'order_count': {'direction': 'up', 'tier': 'secondary'},
    'invoice_count': {'direction': 'up', 'tier': 'secondary'},
    'margin_pct': {'direction': 'up', 'tier': 'secondary'},
    'new_customers': {'direction': 'up', 'tier': 'secondary'},
    'conversion_rate': {'direction': 'up', 'tier': 'secondary'},
}


class SalesDashboardUI(models.AbstractModel):
    _inherit = 'sales.dashboard.service'

    @api.model
    def _build_kpi_cards(self, parsed, current, previous, cache=None, sparkline_days=14):
        cards = super()._build_kpi_cards(parsed, current, previous, cache, sparkline_days)
        return [self._enrich_kpi_card(card, parsed, current, previous) for card in cards]

    @api.model
    def _enrich_kpi_card(self, card, parsed, current, previous):
        key = card.get('key')
        sem = KPI_SEMANTICS.get(key, {'direction': 'up', 'tier': 'secondary'})
        card['tier'] = sem.get('tier', 'secondary')
        card['direction'] = sem.get('direction', 'up')
        card['has_data'] = True
        card['is_configured'] = True
        card['empty_reason'] = False
        card['display_value'] = card.get('value')
        card['semantic_tone'] = self._kpi_semantic_tone(card)

        val = card.get('value') or 0.0
        prev_val = card.get('previous_value') or 0.0
        compare_mode = parsed.get('compare_mode', 'previous')

        if key == 'target_achievement':
            target = current.get('target_achievement', {}).get('target') or 0.0
            card['is_configured'] = bool(target)
            if not target:
                card['has_data'] = False
                card['empty_reason'] = _('Meta no configurada')
                card['display_value'] = None
        elif key in ('pipeline_open', 'forecast_close', 'conversion_rate'):
            if key == 'pipeline_open' and val == 0:
                count = current.get('pipeline_open', {}).get('count', 0)
                if not count:
                    card['has_data'] = False
                    card['empty_reason'] = _('Sin oportunidades en el período')
            elif key == 'conversion_rate' and val == 0:
                leads = current.get('conversion_rate', {}).get('ids', [])
                if not leads:
                    card['has_data'] = False
                    card['empty_reason'] = _('Sin oportunidades en el período')
        elif key == 'growth' and compare_mode == 'none':
            card['has_data'] = False
            card['empty_reason'] = _('No hay datos comparativos')
        elif compare_mode != 'none' and not prev_val and val == 0:
            if key not in ('target_achievement',):
                card['empty_reason'] = card.get('empty_reason') or _('Sin movimiento en el período')

        if key == 'gross_margin' and val == 0 and current.get('net_sales', {}).get('value', 0) > 0:
            card['has_data'] = False
            card['empty_reason'] = _('Sin costos disponibles')

        card['semantic_tone'] = self._kpi_semantic_tone(card)
        return card

    @api.model
    def _kpi_semantic_tone(self, card):
        if not card.get('has_data', True) or card.get('empty_reason'):
            return 'neutral'
        direction = card.get('direction', 'up')
        var = card.get('variation_pct') or 0.0
        if abs(var) < 0.05:
            return 'neutral'
        good = var > 0 if direction == 'up' else var < 0
        return 'success' if good else 'danger'

    @api.model
    def _build_goal_tracker(self, parsed, cache=None, metrics=None):
        data = super()._build_goal_tracker(parsed, cache, metrics=metrics)
        target = data.get('target') or 0.0
        actual = data.get('actual') or 0.0
        data['is_configured'] = bool(target)
        data['gap'] = actual - target
        data['gap_abs'] = abs(data['gap'])
        data['configure_action'] = False
        if not target and self.env.user.has_group(
            'gn_sales_dashboard.group_sales_dashboard_manager',
        ):
            data['configure_action'] = {
                'type': 'ir.actions.act_window',
                'name': _('Metas comerciales'),
                'res_model': 'sales.dashboard.target',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
                'context': {'default_company_id': parsed['company'].id},
            }
        return data

    @api.model
    def _build_health_score(self, parsed, cache=None, metrics=None, prev_metrics=None):
        data = super()._build_health_score(parsed, cache, metrics=metrics, prev_metrics=prev_metrics)
        total_weight = sum(f.get('weight', 0) for f in data.get('factors', [])) or 100.0
        enriched = []
        for f in data.get('factors', []):
            norm = f.get('score', 0.0)
            weight = f.get('weight', 0.0)
            weighted = norm * weight / total_weight
            status = 'good' if norm >= 70 else 'warn' if norm >= 45 else 'bad'
            enriched.append({
                **f,
                'normalized_score': round(norm, 1),
                'weighted_score': round(weighted, 2),
                'status': status,
                'description': self._health_factor_description(f.get('key')),
                'metric': self._health_factor_metric(f.get('key')),
            })
        data['factors'] = enriched
        data['title'] = _('Índice de desempeño comercial')
        data['score_label'] = f"{data.get('score', 0)} / 100"
        score_delta = (data.get('score', 0) or 0) - (data.get('previous_score', 0) or 0)
        data['score_delta'] = round(score_delta, 1)
        return data

    @api.model
    def _health_factor_description(self, key):
        texts = {
            'growth': _('Variación de ventas netas vs período comparativo.'),
            'target': _('Ventas netas alcanzadas respecto a la meta del período.'),
            'margin': _('Margen bruto sobre ventas netas facturadas.'),
            'conversion': _('Oportunidades ganadas vs creadas en CRM.'),
            'concentration': _('Participación de los principales clientes.'),
            'returns': _('Notas de crédito como % de ventas netas.'),
            'pipeline': _('Valor del pipeline abierto vs ventas del período.'),
            'recurring': _('Clientes recurrentes vs activos.'),
            'ticket': _('Tendencia del ticket promedio.'),
        }
        return texts.get(key, '')

    @api.model
    def _health_factor_metric(self, key):
        mapping = {
            'growth': 'growth', 'target': 'target_achievement', 'margin': 'margin_pct',
            'conversion': 'conversion_rate', 'concentration': 'pareto_customers',
            'returns': 'credit_notes', 'pipeline': 'pipeline_open',
            'recurring': 'active_customers', 'ticket': 'avg_ticket',
        }
        return mapping.get(key, 'net_sales')

    @api.model
    def _build_summary_advanced(self, parsed, cache, metrics=None, prev_metrics=None):
        data = super()._build_summary_advanced(parsed, cache, metrics, prev_metrics)
        if metrics is None:
            metrics = self._compute_metrics(parsed, cache)
        if prev_metrics is None:
            compare = self._comparison_parsed(parsed)
            prev_metrics = self._compute_metrics(compare, cache) if compare else {}
        data['insights'] = self._build_insights(parsed, cache, metrics, prev_metrics)
        data['top5'] = self._build_summary_top5(parsed, cache)
        data['closing_forecast'] = self._build_closing_forecast_summary(
            parsed, cache, metrics, data.get('goal_tracker', {}),
        )
        alerts = data.get('alerts', {})
        items = alerts.get('items', [])
        alerts['counts'] = {
            'critical': sum(1 for a in items if a.get('severity') == 'critical'),
            'warning': sum(1 for a in items if a.get('severity') == 'warning'),
            'info': sum(1 for a in items if a.get('severity') == 'info'),
        }
        for item in items:
            item['action_label'] = self._alert_action_label(item.get('metric'))
        data['alerts'] = alerts
        return data

    @api.model
    def _alert_action_label(self, metric):
        labels = {
            'net_sales': _('Ver ventas'),
            'margin_pct': _('Ver productos con bajo margen'),
            'target_achievement': _('Ver meta'),
            'pareto_customers': _('Ver clientes concentrados'),
            'credit_notes': _('Analizar devoluciones'),
            'pipeline_open': _('Revisar pipeline'),
            'invoice_count': _('Abrir facturas pendientes'),
        }
        return labels.get(metric, _('Analizar'))

    @api.model
    def _build_insights(self, parsed, cache, metrics, prev_metrics):
        insights = []
        net = metrics['net_sales']['value']
        prev_net = prev_metrics.get('net_sales', {}).get('value', 0.0)
        growth = self._variation_pct(net, prev_net)
        if parsed.get('compare_mode') != 'none' and abs(growth) >= 5:
            insights.append({
                'title': _('Crecimiento de ventas') if growth > 0 else _('Caída de ventas'),
                'explanation': _(
                    'Las ventas netas variaron %(pct).1f%% respecto al período comparativo.',
                    pct=growth,
                ),
                'severity': 'info' if growth > 0 else 'warning',
                'value': growth,
                'comparison': prev_net,
                'metric': 'net_sales',
                'action_label': _('Ver ventas'),
            })
        credits = metrics['credit_notes']['value']
        if net and credits / net > 0.08:
            insights.append({
                'title': _('Impacto de notas de crédito'),
                'explanation': _(
                    'Las devoluciones representan %(p).1f%% de las ventas netas.',
                    p=credits / net * 100,
                ),
                'severity': 'warning',
                'value': credits,
                'comparison': net,
                'metric': 'credit_notes',
                'action_label': _('Analizar devoluciones'),
            })
        pipeline = metrics['pipeline_open']['value']
        if net and pipeline < net * 0.5:
            insights.append({
                'title': _('Baja cobertura de pipeline'),
                'explanation': _('El pipeline abierto cubre menos del 50% de las ventas del período.'),
                'severity': 'info',
                'value': pipeline,
                'comparison': net * 0.5,
                'metric': 'pipeline_open',
                'action_label': _('Revisar pipeline'),
            })
        goal = self._build_goal_tracker(parsed, cache, metrics)
        if goal.get('is_configured') and goal.get('risk') in ('critical', 'warning'):
            insights.append({
                'title': _('Riesgo de incumplimiento de meta'),
                'explanation': goal.get('message', ''),
                'severity': goal.get('risk', 'warning'),
                'value': goal.get('achievement', 0),
                'comparison': 100.0,
                'metric': 'target_achievement',
                'action_label': _('Ver meta'),
            })
        pareto = self._build_pareto(parsed, 'customers', cache=cache)
        if pareto.get('top_share_pct', 0) > 50:
            insights.append({
                'title': _('Alta concentración de clientes'),
                'explanation': _(
                    'Los principales clientes concentran %(p).1f%% de las ventas.',
                    p=pareto['top_share_pct'],
                ),
                'severity': 'warning',
                'value': pareto['top_share_pct'],
                'comparison': 50.0,
                'metric': 'pareto_customers',
                'action_label': _('Ver clientes'),
            })
        return insights[:5]

    @api.model
    def _build_summary_top5(self, parsed, cache):
        sellers = self._build_seller_ranking(parsed, limit=5, cache=cache)
        products = self._build_top_products(parsed, limit=5, cache=cache)
        customers = self._build_top_customers(parsed, limit=5, cache=cache)
        return {
            'sellers': sellers.get('rows', []),
            'products': products.get('rows', []),
            'customers': customers.get('rows', []),
        }

    @api.model
    def _build_closing_forecast_summary(self, parsed, cache, metrics, goal_tracker):
        net = metrics['net_sales']['value']
        days_total = (parsed['date_to'] - parsed['date_from']).days + 1
        days_elapsed = goal_tracker.get('days_elapsed') or max(1, days_total)
        days_remaining = goal_tracker.get('days_remaining', 0)
        projection = goal_tracker.get('projection', net)
        daily = goal_tracker.get('daily_actual', net / days_elapsed if days_elapsed else 0)
        confidence = 'limited'
        by_day = self._daily_net_sales_map(parsed, cache)
        if len(by_day) >= 7:
            confidence = 'reliable'
        elif len(by_day) >= 3:
            confidence = 'limited'
        else:
            confidence = 'unavailable'
        conservative = net + daily * 0.85 * days_remaining
        optimistic = net + daily * 1.15 * days_remaining
        target = goal_tracker.get('target') or 0.0
        return {
            'projection': projection,
            'conservative': conservative,
            'optimistic': optimistic,
            'target': target,
            'gap_to_target': projection - target if target else 0.0,
            'confidence': confidence,
            'method': _('Ritmo diario acumulado y tendencia reciente'),
            'has_data': confidence != 'unavailable',
        }
