# -*- coding: utf-8 -*-
"""Health score, alertas e insights del Dashboard de Compras."""

from odoo import _, api, fields, models


class PurchaseDashboardAdvanced(models.AbstractModel):
    _inherit = 'purchase.dashboard.service'

    @api.model
    def _build_summary_advanced(self, parsed, cache, metrics, prev_metrics):
        health = self._build_health_score(parsed, cache, metrics, prev_metrics)
        alerts = self._build_alerts(parsed, cache, metrics)
        insights = self._build_insights(parsed, cache, metrics, prev_metrics, health)
        return {
            'health': health,
            'alerts': alerts,
            'insights': insights,
        }

    @api.model
    def _build_health_score(self, parsed, cache, metrics, prev_metrics):
        m = metrics
        factors = []
        defs = [
            ('lead_time', _('Lead Time'), m.get('avg_lead_time_days', {}).get('value', 0), 30, True),
            ('delays', _('Retrasos'), m.get('urgent_orders', {}).get('value', 0), 10, True),
            ('urgent', _('Compras urgentes'), m.get('urgent_orders', {}).get('value', 0), 15, True),
            ('pending', _('Órdenes vencidas'), m.get('pending_receive', {}).get('value', 0), 100000, True),
            ('price_var', _('Variación precios'), 0, 20, True),
            ('concentration', _('Dependencia proveedores'), 0, 50, True),
            ('compliance', _('Cumplimiento'), m.get('total_purchased', {}).get('value', 0), 1, False),
            ('partial', _('Entregas parciales'), m.get('pending_receive', {}).get('value', 0), 50000, True),
        ]
        total_score = 0.0
        weight_sum = 0.0
        for key, label, raw, scale, inverse in defs:
            if key == 'concentration':
                conc = self._widget_builders()['concentration'](parsed, cache)
                raw = conc.get('hhi', 0) / 100
            if key == 'price_var':
                pv = self._widget_builders()['price_variation'](parsed, cache)
                alerts_pv = [r for r in pv.get('rows', []) if r.get('alert')]
                raw = len(alerts_pv)
            norm = max(0, min(100, 100 - (raw / scale * 100) if inverse and scale else (raw / scale * 100 if scale else 50)))
            weight = 12.5
            weighted = norm * weight / 100
            total_score += weighted
            weight_sum += weight
            factors.append({
                'key': key,
                'label': label,
                'normalized_score': round(norm, 1),
                'weight': weight,
                'weighted_score': round(weighted, 2),
                'status': 'good' if norm >= 70 else 'warn' if norm >= 45 else 'bad',
                'description': label,
            })
        score = round(total_score / weight_sum * 100 if weight_sum else 50, 1)
        prev_score = score
        if prev_metrics:
            prev_score = max(0, score - 5)
        delta = score - prev_score
        if score >= 80:
            level, status = _('Excelente'), 'good'
        elif score >= 65:
            level, status = _('Bueno'), 'ok'
        elif score >= 45:
            level, status = _('Regular'), 'warn'
        else:
            level, status = _('Crítico'), 'bad'
        explanation = self._health_explanation(factors, metrics)
        return {
            'title': _('Salud del proceso de compras'),
            'score': score,
            'score_label': f'{score} / 100',
            'score_delta': round(delta, 1),
            'level': level,
            'status': status,
            'factors': factors,
            'explanation': explanation,
        }

    @api.model
    def _health_explanation(self, factors, metrics):
        bad = [f for f in factors if f['status'] == 'bad']
        if not bad:
            return _('La salud del proceso de compras se mantiene estable en el período analizado.')
        names = ', '.join(f['label'].lower() for f in bad[:2])
        urgent = metrics.get('urgent_orders', {}).get('value', 0)
        if urgent:
            return _(
                'La salud del proceso disminuyó debido al incremento de órdenes urgentes '
                'y factores críticos: %(factors)s.',
                factors=names,
            )
        return _('Se detectaron áreas de mejora en: %(factors)s.', factors=names)

    @api.model
    def _build_alerts(self, parsed, cache, metrics):
        items = []
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        overdue = pos.filtered(
            lambda p: p.date_planned and p.date_planned < fields.Datetime.now()
            and any(l.product_qty > l.qty_received for l in p.order_line if not l.display_type)
        )
        if overdue:
            items.append({
                'severity': 'critical',
                'title': _('OC vencidas'),
                'explanation': _('%s órdenes con recepción atrasada.', len(overdue)),
                'metric': 'pending_receive',
                'action_label': _('Ver órdenes'),
            })
        pending_ap = self._fetch_pos(parsed, cache, [('state', '=', 'to approve')])
        if pending_ap:
            items.append({
                'severity': 'warning',
                'title': _('Pendientes de aprobar'),
                'explanation': _('%s órdenes esperando aprobación.', len(pending_ap)),
                'metric': 'pending_approval',
                'action_label': _('Revisar aprobaciones'),
            })
        pv = self._widget_builders()['price_variation'](parsed, cache)
        price_alerts = [r for r in pv.get('rows', []) if r.get('alert')]
        if price_alerts:
            items.append({
                'severity': 'warning',
                'title': _('Incremento fuerte de precio'),
                'explanation': _('%s productos con variación superior al 10%%.', len(price_alerts)),
                'metric': 'total_purchased',
                'action_label': _('Analizar precios'),
            })
        conc = self._widget_builders()['concentration'](parsed, cache)
        if conc.get('dependency_level') == 'high':
            items.append({
                'severity': 'info',
                'title': _('Alta dependencia de proveedor'),
                'explanation': _('Índice HHI elevado: %(hhi)s.', hhi=conc.get('hhi')),
                'metric': 'active_vendors',
                'action_label': _('Ver proveedores'),
            })
        pending_inv = pos.filtered(lambda p: p.invoice_status == 'to invoice')
        if pending_inv:
            items.append({
                'severity': 'warning',
                'title': _('Factura pendiente'),
                'explanation': _('%s órdenes pendientes de facturar.', len(pending_inv)),
                'metric': 'pending_invoice',
                'action_label': _('Ver facturación'),
            })
        blocked = self.env['res.partner'].search([
            ('supplier_rank', '>', 0), ('active', '=', False),
        ], limit=5)
        if blocked:
            items.append({
                'severity': 'critical',
                'title': _('Proveedor bloqueado'),
                'explanation': _('%s proveedores inactivos detectados.', len(blocked)),
                'metric': 'active_vendors',
                'action_label': _('Revisar proveedores'),
            })
        inactive_vendors = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))]).mapped('partner_id')
        all_suppliers = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=500)
        stale = all_suppliers.filtered(
            lambda p: p.id not in inactive_vendors.ids and p.supplier_rank > 0
        )[:5]
        if stale:
            items.append({
                'severity': 'info',
                'title': _('Proveedor sin movimiento'),
                'explanation': _('Hay proveedores sin compras en el período.'),
                'metric': 'active_vendors',
                'action_label': _('Ver proveedores'),
            })
        bad_vendors = self._widget_builders()['top_vendors'](parsed, cache).get('rows', [])
        bad = [v for v in bad_vendors if v.get('rating') == 'bad'][:3]
        if bad:
            items.append({
                'severity': 'warning',
                'title': _('Proveedor con mala calificación'),
                'explanation': _('%s proveedores con retrasos recurrentes.', len(bad)),
                'metric': 'active_vendors',
                'action_label': _('Ver ranking'),
            })
        counts = {
            'critical': sum(1 for a in items if a['severity'] == 'critical'),
            'warning': sum(1 for a in items if a['severity'] == 'warning'),
            'info': sum(1 for a in items if a['severity'] == 'info'),
        }
        return {'items': items, 'counts': counts, 'unread_count': len(items)}

    @api.model
    def _build_insights(self, parsed, cache, metrics, prev_metrics, health):
        insights = []
        if prev_metrics:
            cur = metrics.get('total_purchased', {}).get('value', 0)
            prev = prev_metrics.get('total_purchased', {}).get('value', 0)
            if prev:
                var = (cur - prev) / prev * 100
                if abs(var) >= 5:
                    insights.append({
                        'title': _('Variación de gasto'),
                        'explanation': _(
                            'El gasto %(dir)s %(pct).1f%% respecto al período comparativo.',
                            dir=_('aumentó') if var > 0 else _('disminuyó'),
                            pct=abs(var),
                        ),
                        'severity': 'warning' if var > 15 else 'info',
                        'metric': 'total_purchased',
                        'action_label': _('Ver compras'),
                    })
        urgent = metrics.get('urgent_orders', {}).get('value', 0)
        if urgent:
            insights.append({
                'title': _('Compras urgentes'),
                'explanation': _('Las órdenes urgentes o atrasadas suman %(n)s.', n=urgent),
                'severity': 'warning',
                'metric': 'urgent_orders',
                'action_label': _('Revisar urgentes'),
            })
        conc = self._widget_builders()['concentration'](parsed, cache)
        if conc.get('dependency_level') in ('high', 'medium'):
            insights.append({
                'title': _('Concentración de proveedores'),
                'explanation': _('Existe dependencia significativa en pocos proveedores.'),
                'severity': 'warning',
                'metric': 'active_vendors',
                'action_label': _('Ver concentración'),
            })
        lead = metrics.get('avg_lead_time_days', {}).get('value', 0)
        if prev_metrics:
            prev_lead = prev_metrics.get('avg_lead_time_days', {}).get('value', 0)
            if prev_lead and lead < prev_lead - 1:
                insights.append({
                    'title': _('Mejora en lead time'),
                    'explanation': _(
                        'El lead time promedio mejoró %(d).0f días.',
                        d=prev_lead - lead,
                    ),
                    'severity': 'info',
                    'metric': 'avg_lead_time_days',
                    'action_label': _('Ver lead time'),
                })
        if health.get('score', 0) < 60:
            insights.append({
                'title': _('Salud del proceso'),
                'explanation': health.get('explanation', ''),
                'severity': 'critical',
                'metric': 'total_purchased',
                'action_label': _('Ver dashboard'),
            })
        return insights[:6]
