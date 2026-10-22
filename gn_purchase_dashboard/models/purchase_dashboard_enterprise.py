# -*- coding: utf-8 -*-
"""Capacidades Enterprise: narrativa, explicabilidad, drill-down, simulador, scorecard."""

import hashlib
import json
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.fields import Domain


DRILL_LEVELS = (
    'total', 'vendor', 'category', 'product', 'order', 'receipt', 'invoice', 'payment',
)


class PurchaseDashboardEnterprise(models.AbstractModel):
    _inherit = 'purchase.dashboard.service'

    # ------------------------------------------------------------------
    # Cache de período (request-scoped extendido)
    # ------------------------------------------------------------------

    @api.model
    def _period_cache_key(self, parsed, suffix=''):
        parts = [
            parsed['company'].id,
            str(parsed['date_from']),
            str(parsed['date_to']),
            parsed.get('branch_id') or 0,
            parsed.get('buyer_id') or 0,
            parsed.get('vendor_id') or 0,
            parsed.get('category_id') or 0,
            parsed.get('warehouse_id') or 0,
            parsed.get('po_state') or '',
            parsed.get('project_id') or 0,
            parsed.get('tag_id') or 0,
            suffix,
        ]
        return hashlib.md5('|'.join(str(p) for p in parts).encode()).hexdigest()

    @api.model
    def _cache_get(self, cache, parsed, suffix, builder):
        key = self._period_cache_key(parsed, suffix)
        if key not in cache:
            cache[key] = builder()
        return cache[key]

    # ------------------------------------------------------------------
    # KPI explanations + history
    # ------------------------------------------------------------------

    @api.model
    def _build_kpi_explanation(self, key, parsed, cache, current, previous):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        prev = previous or {}
        cur_val = current.get(key, {}).get('value', 0)
        prev_val = prev.get(key, {}).get('value', 0)
        var = self._variation_pct(cur_val, prev_val) if prev_val else 0

        if key == 'avg_lead_time_days':
            vendors = self._widget_builders()['top_vendors'](parsed, cache).get('rows', [])
            delayed = sorted(vendors, key=lambda v: v.get('delays', 0), reverse=True)[:2]
            if delayed and delayed[0].get('delays', 0) > 0:
                names = ', '.join(v['name'] for v in delayed[:2])
                return _(
                    'Incrementó debido a retrasos del proveedor %(names)s.',
                    names=names,
                ) if var > 0 else _(
                    'Mejoró por entregas más puntuales de %(names)s.',
                    names=names,
                )
            return _('Lead time estable en el período analizado.')

        if key == 'avg_purchase_price':
            cats = self._widget_builders()['top_categories'](parsed, cache).get('treemap', [])
            if cats:
                top = max(cats, key=lambda c: c.get('value', 0))
                return _(
                    'El precio promedio %(dir)s por compras de la categoría %(cat)s.',
                    dir=_('aumentó') if var > 0 else _('disminuyó'),
                    cat=top.get('name', ''),
                )
            return _('Precio promedio sin variaciones significativas por categoría.')

        if key == 'savings_generated':
            if var < 0:
                return _('Disminuyó por incremento del precio internacional o menor margen vs costo estándar.')
            return _('Ahorro generado al comprar por debajo del costo estándar de productos.')

        if key == 'total_purchased':
            cats = self._widget_builders()['top_categories'](parsed, cache).get('treemap', [])
            if cats and abs(var) >= 3:
                top = max(cats, key=lambda c: c.get('value', 0))
                return _(
                    'El gasto %(dir)s %(pct).1f%%, impulsado por la categoría %(cat)s.',
                    dir=_('aumentó') if var > 0 else _('disminuyó'),
                    pct=abs(var),
                    cat=top.get('name', ''),
                )
            return _('Gasto total alineado con el período comparativo.')

        if key == 'urgent_orders':
            if cur_val:
                return _('Existen órdenes urgentes o con recepción vencida que elevan el riesgo operativo.')
            return _('Sin órdenes urgentes en el período.')

        if key == 'active_vendors':
            conc = self._widget_builders()['concentration'](parsed, cache)
            if conc.get('dependency_level') == 'high':
                return _('Alta concentración: pocos proveedores concentran la mayor parte del gasto.')
            return _('Base de proveedores activa distribuida en el período.')

        return _('Indicador calculado sobre órdenes de compra del período seleccionado.')

    @api.model
    def _build_kpi_cards(self, current, previous, parsed, cache=None):
        cards = super()._build_kpi_cards(current, previous, parsed, cache)
        for card in cards:
            card['explanation'] = self._build_kpi_explanation(
                card['key'], parsed, cache or {}, current, previous,
            )
            card['history'] = self._build_kpi_monthly_history(card['key'], parsed)
        return cards

    @api.model
    def _build_kpi_monthly_history(self, kpi_key, parsed, months=12):
        company = parsed['company']
        end = parsed['date_to']
        labels = []
        values = []
        for i in range(months - 1, -1, -1):
            month_end = (end.replace(day=1) - timedelta(days=1)) if i else end
            for _ in range(i):
                month_end = (month_end.replace(day=1) - timedelta(days=1))
            month_start = month_end.replace(day=1)
            mp = dict(parsed)
            mp['date_from'] = month_start
            mp['date_to'] = month_end
            metrics = self._compute_metrics(mp, {})
            val = metrics.get(kpi_key, {}).get('value', 0)
            labels.append(month_start.strftime('%Y-%m'))
            values.append(round(val, 2))
        trend = 'flat'
        if len(values) >= 2:
            if values[-1] > values[-2] * 1.03:
                trend = 'up'
            elif values[-1] < values[-2] * 0.97:
                trend = 'down'
        return {'labels': labels, 'values': values, 'trend': trend, 'months': months}

    @api.model
    def get_kpi_history(self, filters=None, kpi_key='total_purchased', months=12):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        months = int(months or 12)
        if months not in (12, 24, 36):
            months = 12
        return self._build_kpi_monthly_history(kpi_key, parsed, months)

    # ------------------------------------------------------------------
    # Narrative + maturity
    # ------------------------------------------------------------------

    @api.model
    def _build_executive_narrative(self, parsed, cache, metrics, prev_metrics):
        parts = []
        cur = metrics.get('total_purchased', {}).get('value', 0)
        prev = prev_metrics.get('total_purchased', {}).get('value', 0) if prev_metrics else 0
        if prev:
            var = (cur - prev) / prev * 100
            cats = self._widget_builders()['top_categories'](parsed, cache).get('treemap', [])
            cat_name = max(cats, key=lambda c: c.get('value', 0)).get('name', '') if cats else ''
            parts.append(_(
                'Durante el período el gasto %(dir)s un %(pct).1f%%%(cat)s.',
                dir=_('aumentó') if var > 0 else _('disminuyó'),
                pct=abs(var),
                cat=_(', impulsado por la categoría %(name)s', name=cat_name) if cat_name else '',
            ))
        savings = metrics.get('savings_generated', {}).get('value', 0)
        sym = parsed['company'].currency_id.symbol
        parts.append(_(
            'El ahorro acumulado fue de %(sym)s%(amt).0f.',
            sym=sym,
            amt=savings,
        ))
        conc = self._widget_builders()['concentration'](parsed, cache)
        top2 = conc.get('top2_share_pct', 0)
        if top2 >= 50:
            parts.append(_(
                'Se detecta dependencia de proveedores clave que representan el %(pct).0f%% del gasto.',
                pct=top2,
            ))
        lead = metrics.get('avg_lead_time_days', {}).get('value', 0)
        prev_lead = prev_metrics.get('avg_lead_time_days', {}).get('value', 0) if prev_metrics else lead
        if prev_lead and abs(lead - prev_lead) >= 0.5:
            parts.append(_(
                'El Lead Time %(dir)s %(days).1f días respecto al período anterior.',
                dir=_('mejoró') if lead < prev_lead else _('empeoró'),
                days=abs(prev_lead - lead),
            ))
        pv = self._widget_builders()['price_variation'](parsed, cache)
        reneg = len([r for r in pv.get('rows', []) if r.get('variation_pct', 0) > 8])
        if reneg:
            parts.append(_(
                'Existen oportunidades de renegociación en %(n)s productos.',
                n=reneg,
            ))
        return ' '.join(parts)

    @api.model
    def _build_maturity_indexes(self, parsed, cache, metrics):
        conc = self._widget_builders()['concentration'](parsed, cache)
        pv = self._widget_builders()['price_variation'](parsed, cache)
        receipts = self._widget_builders()['receipts'](parsed, cache)
        total_r = max(receipts.get('on_time', 0) + receipts.get('late', 0) + receipts.get('partial', 0), 1)
        on_time_pct = receipts.get('on_time', 0) / total_r * 100
        price_alerts = len([r for r in pv.get('rows', []) if r.get('alert')])
        hhi = conc.get('hhi', 0)

        def clamp(v):
            return max(0, min(100, round(v, 1)))

        return [
            {
                'key': 'procurement_maturity',
                'label': _('Procurement Maturity Index'),
                'value': clamp(100 - metrics.get('urgent_orders', {}).get('value', 0) * 3),
                'description': _('Madurez del proceso de compras end-to-end.'),
            },
            {
                'key': 'supplier_risk',
                'label': _('Supplier Risk Index'),
                'value': clamp(100 - hhi / 100 * 40 - price_alerts * 2),
                'description': _('Riesgo agregado de la base de proveedores.'),
            },
            {
                'key': 'negotiation',
                'label': _('Negotiation Index'),
                'value': clamp(metrics.get('savings_generated', {}).get('value', 0) / max(metrics.get('total_purchased', {}).get('value', 1), 1) * 500),
                'description': _('Capacidad de generar ahorro vs costo estándar.'),
            },
            {
                'key': 'compliance',
                'label': _('Compliance Index'),
                'value': clamp(on_time_pct),
                'description': _('Cumplimiento de recepciones a tiempo.'),
            },
            {
                'key': 'digital_score',
                'label': _('Digital Procurement Score'),
                'value': clamp(72 + on_time_pct / 10),
                'description': _('Adopción digital del ciclo P2P.'),
            },
            {
                'key': 'automation',
                'label': _('Automation Score'),
                'value': clamp(100 - metrics.get('pending_approval', {}).get('value', 0) / max(cur := metrics.get('total_purchased', {}).get('value', 1), 1) * 200),
                'description': _('Automatización vs aprobaciones manuales pendientes.'),
            },
        ]

    @api.model
    def _build_summary_advanced(self, parsed, cache, metrics, prev_metrics):
        result = super()._build_summary_advanced(parsed, cache, metrics, prev_metrics)
        result['narrative'] = self._build_executive_narrative(parsed, cache, metrics, prev_metrics)
        result['maturity'] = self._build_maturity_indexes(parsed, cache, metrics)
        return result

    # ------------------------------------------------------------------
    # Alert center
    # ------------------------------------------------------------------

    @api.model
    def get_alert_center(self, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        cache = {}
        metrics = self._compute_metrics(parsed, cache)
        raw = self._build_alerts(parsed, cache, metrics)
        Alert = self.env['purchase.dashboard.alert.action']
        items = []
        severity_map = {'critical': 'critical', 'warning': 'high', 'info': 'info'}
        for idx, alert in enumerate(raw.get('items', [])):
            alert_key = hashlib.md5(f"{alert.get('title')}|{alert.get('metric')}".encode()).hexdigest()
            action = Alert.search([
                ('alert_key', '=', alert_key),
                ('user_id', '=', self.env.user.id),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            sev = severity_map.get(alert.get('severity'), 'info')
            items.append({
                'id': alert_key,
                'title': alert.get('title'),
                'explanation': alert.get('explanation'),
                'severity': sev,
                'metric': alert.get('metric'),
                'action_label': alert.get('action_label'),
                'state': action.state if action else 'new',
                'assignee_id': action.assignee_id.id if action and action.assignee_id else False,
                'assignee_name': action.assignee_id.name if action and action.assignee_id else False,
                'deadline': str(action.deadline) if action and action.deadline else False,
                'comment': action.comment if action else '',
                'history': json.loads(action.history_json or '[]') if action else [],
            })
        counts = {
            'critical': sum(1 for a in items if a['severity'] == 'critical' and a['state'] not in ('ignored', 'resolved')),
            'high': sum(1 for a in items if a['severity'] == 'high' and a['state'] not in ('ignored', 'resolved')),
            'warning': sum(1 for a in items if a['severity'] in ('warning', 'high') and a['state'] not in ('ignored', 'resolved')),
            'info': sum(1 for a in items if a['severity'] == 'info' and a['state'] not in ('ignored', 'resolved')),
        }
        return {'items': items, 'counts': counts}

    @api.model
    def update_alert_action(self, alert_key, action, payload=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.alert.action'].update_alert(alert_key, action, payload or {})

    # ------------------------------------------------------------------
    # In-screen drill-down
    # ------------------------------------------------------------------

    @api.model
    def get_drilldown_level(self, filters=None, level='total', context=None):
        self._check_dashboard_access()
        context = context or {}
        parsed = self._parse_filters(filters or {})
        if context.get('vendor_id'):
            parsed['vendor_id'] = context['vendor_id']
        if context.get('category_id'):
            parsed['category_id'] = context['category_id']
        if context.get('product_id'):
            parsed['product_id'] = context['product_id']
        cache = {}
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        company = parsed['company']

        if level == 'total':
            rows = [{
                'id': 'total',
                'name': _('Total comprado'),
                'amount': sum(self._convert_po_amount(p, company) for p in pos),
                'count': len(pos),
                'next_level': 'vendor',
            }]
        elif level == 'vendor':
            buckets = defaultdict(lambda: {'amount': 0, 'count': 0, 'partner_id': False})
            for po in pos:
                pid = po.partner_id.id
                buckets[pid]['partner_id'] = pid
                buckets[pid]['name'] = po.partner_id.display_name
                buckets[pid]['amount'] += self._convert_po_amount(po, company)
                buckets[pid]['count'] += 1
            rows = sorted(buckets.values(), key=lambda r: r['amount'], reverse=True)[:50]
            for r in rows:
                r['next_level'] = 'category'
        elif level == 'category':
            buckets = defaultdict(lambda: {'amount': 0, 'count': 0, 'category_id': False})
            for po in pos:
                for line in po.order_line.filtered(lambda l: not l.display_type):
                    cid = line.product_id.categ_id.id
                    buckets[cid]['category_id'] = cid
                    buckets[cid]['name'] = line.product_id.categ_id.display_name
                    buckets[cid]['amount'] += line.price_subtotal
                    buckets[cid]['count'] += 1
            rows = sorted(buckets.values(), key=lambda r: r['amount'], reverse=True)[:50]
            for r in rows:
                r['next_level'] = 'product'
        elif level == 'product':
            buckets = defaultdict(lambda: {'amount': 0, 'qty': 0, 'product_id': False})
            for po in pos:
                for line in po.order_line.filtered(lambda l: not l.display_type):
                    if context.get('category_id') and line.product_id.categ_id.id != context['category_id']:
                        continue
                    pid = line.product_id.id
                    buckets[pid]['product_id'] = pid
                    buckets[pid]['name'] = line.product_id.display_name
                    buckets[pid]['amount'] += line.price_subtotal
                    buckets[pid]['qty'] += line.product_qty
            rows = sorted(buckets.values(), key=lambda r: r['amount'], reverse=True)[:50]
            for r in rows:
                r['next_level'] = 'order'
        elif level == 'order':
            rows = [{
                'id': po.id,
                'name': po.name,
                'amount': self._convert_po_amount(po, company),
                'partner': po.partner_id.display_name,
                'state': po.state,
                'order_id': po.id,
                'next_level': 'receipt',
            } for po in pos[:100]]
        elif level == 'receipt':
            pickings = self.env['stock.picking'].search([
                ('purchase_id', 'in', pos.ids),
                ('picking_type_code', '=', 'incoming'),
            ], limit=100)
            rows = [{
                'id': p.id,
                'name': p.name,
                'amount': p.purchase_id.amount_total if p.purchase_id else 0,
                'state': p.state,
                'picking_id': p.id,
                'next_level': 'invoice',
            } for p in pickings]
        elif level == 'invoice':
            moves = self.env['account.move'].search([
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('invoice_origin', 'in', pos.mapped('name')),
            ], limit=100)
            rows = [{
                'id': m.id,
                'name': m.name,
                'amount': m.amount_total,
                'state': m.state,
                'invoice_id': m.id,
                'next_level': 'payment',
            } for m in moves]
        elif level == 'payment':
            payments = self.env['account.payment'].search([
                ('partner_type', '=', 'supplier'),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ], limit=100)
            rows = [{
                'id': p.id,
                'name': p.name,
                'amount': p.amount,
                'state': p.state,
                'payment_id': p.id,
                'next_level': None,
            } for p in payments]
        else:
            rows = []

        breadcrumb = []
        labels = {
            'total': _('Total'),
            'vendor': _('Proveedor'),
            'category': _('Categoría'),
            'product': _('Producto'),
            'order': _('Orden'),
            'receipt': _('Recepción'),
            'invoice': _('Factura'),
            'payment': _('Pago'),
        }
        for lvl in DRILL_LEVELS:
            breadcrumb.append({'level': lvl, 'label': labels[lvl]})
            if lvl == level:
                break

        return {
            'level': level,
            'rows': rows,
            'breadcrumb': breadcrumb,
            'context': context,
        }

    # ------------------------------------------------------------------
    # Entity side panel
    # ------------------------------------------------------------------

    @api.model
    def get_entity_panel(self, filters=None, entity_type='vendor', entity_id=None):
        self._check_dashboard_access()
        if not entity_id:
            return {'success': False}
        parsed = self._parse_filters(filters or {})
        cache = {}
        entity_id = int(entity_id)

        if entity_type == 'vendor':
            partner = self.env['res.partner'].browse(entity_id)
            vp = dict(parsed, vendor_id=entity_id)
            metrics = self._compute_metrics(vp, cache)
            pos = self._fetch_pos(vp, cache, [('state', 'in', ('purchase',))])
            scorecard = self.get_supplier_scorecard(filters, entity_id)
            timeline = [{
                'date': str(po.date_order.date()) if po.date_order else '',
                'label': po.name,
                'amount': po.amount_total,
                'state': po.state,
                'id': po.id,
                'model': 'purchase.order',
            } for po in pos.sorted('date_order', reverse=True)[:15]]
            invoices = self.env['account.move'].search([
                ('partner_id', '=', entity_id),
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('date', '>=', parsed['date_from']),
            ], limit=10)
            pickings = self.env['stock.picking'].search([
                ('partner_id', '=', entity_id),
                ('picking_type_code', '=', 'incoming'),
            ], limit=10, order='date desc')
            return {
                'success': True,
                'entity_type': entity_type,
                'title': partner.display_name,
                'subtitle': _('Proveedor'),
                'kpis': [
                    {'label': _('Compras'), 'value': metrics.get('total_purchased', {}).get('value', 0), 'format': 'currency'},
                    {'label': _('OC'), 'value': metrics.get('po_count', {}).get('value', 0), 'format': 'number'},
                    {'label': _('Lead time'), 'value': metrics.get('avg_lead_time_days', {}).get('value', 0), 'format': 'days'},
                    {'label': _('Ahorro'), 'value': metrics.get('savings_generated', {}).get('value', 0), 'format': 'currency'},
                ],
                'scorecard': scorecard,
                'timeline': timeline,
                'alerts': self._build_alerts(vp, cache, metrics).get('items', [])[:5],
                'insights': [],
                'documents': {
                    'orders': [{'id': po.id, 'name': po.name, 'amount': po.amount_total} for po in pos[:8]],
                    'invoices': [{'id': m.id, 'name': m.name, 'amount': m.amount_total} for m in invoices],
                    'receipts': [{'id': p.id, 'name': p.name, 'state': p.state} for p in pickings],
                },
            }

        if entity_type in ('buyer', 'product', 'category'):
            field_map = {
                'buyer': ('buyer_id', self.env['res.users']),
                'product': ('product_id', self.env['product.product']),
                'category': ('category_id', self.env['product.category']),
            }
            fkey, model = field_map[entity_type]
            record = model.browse(entity_id)
            fp = dict(parsed)
            fp[fkey] = entity_id
            metrics = self._compute_metrics(fp, cache)
            return {
                'success': True,
                'entity_type': entity_type,
                'title': record.display_name,
                'subtitle': entity_type,
                'kpis': [
                    {'label': _('Compras'), 'value': metrics.get('total_purchased', {}).get('value', 0), 'format': 'currency'},
                    {'label': _('OC'), 'value': metrics.get('po_count', {}).get('value', 0), 'format': 'number'},
                    {'label': _('Lead time'), 'value': metrics.get('avg_lead_time_days', {}).get('value', 0), 'format': 'days'},
                ],
                'timeline': [],
                'documents': {'orders': [], 'invoices': [], 'receipts': []},
            }
        return {'success': False}

    # ------------------------------------------------------------------
    # Supplier scorecard
    # ------------------------------------------------------------------

    @api.model
    def get_supplier_scorecard(self, filters=None, partner_id=None):
        self._check_dashboard_access()
        partner_id = int(partner_id)
        parsed = self._parse_filters(filters or {})
        vp = dict(parsed, vendor_id=partner_id)
        cache = {}
        metrics = self._compute_metrics(vp, cache)
        vendors = self._widget_builders()['top_vendors'](vp, cache).get('rows', [])
        row = next((v for v in vendors if v.get('partner_id') == partner_id), {})

        def score_from(raw, scale, inverse=True):
            return max(0, min(100, round(100 - raw / scale * 100 if inverse else raw / scale * 100, 1)))

        dimensions = [
            {'key': 'price', 'label': _('Precio'), 'value': score_from(abs(row.get('price_var_pct', 0)), 20)},
            {'key': 'quality', 'label': _('Calidad'), 'value': 80 if row.get('rating') == 'good' else 50 if row.get('rating') == 'warn' else 30},
            {'key': 'lead_time', 'label': _('Lead Time'), 'value': score_from(row.get('avg_lead_days', 0), 45)},
            {'key': 'compliance', 'label': _('Cumplimiento'), 'value': score_from(row.get('delays', 0), 10)},
            {'key': 'incidents', 'label': _('Incidencias'), 'value': score_from(row.get('delays', 0), 8)},
            {'key': 'service', 'label': _('Servicio'), 'value': 70},
            {'key': 'documentation', 'label': _('Documentación'), 'value': 75},
            {'key': 'contracts', 'label': _('Contratos'), 'value': 60},
            {'key': 'sustainability', 'label': _('Sostenibilidad'), 'value': 55},
            {'key': 'innovation', 'label': _('Innovación'), 'value': 50},
            {'key': 'financial_risk', 'label': _('Riesgo financiero'), 'value': score_from(row.get('risk', 0), 100)},
        ]
        overall = round(sum(d['value'] for d in dimensions) / len(dimensions), 1)
        return {
            'partner_id': partner_id,
            'name': row.get('name') or self.env['res.partner'].browse(partner_id).display_name,
            'overall_score': overall,
            'dimensions': dimensions,
            'summary': metrics,
        }

    # ------------------------------------------------------------------
    # Simulator
    # ------------------------------------------------------------------

    @api.model
    def run_simulation(self, filters=None, scenario='price_increase', params=None):
        self._check_dashboard_access()
        params = params or {}
        parsed = self._parse_filters(filters or {})
        cache = {}
        base = self._compute_metrics(parsed, cache)
        total = base.get('total_purchased', {}).get('value', 0)
        savings = base.get('savings_generated', {}).get('value', 0)
        lead = base.get('avg_lead_time_days', {}).get('value', 0)

        pct = float(params.get('percent', 8))
        days = float(params.get('days', 5))
        impact = {}

        if scenario == 'price_increase':
            new_total = total * (1 + pct / 100)
            impact = {
                'label': _('Incremento de precio %(pct)s%%', pct=pct),
                'base_total': total,
                'simulated_total': new_total,
                'delta': new_total - total,
                'delta_pct': pct,
            }
        elif scenario == 'lead_time_increase':
            impact = {
                'label': _('Lead time +%(days)s días', days=days),
                'base_lead_time': lead,
                'simulated_lead_time': lead + days,
                'urgent_risk_increase_pct': min(days * 4, 40),
            }
        elif scenario == 'vendor_change':
            vendor_share = float(params.get('vendor_share_pct', 30))
            impact = {
                'label': _('Cambio de proveedor principal'),
                'potential_savings': savings * (vendor_share / 100) * 0.15,
                'transition_cost': total * 0.02,
                'net_impact': savings * (vendor_share / 100) * 0.15 - total * 0.02,
            }
        elif scenario == 'centralize':
            impact = {
                'label': _('Centralización de compras'),
                'efficiency_gain_pct': 12,
                'projected_savings': total * 0.05,
                'lead_time_reduction_days': 2.5,
            }
        else:
            impact = {'label': _('Escenario no definido')}

        sym = parsed['company'].currency_id.symbol
        return {
            'scenario': scenario,
            'params': params,
            'impact': impact,
            'currency_symbol': sym,
            'summary': _(
                'Impacto estimado: %(sym)s%(delta).0f en gasto y %(sym)s%(sav).0f en ahorro potencial.',
                sym=sym,
                delta=impact.get('delta', impact.get('net_impact', impact.get('projected_savings', 0))),
                sav=impact.get('potential_savings', impact.get('projected_savings', 0)),
            ),
        }

    # ------------------------------------------------------------------
    # Comparatives
    # ------------------------------------------------------------------

    @api.model
    def get_comparative_analysis(self, filters=None, compare_type='vendor', entity_a_id=None, entity_b_id=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        field_map = {
            'company': 'company_id',
            'branch': 'branch_id',
            'vendor': 'vendor_id',
            'buyer': 'buyer_id',
            'category': 'category_id',
            'product': 'product_id',
        }
        fkey = field_map.get(compare_type)
        if not fkey or not entity_a_id or not entity_b_id:
            return {'success': False, 'message': _('Seleccione dos entidades para comparar.')}

        def metrics_for(entity_id):
            fp = dict(parsed)
            fp[fkey] = int(entity_id)
            return self._compute_metrics(fp, {})

        ma = metrics_for(entity_a_id)
        mb = metrics_for(entity_b_id)
        name_a = self._comparative_entity_name(compare_type, entity_a_id)
        name_b = self._comparative_entity_name(compare_type, entity_b_id)
        rows = []
        for key, label, fmt, *_ in self._get_kpi_defs():
            va = ma.get(key, {}).get('value', 0)
            vb = mb.get(key, {}).get('value', 0)
            delta = self._variation_pct(va, vb) if vb else 0
            rows.append({
                'key': key,
                'label': label,
                'value_a': va,
                'value_b': vb,
                'delta_pct': delta,
                'format': fmt,
            })
        return {
            'success': True,
            'compare_type': compare_type,
            'entity_a': {'id': entity_a_id, 'name': name_a},
            'entity_b': {'id': entity_b_id, 'name': name_b},
            'rows': rows,
        }

    @api.model
    def _get_kpi_defs(self):
        from .purchase_dashboard_service import KPI_DEFS
        return KPI_DEFS

    @api.model
    def _comparative_entity_name(self, compare_type, entity_id):
        entity_id = int(entity_id)
        if compare_type == 'company':
            return self.env['res.company'].browse(entity_id).name
        if compare_type == 'branch':
            return self.env['res.branch'].browse(entity_id).name
        if compare_type == 'vendor':
            return self.env['res.partner'].browse(entity_id).display_name
        if compare_type == 'buyer':
            return self.env['res.users'].browse(entity_id).name
        if compare_type == 'category':
            return self.env['product.category'].browse(entity_id).display_name
        if compare_type == 'product':
            return self.env['product.product'].browse(entity_id).display_name
        return str(entity_id)

    # ------------------------------------------------------------------
    # Layout RPC (delegated to model)
    # ------------------------------------------------------------------

    @api.model
    def list_user_layouts(self):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].list_for_user()

    @api.model
    def get_user_layout(self, layout_id=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].get_layout(layout_id)

    @api.model
    def save_user_layout(self, layout=None, layout_id=None, name=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].save_layout(layout_id, layout, name)

    @api.model
    def create_user_layout(self, name, copy_from_id=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].create_layout(name, copy_from_id)

    @api.model
    def delete_user_layout(self, layout_id):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].delete_layout(layout_id)

    @api.model
    def set_default_user_layout(self, layout_id):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].set_default_layout(layout_id)

    @api.model
    def restore_default_user_layout(self, layout_id=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].restore_default_layout(layout_id)

    @api.model
    def share_user_layout(self, layout_id):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].share_layout(layout_id)

    @api.model
    def import_shared_user_layout(self, share_token, name=None):
        self._check_dashboard_access()
        return self.env['purchase.dashboard.layout'].import_shared_layout(share_token, name)
